"""Audit-only reproductions using in-memory data. Does not change business data."""
import ast
import importlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'backend'))
# Test Alembic's actual model-import list in a fresh interpreter, without app.main.
tree = ast.parse((ROOT / 'backend/alembic/env.py').read_text())
model_imports = [a.name for n in tree.body if isinstance(n, ast.Import) for a in n.names if a.name.startswith('app.')]
code = '\n'.join('import ' + name for name in model_imports) + "\nfrom app.core.db import Base\nprint([n for n in Base.metadata.tables if n.startswith('masterdata_')])"
metadata = subprocess.check_output([sys.executable, '-c', code], cwd=ROOT / 'backend', text=True).strip()

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.main import app
from app.core.db import Base
from app.core.auth import AuthenticatedUser
from app.core.tenancy import TenantContext
from app.core.config import Settings
from app.dependencies import get_current_user, get_db
from app.foundation.infrastructure.models import Organization, User, Permission, Role, UserRole, RolePermission
from app.commercial.infrastructure.models import Customer, Sample

engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
Base.metadata.create_all(engine)
with Session(engine) as db:
    org = Organization(name='Audit', code='audit', timezone='UTC')
    db.add(org); db.flush()
    user = User(organization_id=org.id, full_name='Audit', email='audit@example.invalid', password_hash='unused')
    role = Role(organization_id=org.id, code='audit-own', name='Audit own')
    p = Permission(organization_id=org.id, code='commercial:samples:read', name='Read', description='Read', module_name='commercial', resource_name='samples', action_name='read')
    db.add_all([user, role, p]); db.flush()
    db.add_all([UserRole(user_id=user.id, role_id=role.id), RolePermission(role_id=role.id, permission_id=p.id, scope='own')])
    for owner in (user.id, uuid4()):
        customer = Customer(organization_id=org.id, customer_code=str(owner), name='Audit', sales_owner_user_id=owner)
        db.add(customer); db.flush()
        db.add(Sample(customer_id=customer.id, sample_code=str(uuid4()), product_type='Audit', created_by_user_id=user.id, request_date=datetime.now(timezone.utc)))
    db.commit()
    tenant = TenantContext(user.id, org.id, permissions=frozenset({p.code}))
    current = SimpleNamespace(user=user, tenant=tenant, auth_user=AuthenticatedUser(user.id, org.id, user.email, permissions=tenant.permissions))
    app.dependency_overrides[get_current_user] = lambda: current
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        summary = client.get('/api/v1/dashboard/summary')
        commercial = client.get('/api/v1/commercial/dashboard')
        samples = client.get('/api/v1/commercial/samples')
    result = {'alembic_imported_masterdata_tables': metadata, 'runtime_masterdata_tables': [n for n in Base.metadata.tables if n.startswith('masterdata_')],
        'own_scope_sample_count': {'summary_status': summary.status_code, 'summary_count': summary.json()['samples_count'],
           'sample_list_status': samples.status_code, 'sample_list_total': samples.json().get('total'),
           'commercial_count': next(c['value'] for c in commercial.json()['cards'] if c['key'] == 'samples_requested')}}
    assert summary.json()['samples_count'] == 2
    assert samples.json()['total'] == 1
    assert metadata == '[]'
app.dependency_overrides.clear()
engine.dispose()
lock = json.loads((ROOT / 'frontend/package-lock.json').read_text())
result['locked_versions'] = {k: lock['packages']['node_modules/' + k]['version'] for k in ('next', 'react', 'react-dom')}
unsafe = Settings(_env_file=None, app_env='production', secret_key='synthetic-audit-key-not-a-live-secret-12345',
                  refresh_cookie_secure=True, email_mode='console', debug=True)
result['production_accepts_console_email_and_debug'] = unsafe.email_mode == 'console' and unsafe.debug
Path(__file__).with_name('probes.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
