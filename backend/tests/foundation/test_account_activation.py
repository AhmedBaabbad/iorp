"""SEC-003: nobody chooses another person's first password.

A new account (organization user, platform administrator, organization root) is created without a usable password; its
owner receives an activation link valid ACCOUNT_INVITATION_EXPIRY_HOURS (24) and chooses the password. Until then
nothing signs in. The administrator can resend the link; the earlier one stops working.
"""
from datetime import timedelta

from sqlalchemy import select

from app.core.utils import utc_now
from app.foundation.infrastructure.models import TenantPasswordResetToken, User
from tests.foundation.test_session_security import admin, sign_in  # noqa: F401  (the fixture is reused)

NEW = {"full_name": "New Person", "email": "new-person@example.com", "role_codes": []}


def _create(client, headers, **extra):
    r = client.post("/api/v1/admin/users", headers=headers, json={**NEW, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_a_new_user_has_no_password_until_they_choose_one(client, db, admin, mailbox, activate):
    headers = sign_in(client, "admin@example.com", "Admin12345!")
    body = _create(client, headers, password="Chosen12345678!")  # a password sent by the administrator is ignored
    assert body["activation_pending"] is True and body["invitation_sent"] is True
    assert "new-person@example.com" in mailbox
    assert client.post("/api/v1/auth/login", json={"email": "new-person@example.com", "password": "Chosen12345678!"}).status_code == 401
    activate("new-person@example.com", "MyOwnChoice12345!")
    assert client.post("/api/v1/auth/login", json={"email": "new-person@example.com", "password": "MyOwnChoice12345!"}).status_code == 200
    assert client.get(f"/api/v1/admin/users/{body['id']}", headers=headers).json()["activation_pending"] is False


def test_the_activation_link_lasts_24_hours_and_a_reset_link_30_minutes(client, db, admin):
    headers = sign_in(client, "admin@example.com", "Admin12345!")
    body = _create(client, headers)
    token = db.scalar(select(TenantPasswordResetToken).where(TenantPasswordResetToken.used_at.is_(None)))
    expires = token.expires_at.replace(tzinfo=None) - utc_now().replace(tzinfo=None)
    assert timedelta(hours=23, minutes=59) < expires <= timedelta(hours=24)
    user = db.get(User, token.user_id)
    assert str(user.id) == body["id"]


def test_an_expired_activation_link_is_refused_and_can_be_resent(client, db, admin, mailbox):
    headers = sign_in(client, "admin@example.com", "Admin12345!")
    body = _create(client, headers)
    first = mailbox["new-person@example.com"]
    token = db.scalar(select(TenantPasswordResetToken).where(TenantPasswordResetToken.used_at.is_(None)))
    token.expires_at = utc_now() - timedelta(minutes=1)
    db.commit()
    expired = client.post("/api/v1/auth/reset-password", json={"token": first, "new_password": "MyOwnChoice12345!", "new_password_confirmation": "MyOwnChoice12345!"})
    assert expired.status_code >= 400 and "RESET_TOKEN_EXPIRED" in expired.text
    resent = client.post(f"/api/v1/admin/users/{body['id']}/reset-password", headers=headers, json={})
    assert resent.status_code == 200 and resent.json()["method"] == "invitation"
    second = mailbox["new-person@example.com"]
    assert second != first
    done = client.post("/api/v1/auth/reset-password", json={"token": second, "new_password": "MyOwnChoice12345!", "new_password_confirmation": "MyOwnChoice12345!"})
    assert done.status_code in (200, 204)


def test_resending_cancels_the_earlier_link(client, db, admin, mailbox):
    headers = sign_in(client, "admin@example.com", "Admin12345!")
    body = _create(client, headers)
    first = mailbox["new-person@example.com"]
    client.post(f"/api/v1/admin/users/{body['id']}/reset-password", headers=headers, json={})
    old = client.post("/api/v1/auth/reset-password", json={"token": first, "new_password": "MyOwnChoice12345!", "new_password_confirmation": "MyOwnChoice12345!"})
    assert old.status_code >= 400


def test_a_failed_activation_email_is_reported_and_the_user_still_exists(client, db, admin, monkeypatch):
    headers = sign_in(client, "admin@example.com", "Admin12345!")
    monkeypatch.setattr("app.core.email.service.EmailService.send_email", lambda *args, **kwargs: False)
    body = _create(client, headers)
    assert body["invitation_sent"] is False and body["activation_pending"] is True
    assert db.scalar(select(User).where(User.email == "new-person@example.com")) is not None


def test_a_new_platform_administrator_activates_their_own_account(client, monkeypatch, mailbox, activate):
    from app.core.config import settings
    monkeypatch.setattr(settings, "bootstrap_token", "activation-token")
    assert client.post("/api/v1/system/bootstrap/initialize", json={
        "bootstrap_token": "activation-token",
        "platform_root": {"full_name": "Root", "email": "root-p@example.com", "password": "PlatformRoot123!", "password_confirmation": "PlatformRoot123!"},
        "organization": {"name": "Org", "code": "org-a", "timezone": "UTC", "default_locale": "en"},
        "organization_admin": {"full_name": "Org Root", "email": "org-root@example.com", "password": "OrgRoot12345!", "password_confirmation": "OrgRoot12345!"},
    }).status_code == 201
    token = client.post("/api/v1/platform/login", json={"email": "root-p@example.com", "password": "PlatformRoot123!"}).json()["access_token"]
    created = client.post("/api/v1/platform/administrators", headers={"Authorization": f"Bearer {token}"},
                          json={"full_name": "New Admin", "email": "new-admin@example.com", "role": "admin"})
    assert created.status_code == 201 and created.json()["activation_pending"] is True and created.json()["invitation_sent"] is True
    assert client.post("/api/v1/platform/login", json={"email": "new-admin@example.com", "password": "AnyGuess12345!"}).status_code == 401
    activate("new-admin@example.com", "NewAdminOwn12345!", platform=True)
    assert client.post("/api/v1/platform/login", json={"email": "new-admin@example.com", "password": "NewAdminOwn12345!"}).status_code == 200
