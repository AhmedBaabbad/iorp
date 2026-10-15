"""Batch 2 — platform sessions (SEC-004) and audit integrity (AUDIT-001).

Sessions: signing out stops the access token at once and the old refresh token cannot be reused; a sign-in lasts at most
PLATFORM_SESSION_MAX_HOURS and ends after PLATFORM_IDLE_TIMEOUT_MINUTES without use; deactivation and changes of email
or role end the account's sessions. Tenant sign-ins keep their own rules.
Audit: each sensitive platform change and its audit record are committed together; when the record cannot be written
the change is not kept; storage quota changes and refused lifecycle changes are audited.
"""
from datetime import timedelta
from uuid import UUID

import pytest
from sqlalchemy import select, update

from app.core.audit import PlatformAuditService
from app.core.security_models import AuthSession
from app.core.utils import utc_now
from app.foundation.infrastructure.models import Organization
from app.platform.infrastructure.models import PlatformAccount, PlatformActivityLog
from tests.test_platform_identity import _bootstrap, _headers
from tests.test_platform_mfa import proof

ADMIN = {"full_name": "Second Admin", "email": "second-admin@example.com", "role": "admin"}


def _me(client, token):
    return client.get("/api/v1/platform/me", headers=_headers(token))


def _admin(client, root_token, activate):
    assert client.post("/api/v1/platform/administrators", headers=proof(client, root_token, 'POST', ("/api/v1/platform/administrators").removeprefix('/api/v1'), ADMIN), json=ADMIN).status_code == 201
    activate(ADMIN["email"], "SecondAdmin12345!", platform=True)
    login = client.post("/api/v1/platform/login", json={"email": ADMIN["email"], "password": "SecondAdmin12345!"})
    assert login.status_code == 200
    return login.json()["access_token"]


def _org(db):
    return db.scalar(select(Organization).where(Organization.code == "IDENTITY-ORG"))


def _platform_sessions(db, account_email):
    account = db.scalar(select(PlatformAccount).where(PlatformAccount.email == account_email))
    return select(AuthSession).where(AuthSession.account_type == "platform", AuthSession.account_id == account.id)


# ── sessions ────────────────────────────────────────────────────────────────────────────────────

def test_signing_out_stops_the_access_token_at_once_and_the_refresh_token_cannot_be_reused(client, monkeypatch):
    token = _bootstrap(client, monkeypatch)
    old_cookie = client.cookies.get("iorp_refresh")
    assert _me(client, token).status_code == 200
    assert client.post("/api/v1/platform/logout").status_code == 204
    assert _me(client, token).status_code == 401  # not after the access token expires: now
    client.cookies.clear()
    client.cookies.set("iorp_refresh", old_cookie, path="/api/v1/platform")
    reused = client.post("/api/v1/platform/refresh")
    assert reused.status_code == 401


def test_a_reused_rotated_refresh_token_ends_the_whole_sign_in(client, monkeypatch):
    _bootstrap(client, monkeypatch)
    first = client.cookies.get("iorp_refresh")
    renewed = client.post("/api/v1/platform/refresh")
    assert renewed.status_code == 200
    fresh_token = renewed.json()["access_token"]
    client.cookies.clear()  # present only the stolen, already-rotated token
    client.cookies.set("iorp_refresh", first, path="/api/v1/platform")
    reuse = client.post("/api/v1/platform/refresh")
    assert reuse.status_code == 401 and reuse.json()["code"] == "TOKEN_REUSED"
    assert _me(client, fresh_token).status_code == 401  # the stolen-token family is closed


def test_a_platform_sign_in_has_an_absolute_lifetime(client, db, monkeypatch):
    _bootstrap(client, monkeypatch)
    db.execute(update(AuthSession).where(AuthSession.account_type == "platform").values(started_at=utc_now() - timedelta(hours=9)))
    db.commit()
    r = client.post("/api/v1/platform/refresh")
    assert r.status_code == 401 and r.json()["code"] == "SESSION_MAX_AGE"


def test_a_platform_sign_in_ends_after_the_idle_limit_but_not_while_used(client, db, monkeypatch):
    _bootstrap(client, monkeypatch)
    db.execute(update(AuthSession).where(AuthSession.account_type == "platform").values(created_at=utc_now() - timedelta(minutes=12)))
    db.commit()
    used = client.post("/api/v1/platform/refresh")
    assert used.status_code == 200  # renewed within the 15-minute limit
    db.execute(update(AuthSession).where(AuthSession.account_type == "platform", AuthSession.revoked_at.is_(None))
               .values(created_at=utc_now() - timedelta(minutes=16)))
    db.commit()
    idle = client.post("/api/v1/platform/refresh")
    assert idle.status_code == 401 and idle.json()["code"] == "SESSION_IDLE_TIMEOUT"
    assert _me(client, used.json()["access_token"]).status_code == 401


