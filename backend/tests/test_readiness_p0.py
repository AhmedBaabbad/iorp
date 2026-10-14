import ast
import json
import logging
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.core.config import Settings
from app.core.db import Base
from app.core.email.service import EmailService


def production_settings(**overrides):
    return Settings(_env_file=None, app_env='production', secret_key='test-only-runtime-secret-value-123456',
                    refresh_cookie_secure=True, **{'debug': False, 'email_mode': 'smtp', 'smtp_tls': True,
                    'frontend_url':'https://app.example.test', 'platform_frontend_url':'https://app.example.test', **overrides})


@pytest.mark.parametrize('override', [{'debug': True}, {'email_mode': 'console'}, {'smtp_tls': False}])
def test_production_rejects_unsafe_configuration(override):
    with pytest.raises(ValueError): production_settings(**override)


def test_valid_production_configuration():
    assert production_settings().app_env == 'production'


@pytest.mark.real_email
def test_console_and_failed_smtp_never_log_email_secrets(caplog, monkeypatch):
    service = EmailService()
    service.settings = Settings(_env_file=None, email_mode='console')
    secret = 'synthetic-reset-token-must-never-appear'
    with caplog.at_level(logging.INFO):
        assert service.send_email('private@example.invalid', secret, secret, secret)
    assert secret not in caplog.text and 'private@example.invalid' not in caplog.text
    service.settings = production_settings()
    seen = []
    def fail(*args, **kwargs):
        seen.append(kwargs['timeout'])
        raise RuntimeError(secret)
    monkeypatch.setattr('app.core.email.service.smtplib.SMTP', fail)
    assert not service.send_email('private@example.invalid', secret, secret)
    assert seen == [10] and secret not in caplog.text


def test_alembic_imports_all_runtime_tables_in_fresh_interpreter():
    root = Path(__file__).parents[1]
    tree = ast.parse((root / 'alembic/env.py').read_text(encoding='utf-8'))
    imports = [a.name for n in tree.body if isinstance(n, ast.Import) for a in n.names if a.name.startswith('app.')]
    code = '\n'.join('import ' + name for name in imports)
    code += '\nfrom app.core.db import Base\nimport json\nprint(json.dumps(sorted(Base.metadata.tables)))'
    tables = json.loads(subprocess.check_output([sys.executable, '-c', code], cwd=root, text=True))
    assert set(tables) == set(Base.metadata.tables)
    assert len([t for t in tables if t.startswith('masterdata_')]) == 5


@pytest.mark.parametrize('scope,expected', [('own', 1), ('team', 1), ('organization', 2)])
def test_summary_samples_respect_scope_and_organization(client, db, test_org, test_user, scope, expected):
    from app.foundation.infrastructure.models import Role, Permission, RolePermission, UserRole
    from app.commercial.infrastructure.models import Customer, Sample
    from app.core.auth import AuthenticatedUser
    from app.core.tenancy import TenantContext
    from app.dependencies import get_current_user
    from app.main import app
    code = 'commercial:samples:read'
    role = Role(organization_id=test_org.id, code='sample-scope', name='Sample scope')
    permission = Permission(organization_id=test_org.id, code=code, name='Read', description='Read', module_name='commercial', resource_name='samples', action_name='read')
    db.add_all([role, permission]); db.flush()
    db.add_all([UserRole(user_id=test_user.id, role_id=role.id), RolePermission(role_id=role.id, permission_id=permission.id, scope=scope)])
    for org, owner in [(test_org.id, test_user.id), (test_org.id, uuid4()), (uuid4(), test_user.id)]:
        customer = Customer(organization_id=org, customer_code=str(uuid4()), name='Customer', sales_owner_user_id=owner)
        db.add(customer); db.flush()
        db.add(Sample(customer_id=customer.id, sample_code=str(uuid4()), product_type='test', request_date=datetime.now(timezone.utc), created_by_user_id=test_user.id))
    db.commit()
    tenant = TenantContext(test_user.id, test_org.id, permissions=frozenset({code}))
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(user=test_user, tenant=tenant,
        auth_user=AuthenticatedUser(test_user.id, test_org.id, test_user.email, permissions=tenant.permissions))
    response = client.get('/api/v1/dashboard/summary')
    assert response.status_code == 200, response.text
    assert response.json()['samples_count'] == expected
