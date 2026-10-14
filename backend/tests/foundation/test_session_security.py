"""SEC-001/002: sessions and passwords as security standards expect them.

- A sign-in renews itself while used (the refresh cookie rotates); it lasts at most TENANT_SESSION_MAX_HOURS.
- Ending a sign-in (signing out, "my sessions", an administrator, the session limit) stops its access token at once.
- One user is signed in on at most the organization's limit of devices: a further sign-in ends the oldest; a new device
  is notified.
- An administrator never chooses nor learns a user's password: a reset link e-mailed to the user is the only way.
"""
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, update

from app.core.security import hash_password
from app.core.security_models import AuthSession
from app.core.utils import utc_now
from app.foundation.domain.enums import UserStatus
from app.foundation.infrastructure.models import Permission, Role, RolePermission, User, UserRole
from app.notifications.infrastructure.models import NotificationItem

CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
PHONE = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Mobile Safari/537.36"
FIREFOX = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0"


def sign_in(client, email="test@example.com", password="Test1234!", agent=CHROME):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password}, headers={"User-Agent": agent})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}", "User-Agent": agent}


@pytest.fixture
def admin(db, test_org):
    role = Role(organization_id=test_org.id, name="Admins", code=f"r{uuid4().hex[:6]}")
    db.add(role); db.flush()
    for code in ("foundation:users:read", "foundation:users:lock", "foundation:users:reset_password", "foundation:users:write"):
        found = db.query(Permission).filter_by(organization_id=test_org.id, code=code).first()
        if found is None:
            module, resource, action = code.split(":")
            found = Permission(organization_id=test_org.id, code=code, name=code, description=code, module_name=module, resource_name=resource, action_name=action)
            db.add(found); db.flush()
        db.add(RolePermission(role_id=role.id, permission_id=found.id, scope="organization"))
    person = User(organization_id=test_org.id, full_name="Org Admin", email="admin@example.com", password_hash=hash_password("Admin12345!"),
                  status=UserStatus.ACTIVE)
    db.add(person); db.flush()
    db.add(UserRole(user_id=person.id, role_id=role.id)); db.commit()
    return person


def test_a_sign_in_renews_itself_and_signing_out_stops_its_token_at_once(client, test_user):
    headers = sign_in(client)
    renewed = client.post("/api/v1/auth/refresh")
    assert renewed.status_code == 200, renewed.text  # the refresh cookie works and rotates
    headers = {**headers, "Authorization": f"Bearer {renewed.json()['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 204
    ended = client.get("/api/v1/auth/me", headers=headers)
    assert ended.status_code == 401 and ended.json()["detail"]["code"] == "SESSION_ENDED"


def test_a_sign_in_lasts_at_most_its_absolute_lifetime(client, db, test_user):
    sign_in(client)
    db.execute(update(AuthSession).values(started_at=utc_now() - timedelta(hours=13)))
    db.commit()
    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 401 and r.json()["code"] == "SESSION_MAX_AGE"


def test_the_session_limit_ends_the_oldest_and_a_new_device_is_notified(client, db, test_user):
    first = sign_in(client, agent=CHROME)
    second = sign_in(client, agent=PHONE)
    third = sign_in(client, agent=FIREFOX)
    assert client.get("/api/v1/auth/me", headers=first).status_code == 401  # the oldest of three, over the limit of two
    for headers in (second, third):
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    mine = client.get("/api/v1/auth/sessions", headers=third).json()
    assert [(s["device"], s["current"]) for s in mine] == [("Firefox · Windows", True), ("Chrome · Android", False)]
    events = [n.event for n in db.scalars(select(NotificationItem).where(NotificationItem.recipient_user_id == test_user.id))]
    assert events.count("foundation.user.new_device") == 2 and "foundation.user.session_limit" in events


def test_i_end_my_other_sessions_but_not_this_one(client, test_user):
    phone = sign_in(client, agent=PHONE)
    here = sign_in(client, agent=CHROME)
    assert client.post("/api/v1/auth/sessions/end", json={"all_others": True}, headers=here).json() == {"ended": 1}
    assert client.get("/api/v1/auth/me", headers=phone).status_code == 401
    assert client.get("/api/v1/auth/me", headers=here).status_code == 200


def test_an_administrator_signs_a_user_out_everywhere_without_their_password(client, db, test_user, admin):
    user_headers = sign_in(client)
    admin_headers = sign_in(client, "admin@example.com", "Admin12345!")
    assert len(client.get(f"/api/v1/admin/users/{test_user.id}/sessions", headers=admin_headers).json()) == 1
    assert client.post(f"/api/v1/admin/users/{test_user.id}/sessions/end", headers=admin_headers).json() == {"ended": 1}
    assert client.get("/api/v1/auth/me", headers=user_headers).status_code == 401
    assert "foundation.user.sessions_ended" in [n.event for n in db.scalars(select(NotificationItem).where(NotificationItem.recipient_user_id == test_user.id))]


def test_an_administrator_cannot_choose_a_users_password(client, db, test_user, admin, monkeypatch):
    sent = []
    monkeypatch.setattr("app.core.email.service.EmailService.send_email", lambda self, to, subject, html, text=None: sent.append(to) or True)
    admin_headers = sign_in(client, "admin@example.com", "Admin12345!")
    chosen = client.post(f"/api/v1/admin/users/{test_user.id}/reset-password", headers=admin_headers,
                         json={"new_password": "Chosen12345!", "new_password_confirmation": "Chosen12345!"})
    assert chosen.json()["method"] == "link" and sent == ["test@example.com"]  # a link to the user, never a chosen password
    assert client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "Chosen12345!"}).status_code == 401


