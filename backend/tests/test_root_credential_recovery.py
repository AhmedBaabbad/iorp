import re
from app.core.config import settings
from app.core.security import decode_access_token, verify_password
from app.foundation.infrastructure.models import User



def _mailbox(monkeypatch):
    """SEC-002: the reset e-mails sent, as {address: reset token}."""
    box = {}

    def send(self, to, subject, html, text=None):
        found = re.search(r"token=([A-Za-z0-9_\-]+)", text or html)
        box[to] = found.group(1) if found else None
        return True
    monkeypatch.setattr("app.core.email.service.EmailService.send_email", send)
    return box

def _payload():
    return {
        "bootstrap_token": "credential-test-token",
        "platform_root": {
            "full_name": "Platform Root",
            "email": "platform@example.com",
            "password": "PlatformRoot123!",
            "password_confirmation": "PlatformRoot123!",
        },
        "organization": {
            "name": "Credential Org",
            "code": "credential-org",
            "timezone": "Asia/Riyadh",
            "default_locale": "ar",
        },
        "organization_admin": {
            "full_name": "Organization Root",
            "email": "root@example.com",
            "password": "OrganizationRoot123!",
            "password_confirmation": "OrganizationRoot123!",
        },
    }


def _setup(client, monkeypatch):
    monkeypatch.setattr(settings, "bootstrap_token", "credential-test-token")
    created = client.post("/api/v1/system/bootstrap/initialize", json=_payload())
    assert created.status_code == 201
    tenant = client.post(
        "/api/v1/auth/login",
        json={"email": "root@example.com", "password": "OrganizationRoot123!"},
    ).json()["access_token"]
    platform = client.post(
        "/api/v1/platform/login",
        json={"email": "platform@example.com", "password": "PlatformRoot123!"},
    ).json()["access_token"]
    return tenant, platform


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_t01_t06_token_version_lifecycle(client, db, monkeypatch):
    old_token, _ = _setup(client, monkeypatch)
    assert decode_access_token(old_token)["token_version"] == 0
    changed = client.post(
        "/api/v1/auth/change-password",
        headers=_headers(old_token),
        json={
            "current_password": "OrganizationRoot123!",
            "new_password": "NewOrganizationRoot123!",
            "new_password_confirmation": "NewOrganizationRoot123!",
        },
    )
    assert changed.status_code == 200
    assert db.query(User).filter_by(email="root@example.com").one().token_version == 1
    assert client.get("/api/v1/auth/me", headers=_headers(old_token)).status_code == 401
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "root@example.com", "password": "NewOrganizationRoot123!"},
    )
    assert login.status_code == 200
    assert decode_access_token(login.json()["access_token"])["token_version"] == 1


def test_t07_t16_self_service_policy_and_authentication(client, db, monkeypatch):
    token, _ = _setup(client, monkeypatch)
    endpoint = "/api/v1/auth/change-password"
    assert client.post(endpoint, headers=_headers(token), json={
        "current_password": "wrong", "new_password": "NewOrganizationRoot123!",
        "new_password_confirmation": "NewOrganizationRoot123!",
    }).status_code == 400
    assert client.post(endpoint, headers=_headers(token), json={
        "current_password": "OrganizationRoot123!", "new_password": "short",
        "new_password_confirmation": "short",
    }).status_code == 400
    assert client.post(endpoint, headers=_headers(token), json={
        "current_password": "OrganizationRoot123!", "new_password": "root@example.com",
        "new_password_confirmation": "root@example.com",
    }).status_code == 400
    assert client.post(endpoint, headers=_headers(token), json={
        "current_password": "OrganizationRoot123!", "new_password": "NewOrganizationRoot123!",
        "new_password_confirmation": "different-password",
    }).status_code == 400
    assert db.query(User).filter_by(email="root@example.com").one().token_version == 0


def test_t17_t25_platform_root_recovery(client, db, monkeypatch):
    tenant_token, platform_token = _setup(client, monkeypatch)
    root = db.query(User).filter_by(email="root@example.com").one()
    box = _mailbox(monkeypatch)
    response = client.post(
        f"/api/v1/platform/organizations/{root.organization_id}/reset-root-password",
        headers=_headers(platform_token),
        json={},
    )
    assert response.status_code == 200
    assert response.json()["root_user_email"] == "root@example.com"
    assert "password" not in response.json()
    # SEC-002: the platform never sets the password: the root receives a link and chooses their own
    assert client.get("/api/v1/auth/me", headers=_headers(tenant_token)).status_code == 200
    done = client.post("/api/v1/auth/reset-password", json={"token": box["root@example.com"], "new_password": "RecoveredRoot123!",
                                                             "new_password_confirmation": "RecoveredRoot123!"})
    assert done.status_code in (200, 204), done.text
    assert client.get("/api/v1/auth/me", headers=_headers(tenant_token)).status_code == 401
    assert client.post("/api/v1/auth/login", json={
        "email": "root@example.com", "password": "RecoveredRoot123!",
    }).status_code == 200
    db.refresh(root)
    assert verify_password("RecoveredRoot123!", root.password_hash)


def test_t19_t21_platform_recovery_rejects_invalid_authority(client, db, monkeypatch):
    tenant_token, platform_token = _setup(client, monkeypatch)
    root = db.query(User).filter_by(email="root@example.com").one()
    body = {"new_password": "RecoveredRoot123!", "new_password_confirmation": "RecoveredRoot123!"}
    assert client.post(
        "/api/v1/platform/organizations/00000000-0000-0000-0000-000000000000/reset-root-password",
        headers=_headers(platform_token), json=body,
    ).status_code == 404
    assert client.post(
        f"/api/v1/platform/organizations/{root.organization_id}/reset-root-password",
        headers=_headers(tenant_token), json=body,
    ).status_code == 401


def test_t32_t35_password_version_is_per_user_and_tenant_safe(client, db, monkeypatch):
    token, _ = _setup(client, monkeypatch)
    root = db.query(User).filter_by(email="root@example.com").one()
    original_org = root.organization_id
    client.post("/api/v1/auth/change-password", headers=_headers(token), json={
        "current_password": "OrganizationRoot123!", "new_password": "IsolatedRoot123!",
        "new_password_confirmation": "IsolatedRoot123!",
    })
    db.refresh(root)
    assert root.organization_id == original_org and root.token_version == 1