@pytest.mark.parametrize("change", [{"status": "inactive"}, {"email": "renamed-admin@example.com"}, {"role": "root"}])
def test_sensitive_account_changes_end_the_accounts_sessions(client, db, monkeypatch, activate, change):
    root = _bootstrap(client, monkeypatch)
    admin = _admin(client, root, activate)
    assert _me(client, admin).status_code == 200
    target = db.scalar(select(PlatformAccount).where(PlatformAccount.email == ADMIN["email"]))
    assert client.patch(f"/api/v1/platform/administrators/{target.id}", headers=proof(client, root, 'PATCH', (f"/api/v1/platform/administrators/{target.id}").removeprefix('/api/v1'), change), json=change).status_code == 200
    assert _me(client, admin).status_code == 401
    assert _me(client, root).status_code == 200  # only the changed account


def test_a_name_change_keeps_the_sessions(client, db, monkeypatch, activate):
    root = _bootstrap(client, monkeypatch)
    admin = _admin(client, root, activate)
    target = db.scalar(select(PlatformAccount).where(PlatformAccount.email == ADMIN["email"]))
    assert client.patch(f"/api/v1/platform/administrators/{target.id}", headers=proof(client, root, 'PATCH', (f"/api/v1/platform/administrators/{target.id}").removeprefix('/api/v1'), {"full_name": "Renamed"}), json={"full_name": "Renamed"}).status_code == 200
    assert _me(client, admin).status_code == 200


def test_tenant_sign_ins_keep_their_rules(client, db, test_user):
    """The platform idle limit does not apply to tenant sign-ins (their idle sign-out is the browser's, SEC-001)."""
    login = client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "Test1234!"})
    assert login.status_code == 200
    db.execute(update(AuthSession).where(AuthSession.account_type == "tenant").values(created_at=utc_now() - timedelta(minutes=40)))
    db.commit()
    assert client.post("/api/v1/auth/refresh").status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"}).status_code == 401


def test_an_admin_cannot_perform_root_only_operations(client, db, monkeypatch, activate):
    root = _bootstrap(client, monkeypatch)
    admin = _admin(client, root, activate)
    org = _org(db)
    assert client.post(f"/api/v1/platform/organizations/{org.id}/suspend", headers=_headers(admin), json={"reason": "x"}).status_code == 403
    assert client.post("/api/v1/platform/administrators", headers=_headers(admin), json={**ADMIN, "email": "x@example.com"}).status_code == 403
    db.refresh(org)
    assert org.status.value == "active"


# ── audit ───────────────────────────────────────────────────────────────────────────────────────

def _records(db, action):
    return db.scalars(select(PlatformActivityLog).where(PlatformActivityLog.action == action)).all()


def test_a_lifecycle_change_and_its_audit_record_are_kept_together(client, db, monkeypatch):
    root = _bootstrap(client, monkeypatch)
    org = _org(db)
    r = client.post(f"/api/v1/platform/organizations/{org.id}/suspend", headers=proof(client, root, 'POST', (f"/api/v1/platform/organizations/{org.id}/suspend").removeprefix('/api/v1'), {"reason": "Unpaid"}), json={"reason": "Unpaid"})
    assert r.status_code == 200
    [record] = _records(db, "organization.suspended")
    assert record.entity_id == org.id and record.actor_name == "Origin Root"
    assert record.details["changes"] == {"status": {"before": "active", "after": "suspended"}}
    assert record.details["outcome"] == "success" and record.details["reason"] == "Unpaid"
    assert record.details["request_id"]


def test_when_the_audit_record_fails_the_lifecycle_change_is_not_kept(client, db, monkeypatch):
    root = _bootstrap(client, monkeypatch)
    org = _org(db)

    verified_headers = proof(client, root, 'POST', (f"/api/v1/platform/organizations/{org.id}/suspend").removeprefix('/api/v1'), {"reason": "Unpaid"})
    def broken(self, **kwargs):
        raise RuntimeError("audit store unavailable")
    monkeypatch.setattr(PlatformAuditService, "record", broken)
    with pytest.raises(RuntimeError):
        client.post(f"/api/v1/platform/organizations/{org.id}/suspend", headers=verified_headers, json={"reason": "Unpaid"})
    db.rollback()
    db.expire_all()
    assert _org(db).status.value == "active"