def test_a_failed_reset_email_is_reported(client, test_user, admin, monkeypatch):
    monkeypatch.setattr("app.core.email.service.EmailService.send_email", lambda *args, **kwargs: False)
    admin_headers = sign_in(client, "admin@example.com", "Admin12345!")
    r = client.post(f"/api/v1/admin/users/{test_user.id}/reset-password", headers=admin_headers, json={"method": "link"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "RESET_EMAIL_NOT_SENT"


def test_the_reset_link_is_the_only_way_and_the_user_chooses_their_own_password(client, db, test_user, admin, monkeypatch):
    import re as regex
    tokens = {}
    monkeypatch.setattr("app.core.email.service.EmailService.send_email",
                        lambda self, to, subject, html, text=None: tokens.update({to: regex.search(r"token=([A-Za-z0-9_\-]+)", text or html).group(1)}) or True)
    admin_headers = sign_in(client, "admin@example.com", "Admin12345!")
    user_headers = sign_in(client)
    assert client.post(f"/api/v1/admin/users/{test_user.id}/reset-password", headers=admin_headers, json={"method": "temporary"}).json()["method"] == "link"
    assert client.get("/api/v1/auth/me", headers=user_headers).status_code == 200  # nothing changes until the user acts
    done = client.post("/api/v1/auth/reset-password", json={"token": tokens["test@example.com"], "new_password": "MyOwnPassword12!",
                                                             "new_password_confirmation": "MyOwnPassword12!"})
    assert done.status_code in (200, 204), done.text
    assert client.get("/api/v1/auth/me", headers=user_headers).status_code == 401  # their sessions ended
    assert client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "MyOwnPassword12!"}).status_code == 200


def test_an_administrator_cannot_change_a_users_email(client, test_user, admin, monkeypatch):
    """ADR-010: personal details belong to the account owner (email changes are verified from both mailboxes there)."""
    sent = []
    monkeypatch.setattr("app.core.email.service.EmailService.send_email", lambda self, to, subject, html, text=None: sent.append(to) or True)
    admin_headers = sign_in(client, "admin@example.com", "Admin12345!")
    r = client.patch(f"/api/v1/admin/users/{test_user.id}", headers=admin_headers, json={"email": "new-address@example.com"})
    assert r.status_code == 400 and sent == []
    assert client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "Test1234!"}).status_code == 200
