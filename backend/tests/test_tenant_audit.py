"""ORG-AUDIT-002: the organization's audit trail — who changed what in the administration, when, before and after.

Its own table, written in the transaction of the change, read only through the API, one organization only; the
security log keeps sign-ins and their like (no token mechanics), the activity log the daily work."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.interfaces import audit_trail
from app.core.security import hash_password
from app.foundation.application.audit import (
    ORG_LOGO_REMOVED, ORG_LOGO_UPLOADED, ORG_PROFILE_UPDATED, ROLE_ASSIGNED, ROLE_CREATED, ROLE_DELETED, ROLE_PERMISSIONS_UPDATED,
    ROLE_REMOVED, ROLE_UPDATED, USER_ACTIVATED, USER_CREATED, USER_DEACTIVATED, USER_LOCKED, USER_PASSWORD_CHANGED,
    USER_PASSWORD_RESET, USER_UNLOCKED, USER_UPDATED, log_tenant_audit,
)
from app.foundation.domain.audit_labels import ACTIONS, ENTITIES
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, TenantActivityLog, TenantAuditEntry, TenantSecurityEvent, User

EVENTS = [USER_CREATED, USER_UPDATED, USER_DEACTIVATED, USER_ACTIVATED, USER_LOCKED, USER_UNLOCKED, USER_PASSWORD_CHANGED,
          USER_PASSWORD_RESET, ROLE_CREATED, ROLE_UPDATED, ROLE_DELETED, ROLE_ASSIGNED, ROLE_REMOVED, ROLE_PERMISSIONS_UPDATED,
          ORG_PROFILE_UPDATED, ORG_LOGO_UPLOADED, ORG_LOGO_REMOVED]
API = "/api/v1/admin/audit-log"
ROOT = Path(__file__).parents[2]


@pytest.fixture
def audit_headers(client, db, test_user):
    test_user.is_organization_root = True
    db.commit()
    response = client.post("/api/v1/auth/login", json={"email": test_user.email, "password": "Test1234!"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.parametrize("action", EVENTS)
def test_every_administrative_change_goes_to_the_audit_trail_not_the_activity_log(db, test_org, test_user, action):
    log_tenant_audit(db, test_org.id, action, "user", test_user.id, test_user.id, target_display="Somebody", details={"field": "value"})
    db.commit()
    entry = db.scalar(select(TenantAuditEntry).where(TenantAuditEntry.action == action))
    assert entry and entry.organization_id == test_org.id and entry.actor_id == test_user.id
    assert entry.actor_name == test_user.full_name  # the name, found when not given
    assert db.scalar(select(TenantActivityLog).where(TenantActivityLog.action == action)) is None


def test_passwords_and_tokens_are_never_stored(db, test_org, test_user):
    log_tenant_audit(db, test_org.id, USER_PASSWORD_CHANGED, "user", test_user.id, test_user.id,
                     details={"password": "secret", "nested": {"access_token": "jwt", "safe": True}})
    db.commit()
    entry = db.scalar(select(TenantAuditEntry).where(TenantAuditEntry.action == USER_PASSWORD_CHANGED))
    assert entry.details == {"password": "***REDACTED***", "nested": {"access_token": "***REDACTED***", "safe": True}}


def _entry(db, org_id, *, action=USER_CREATED, entity="user", actor_id=None, when=None, details=None, name="Target"):
    entry = TenantAuditEntry(organization_id=org_id, action=action, entity_type=entity, entity_id=str(uuid4()), entity_name=name,
                             actor_id=actor_id, actor_name="Org Admin", details=details, created_at=when or datetime.now(timezone.utc))
    db.add(entry); db.commit(); db.refresh(entry)
    return entry


def test_list_pages_and_filters(client, db, test_org, test_user, audit_headers):
    _entry(db, test_org.id, entity="role", action=ROLE_CREATED, name="Planners")
    _entry(db, test_org.id, entity="user", when=datetime.now(timezone.utc) - timedelta(days=10), name="Old one")
    page = client.get(API, headers=audit_headers).json()
    assert page["total"] >= 2 and {"pages", "page_size"} <= set(page)
    assert all(i["entity_type"] == "role" for i in client.get(f"{API}?entity_type=role", headers=audit_headers).json()["items"])
    assert all(i["action"] == ROLE_CREATED for i in client.get(f"{API}?action={ROLE_CREATED}", headers=audit_headers).json()["items"])
    start = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert client.get(API, params={"date_from": start, "action": USER_CREATED}, headers=audit_headers).json()["total"] == 0
    assert [i["entity_name"] for i in client.get(f"{API}?search=Plann", headers=audit_headers).json()["items"]] == ["Planners"]


def test_a_permission_is_named_in_both_languages(client, db, test_org, audit_headers):
    entry = _entry(db, test_org.id, action=ROLE_PERMISSIONS_UPDATED, entity="role",
                   details={"permission": "procurement:purchase_orders:approve", "operation": "added"})
    shown = client.get(f"{API}/{entry.id}", headers=audit_headers).json()
    assert shown["permission_names"]["procurement:purchase_orders:approve"]["en"]


def test_other_organizations_are_invisible_and_permission_is_required(client, db, test_org, audit_headers):
    other = Organization(name="Other", code="other-audit", status=OrganizationStatus.ACTIVE, timezone="UTC")
    db.add(other); db.commit()
    assert client.get(f"{API}/{_entry(db, other.id).id}", headers=audit_headers).status_code == 404
    user = User(organization_id=test_org.id, full_name="No Audit", email="no-audit@example.com",
                password_hash=hash_password("Test1234!"), status=UserStatus.ACTIVE)
    db.add(user); db.commit()
    login = client.post("/api/v1/auth/login", json={"email": user.email, "password": "Test1234!"})
    assert client.get(API, headers={"Authorization": f"Bearer {login.json()['access_token']}"}).status_code == 403


def test_the_trail_cannot_be_written_nor_deleted_through_the_api(client, audit_headers):
    assert client.post(API, headers=audit_headers, json={}).status_code == 405
    assert client.delete(f"{API}/{uuid4()}", headers=audit_headers).status_code == 405


def test_export_reads_like_the_screen(client, db, test_org, audit_headers):
    _entry(db, test_org.id, action=ROLE_ASSIGNED, entity="role_assignment", name="Omar")
    text = client.get(f"{API}/export?locale=ar", headers=audit_headers).content.decode("utf-8")
    assert "منح دور لمستخدم" in text and "role_assignment.added" not in text


def test_other_modules_record_through_the_core_interface(db, test_org, test_user):
    audit_trail.record(db, test_org.id, "announcement.sent", "announcement", uuid4(), "Safety first", test_user.id, {"recipients": 3})
    db.commit()
    assert db.scalar(select(TenantAuditEntry).where(TenantAuditEntry.action == "announcement.sent")).entity_name == "Safety first"


def test_signing_in_writes_one_security_event_and_no_token_mechanics(client, db, test_org, test_user):
    before = db.scalar(select(func.count()).select_from(TenantSecurityEvent))
    assert client.post("/api/v1/auth/login", json={"email": test_user.email, "password": "Test1234!"}).status_code == 200
    kinds = db.scalars(select(TenantSecurityEvent.event_type).order_by(TenantSecurityEvent.created_at)).all()[before:]
    assert kinds == ["tenant.login_success"]


def test_every_action_and_record_kind_has_its_words_on_the_screens():
    for lang in ("ar", "en"):
        words = json.loads((ROOT / "frontend" / "src" / "i18n" / "locales" / lang / "tenant-audit.json").read_text(encoding="utf-8"))
        assert set(ACTIONS) <= set(words["actions"]), (lang, sorted(set(ACTIONS) - set(words["actions"])))
        assert set(ENTITIES) <= set(words["entities"]), (lang, sorted(set(ENTITIES) - set(words["entities"])))


# ORG-AUDIT-003: the security log keeps what matters, counts what repeats, and forgets what is no longer useful.
from app.foundation.application import security_log as SL  # noqa: E402


def test_signing_in_again_from_the_same_device_is_counted_not_repeated(db, test_org, test_user):
    for _ in range(3):
        SL.log_tenant_security(db, test_org.id, SL.TENANT_LOGIN_SUCCESS, test_user.id, test_user.email, "10.0.0.5", "Chrome")
    SL.log_tenant_security(db, test_org.id, SL.TENANT_LOGIN_SUCCESS, test_user.id, test_user.email, "10.0.0.9", "Chrome")  # another device
    SL.log_tenant_security(db, test_org.id, SL.TENANT_LOGIN_FAILED, test_user.id, test_user.email, "10.0.0.5", "Chrome")
    SL.log_tenant_security(db, test_org.id, SL.TENANT_LOGIN_FAILED, test_user.id, test_user.email, "10.0.0.5", "Chrome")  # failures: each its own
    db.commit()
    rows = db.scalars(select(TenantSecurityEvent).where(TenantSecurityEvent.organization_id == test_org.id)
                      .order_by(TenantSecurityEvent.created_at)).all()
    assert [(r.event_type, r.ip_address, r.occurrences) for r in rows] == [
        (SL.TENANT_LOGIN_SUCCESS, "10.0.0.5", 3), (SL.TENANT_LOGIN_SUCCESS, "10.0.0.9", 1),
        (SL.TENANT_LOGIN_FAILED, "10.0.0.5", 1), (SL.TENANT_LOGIN_FAILED, "10.0.0.5", 1)]
    assert rows[0].last_seen_at is not None


def test_after_the_window_a_new_sign_in_is_a_new_entry(db, test_org, test_user):
    SL.log_tenant_security(db, test_org.id, SL.TENANT_LOGIN_SUCCESS, test_user.id, test_user.email, "10.0.0.5", "Chrome")
    db.commit()
    first = db.scalar(select(TenantSecurityEvent).where(TenantSecurityEvent.actor_id == test_user.id))
    first.created_at = first.created_at - SL.MERGE_WINDOW - timedelta(minutes=1)
    db.commit()
    SL.log_tenant_security(db, test_org.id, SL.TENANT_LOGIN_SUCCESS, test_user.id, test_user.email, "10.0.0.5", "Chrome")
    db.commit()
    assert db.scalar(select(func.count()).select_from(TenantSecurityEvent).where(TenantSecurityEvent.actor_id == test_user.id)) == 2


def test_a_failed_attempt_records_the_device_even_for_the_root(client, db, test_org, test_user):
    test_user.is_organization_root = True
    db.commit()
    client.post("/api/v1/auth/login", json={"email": test_user.email, "password": "wrong-password"}, headers={"User-Agent": "Firefox"})
    failed = db.scalar(select(TenantSecurityEvent).where(TenantSecurityEvent.event_type == SL.TENANT_LOGIN_FAILED))
    assert failed is not None and failed.ip_address and failed.user_agent == "Firefox"


def test_the_log_opens_on_important_events(client, db, test_org, test_user, audit_headers):
    SL.log_tenant_security(db, test_org.id, SL.TENANT_LOGIN_FAILED, test_user.id, test_user.email, "10.0.0.7")
    db.commit()
    important = client.get("/api/v1/admin/security-log?important=true", headers=audit_headers).json()
    assert important["items"] and all(not i["routine"] for i in important["items"])
    everything = client.get("/api/v1/admin/security-log", headers=audit_headers).json()
    assert any(i["routine"] for i in everything["items"])  # the sign-in of audit_headers


def test_purge_keeps_incidents_longer_than_sign_ins(db, test_org, test_user):
    now = datetime.now(timezone.utc)
    for event, days in ((SL.TENANT_LOGIN_SUCCESS, 100), (SL.TENANT_LOGIN_SUCCESS, 10), (SL.TENANT_LOGIN_FAILED, 100), (SL.TENANT_LOGIN_FAILED, 400)):
        db.add(TenantSecurityEvent(organization_id=test_org.id, event_type=event, actor_id=test_user.id, created_at=now - timedelta(days=days)))
    db.commit()
    assert SL.purge(db, now) == 2
    left = sorted((r.event_type, (now - r.created_at).days) for r in db.scalars(select(TenantSecurityEvent)))
    assert left == [(SL.TENANT_LOGIN_FAILED, 100), (SL.TENANT_LOGIN_SUCCESS, 10)]
