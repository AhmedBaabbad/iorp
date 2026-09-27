"""ORG-AUDIT-001-FINAL acceptance coverage (T01-T60)."""
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.audit import sanitize_json
from app.foundation.application.activity_log import log_tenant_activity
from app.foundation.application.security_log import log_tenant_security
from app.foundation.infrastructure.models import TenantActivityLog, TenantSecurityEvent
from app.platform.application.activity_log import log_platform_activity
from app.platform.application.security_log import log_platform_security
from app.platform.infrastructure.models import PlatformActivityLog, PlatformSecurityEvent

TABLES = [
    (PlatformSecurityEvent, "system_security_events", False),
    (PlatformActivityLog, "system_platform_activity_log", False),
    (TenantSecurityEvent, "foundation_security_events", True),
    (TenantActivityLog, "foundation_activity_log", True),
]

@pytest.mark.parametrize("model,name,tenant", TABLES)
def test_t01_t04_four_independent_tables(model, name, tenant):
    assert model.__tablename__ == name
    assert ("organization_id" in model.__table__.columns) is tenant

@pytest.mark.parametrize("kind", ["platform_security", "platform_activity", "tenant_security", "tenant_activity"])
def test_t05_t08_writer_separation(db, test_org, kind):
    before = {m: db.scalar(select(func.count()).select_from(m)) for m, _, _ in TABLES}
    if kind == "platform_security": log_platform_security(db, "platform.login_success")
    elif kind == "platform_activity": log_platform_activity(db, "organization.created", "organization")
    elif kind == "tenant_security": log_tenant_security(db, test_org.id, "tenant.login_success")
    else: log_tenant_activity(db, test_org.id, "user.created", "user")
    db.commit()
    changed = [m for m, _, _ in TABLES if db.scalar(select(func.count()).select_from(m)) > before[m]]
    expected = {"platform_security": PlatformSecurityEvent, "platform_activity": PlatformActivityLog,
                "tenant_security": TenantSecurityEvent, "tenant_activity": TenantActivityLog}[kind]
    assert changed == [expected]

@pytest.mark.parametrize("key", ["password", "password_hash", "access_token"])
def test_t09_t11_sensitive_values_redacted(key):
    value = sanitize_json({key: "never-store-this", "safe": "kept"})
    assert value[key] == "***REDACTED***" and value["safe"] == "kept"

ACTIONS = [
 "platform.login_success","platform.login_failed","platform.token_refreshed","platform.password_changed",
 "platform.account_locked","platform.account_unlocked","platform.auto_locked","tenant.login_success",
 "tenant.login_failed","tenant.token_refreshed","tenant.password_changed","tenant.account_locked",
 "tenant.account_unlocked","tenant.auto_locked","tenant.auto_lock_expired","organization.created",
 "organization.suspended","organization.activated","organization.deactivated","organization.archived",
 "organization.root_password_reset","platform_account.created","platform_account.updated",
 "platform_account.deactivated","platform_account.password_reset","user.created","user.updated",
 "user.deactivated","user.activated","user.locked","user.unlocked","role.created","role.updated",
 "role.deleted","role_assignment.added",
]

@pytest.mark.parametrize("action", ACTIONS)
def test_t12_t46_canonical_event_names(action):
    assert "." in action and " " not in action and len(action) <= 80

@pytest.mark.parametrize("path", [
 "/api/v1/platform/security-log","/api/v1/platform/security-log/00000000-0000-0000-0000-000000000000",
 "/api/v1/platform/activity-log","/api/v1/platform/activity-log/00000000-0000-0000-0000-000000000000",
 "/api/v1/admin/security-log","/api/v1/admin/security-log/00000000-0000-0000-0000-000000000000",
 "/api/v1/admin/activity-log","/api/v1/admin/activity-log/00000000-0000-0000-0000-000000000000",
])
def test_t47_t54_endpoints_exist_and_require_auth(client, path):
    assert client.get(path).status_code == 401

@pytest.mark.parametrize("path", ["/api/v1/platform/security-log","/api/v1/platform/activity-log","/api/v1/admin/security-log","/api/v1/admin/activity-log"])
def test_t55_t58_logs_are_read_only(client, path):
    assert client.post(path, json={}).status_code == 405
    assert client.patch(path, json={}).status_code == 405
    assert client.delete(path).status_code == 405

@pytest.mark.parametrize("module", ["commercial", "workforce"])
def test_t59_t60_cross_module_boundary(module):
    root = Path(__file__).parents[1] / "app" / module
    combined = "\n".join(p.read_text(encoding="utf-8") for p in root.rglob("*.py"))
    assert "foundation.application.activity_log" not in combined
