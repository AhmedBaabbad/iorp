from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.audit import PlatformAuditService
from app.core.security import hash_password
from app.core.security_models import AuthSecurityEvent
from app.foundation.application.audit import (
    ORG_LOGO_REMOVED, ORG_LOGO_UPLOADED, ORG_PROFILE_UPDATED, ROLE_ASSIGNED,
    ROLE_CREATED, ROLE_DELETED, ROLE_PERMISSIONS_UPDATED, ROLE_REMOVED, ROLE_UPDATED,
    USER_ACTIVATED, USER_CREATED, USER_DEACTIVATED, USER_LOCKED, USER_PASSWORD_CHANGED,
    USER_PASSWORD_RESET, USER_UNLOCKED, USER_UPDATED, log_tenant_audit,
)
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, User
from app.foundation.infrastructure.models import TenantActivityLog
from app.foundation.application.activity_log import TenantActivityLogger

EVENTS = [USER_CREATED, USER_UPDATED, USER_DEACTIVATED, USER_ACTIVATED, USER_LOCKED,
          USER_UNLOCKED, USER_PASSWORD_CHANGED, USER_PASSWORD_RESET, ROLE_CREATED,
          ROLE_UPDATED, ROLE_DELETED, ROLE_ASSIGNED, ROLE_REMOVED,
          ROLE_PERMISSIONS_UPDATED, ORG_PROFILE_UPDATED, ORG_LOGO_UPLOADED, ORG_LOGO_REMOVED]


@pytest.fixture
def audit_headers(client, db, test_user):
    test_user.is_organization_root = True
    db.commit()
    response = client.post("/api/v1/auth/login", json={"email": test_user.email, "password": "Test1234!"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.parametrize("action", EVENTS)
def test_t01_t17_tenant_event_uses_activity_store(db, test_org, test_user, action):
    log_tenant_audit(db, test_org.id, action, "user", test_user.id, test_user.id,
                     test_user.full_name, test_user.email, test_user.full_name, {"field": "value"})
    db.commit()
    event = db.scalar(select(TenantActivityLog).where(TenantActivityLog.action == action))
    assert event and event.organization_id == test_org.id and event.actor_id == test_user.id


def test_t18_passwords_and_tokens_are_never_stored(db, test_org, test_user):
    log_tenant_audit(db, test_org.id, USER_PASSWORD_CHANGED, "user", test_user.id,
                     test_user.id, details={"password": "secret", "nested": {"access_token": "jwt", "safe": True}})
    db.commit(); event = db.scalar(select(TenantActivityLog).where(TenantActivityLog.action == USER_PASSWORD_CHANGED))
    assert event.details == {"password": "***REDACTED***", "nested": {"access_token": "***REDACTED***", "safe": True}}


def test_t19_audit_failure_does_not_break_primary_transaction(db, test_org, monkeypatch):
    monkeypatch.setattr(TenantActivityLogger, "log_activity", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("audit down")))
    organization = Organization(name="Still saved", code="still-saved", status=OrganizationStatus.ACTIVE, timezone="UTC")
    db.add(organization)
    log_tenant_audit(db, test_org.id, USER_UPDATED, "user")
    db.commit()
    assert db.get(Organization, organization.id) is not None


def _event(db, org_id, *, action=USER_CREATED, entity="user", actor_id=None, when=None):
    event = AuthSecurityEvent(event_type=action, category="identity", outcome="success", severity="info",
                              actor_type="tenant", account_type="tenant", account_id=actor_id,
                              organization_id=org_id, target_type=entity, target_id=str(uuid4()),
                              occurred_at=when or datetime.now(timezone.utc))
    db.add(event); db.commit(); db.refresh(event); return event


def test_t20_list_is_paginated(client, db, test_org, test_user, audit_headers):
    _event(db, test_org.id, actor_id=test_user.id)
    response = client.get("/api/v1/admin/audit-log", headers=audit_headers)
    assert response.status_code == 200 and response.json()["total"] >= 1 and "pages" in response.json()


def test_t21_filter_by_entity_type(client, db, test_org, audit_headers):
    _event(db, test_org.id, entity="role"); _event(db, test_org.id, entity="user")
    result = client.get("/api/v1/admin/audit-log?entity_type=role", headers=audit_headers).json()
    assert result["items"] and all(item["target_type"] == "role" for item in result["items"])


def test_t22_filter_by_action(client, db, test_org, audit_headers):
    _event(db, test_org.id, action=ROLE_CREATED)
    result = client.get(f"/api/v1/admin/audit-log?action={ROLE_CREATED}", headers=audit_headers).json()
    assert result["items"] and all(item["event_type"] == ROLE_CREATED for item in result["items"])


def test_t23_filter_by_date_range(client, db, test_org, audit_headers):
    _event(db, test_org.id, when=datetime.now(timezone.utc) - timedelta(days=10)); _event(db, test_org.id)
    start = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    result = client.get("/api/v1/admin/audit-log", params={"date_from": start, "action": USER_CREATED}, headers=audit_headers).json()
    assert result["total"] == 1


def test_t24_detail_returns_full_event(client, db, test_org, audit_headers):
    event = _event(db, test_org.id)
    response = client.get(f"/api/v1/admin/audit-log/{event.id}", headers=audit_headers)
    assert response.status_code == 200 and response.json()["id"] == str(event.id)


def test_t25_other_organization_is_invisible(client, db, test_org, audit_headers):
    other = Organization(name="Other", code="other-audit", status=OrganizationStatus.ACTIVE, timezone="UTC")
    db.add(other); db.commit(); event = _event(db, other.id)
    assert client.get(f"/api/v1/admin/audit-log/{event.id}", headers=audit_headers).status_code == 404


def test_t26_permission_is_required(client, db, test_org):
    user = User(organization_id=test_org.id, full_name="No Audit", email="no-audit@example.com",
                password_hash=hash_password("Test1234!"), status=UserStatus.ACTIVE)
    db.add(user); db.commit()
    login = client.post("/api/v1/auth/login", json={"email": user.email, "password": "Test1234!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/v1/admin/audit-log", headers=headers).status_code == 403


def test_t27_no_create_endpoint(client, audit_headers):
    assert client.post("/api/v1/admin/audit-log", headers=audit_headers, json={}).status_code == 405


def test_t28_no_delete_endpoint(client, audit_headers):
    assert client.delete(f"/api/v1/admin/audit-log/{uuid4()}", headers=audit_headers).status_code == 405


def test_t29_services_have_at_least_fifteen_instrumentation_calls():
    source = Path("app/foundation/application/services.py").read_text(encoding="utf-8")
    assert source.count("log_tenant_audit") >= 15


def test_t30_csv_is_utf8_bom_and_scoped(client, db, test_org, audit_headers):
    _event(db, test_org.id)
    response = client.get("/api/v1/admin/audit-log/export?locale=ar", headers=audit_headers)
    assert response.status_code == 200 and response.content.startswith(b"\xef\xbb\xbf") and "الوقت" in response.content.decode("utf-8-sig")