def test_a_failing_activity_write_is_not_swallowed(client, db, monkeypatch):
    """The log writer itself failing (not only the service) must fail the change."""
    root = _bootstrap(client, monkeypatch)
    org = _org(db)
    import app.platform.application.activity_log as activity

    verified_headers = proof(client, root, 'PUT', (f"/api/v1/platform/organizations/{org.id}/storage").removeprefix('/api/v1'), {"quota_bytes": 5 * 1024 * 1024})
    def unwritable(**fields):
        raise RuntimeError("disk full")
    monkeypatch.setattr(activity, "PlatformActivityLog", unwritable)
    with pytest.raises(RuntimeError):
        client.put(f"/api/v1/platform/organizations/{org.id}/storage", headers=verified_headers, json={"quota_bytes": 5 * 1024 * 1024})
    monkeypatch.undo()
    db.rollback()
    db.expire_all()
    assert _org(db).storage_quota_bytes is None


def test_a_storage_quota_change_is_audited_with_before_and_after(client, db, monkeypatch):
    root = _bootstrap(client, monkeypatch)
    org = _org(db)
    for quota in (5 * 1024 * 1024, 7 * 1024 * 1024):
        assert client.put(f"/api/v1/platform/organizations/{org.id}/storage", headers=proof(client, root, 'PUT', (f"/api/v1/platform/organizations/{org.id}/storage").removeprefix('/api/v1'), {"quota_bytes": quota}), json={"quota_bytes": quota}).status_code == 200
    first, second = sorted(_records(db, "organization_storage_quota_changed"), key=lambda r: r.details["changes"]["quota_bytes"]["after"])
    assert first.details["changes"]["quota_bytes"] == {"before": None, "after": 5 * 1024 * 1024}
    assert second.details["changes"]["quota_bytes"] == {"before": 5 * 1024 * 1024, "after": 7 * 1024 * 1024}
    assert second.entity_id == org.id and second.actor_id is not None


def test_when_the_quota_audit_fails_the_quota_is_not_changed(client, db, monkeypatch):
    root = _bootstrap(client, monkeypatch)
    org = _org(db)
    verified_headers = proof(client, root, 'PUT', (f"/api/v1/platform/organizations/{org.id}/storage").removeprefix('/api/v1'), {"quota_bytes": 5 * 1024 * 1024})
    monkeypatch.setattr(PlatformAuditService, "record", lambda self, **kw: (_ for _ in ()).throw(RuntimeError("audit down")))
    with pytest.raises(RuntimeError):
        client.put(f"/api/v1/platform/organizations/{org.id}/storage", headers=verified_headers, json={"quota_bytes": 5 * 1024 * 1024})
    db.rollback()
    db.expire_all()
    assert _org(db).storage_quota_bytes is None


def test_when_the_audit_fails_no_administrator_is_created(client, db, monkeypatch):
    root = _bootstrap(client, monkeypatch)
    verified_headers = proof(client, root, 'POST', ("/api/v1/platform/administrators").removeprefix('/api/v1'), ADMIN)
    monkeypatch.setattr(PlatformAuditService, "record", lambda self, **kw: (_ for _ in ()).throw(RuntimeError("audit down")))
    with pytest.raises(RuntimeError):
        client.post("/api/v1/platform/administrators", headers=verified_headers, json=ADMIN)
    db.rollback()
    assert db.scalar(select(PlatformAccount).where(PlatformAccount.email == ADMIN["email"])) is None


def test_a_refused_lifecycle_change_is_audited_as_a_failure(client, db, monkeypatch):
    root = _bootstrap(client, monkeypatch)
    org = _org(db)
    r = client.post(f"/api/v1/platform/organizations/{org.id}/archive", headers=proof(client, root, 'POST', (f"/api/v1/platform/organizations/{org.id}/archive").removeprefix('/api/v1'), {"reason": "Closing"}), json={"reason": "Closing"})
    assert r.status_code == 409  # active → archived is not allowed
    [record] = _records(db, "organization_status_change_refused")
    assert record.details["outcome"] == "failure" and record.details["error_code"] == "INVALID_STATE_TRANSITION"
    db.refresh(org)
    assert org.status.value == "active"


def test_session_rows_belong_to_the_account(client, db, monkeypatch):
    _bootstrap(client, monkeypatch)
    rows = db.scalars(_platform_sessions(db, "origin@example.com")).all()
    assert rows and all(isinstance(r.family_id, UUID) for r in rows)
