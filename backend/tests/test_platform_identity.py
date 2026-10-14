import re
from app.core.config import settings
from app.core.security import decode_access_token
from app.foundation.infrastructure.models import User
from app.platform.domain.enums import PlatformAccountRole
from app.platform.domain.permissions import PlatformPermission, has_platform_permission
from app.platform.infrastructure.models import PlatformAccount



def _mailbox(monkeypatch):
    """SEC-002: the reset e-mails sent, as {address: reset token}."""
    box = {}

    def send(self, to, subject, html, text=None):
        found = re.search(r"token=([A-Za-z0-9_\-]+)", text or html)
        box[to] = found.group(1) if found else None
        return True
    monkeypatch.setattr("app.core.email.service.EmailService.send_email", send)
    return box

def _bootstrap(client, monkeypatch):
    monkeypatch.setattr(settings, "bootstrap_token", "identity-token")
    response = client.post("/api/v1/system/bootstrap/initialize", json={
        "bootstrap_token": "identity-token",
        "platform_root": {"full_name": "Origin Root", "email": "origin@example.com", "password": "OriginPlatform123!", "password_confirmation": "OriginPlatform123!"},
        "organization": {"name": "Identity Org", "code": "identity-org", "timezone": "UTC", "default_locale": "en"},
        "organization_admin": {"full_name": "Tenant Root", "email": "tenant@example.com", "password": "TenantRoot123!", "password_confirmation": "TenantRoot123!"},
    })
    assert response.status_code == 201
    login = client.post("/api/v1/platform/login", json={"email": "origin@example.com", "password": "OriginPlatform123!"})
    assert login.status_code == 200
    return login.json()["access_token"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create(client, token, email="admin@example.com", role="admin"):
    return client.post("/api/v1/platform/administrators", headers=_headers(token), json={
        "full_name": "Platform Admin", "email": email, "role": role,
        "password": "PlatformAdmin123!", "password_confirmation": "PlatformAdmin123!",
    })


def test_t01_t05_platform_permission_catalog():
    assert all(has_platform_permission(PlatformAccountRole.ROOT, item) for item in PlatformPermission)
    assert has_platform_permission(PlatformAccountRole.ADMIN, PlatformPermission.ORGANIZATIONS_READ)
    assert not has_platform_permission(PlatformAccountRole.ADMIN, PlatformPermission.ADMINISTRATORS_CREATE)
    assert all(item.value.startswith("platform:") for item in PlatformPermission)


def test_t06_t12_last_and_bootstrap_root_protection(client, db, monkeypatch):
    token = _bootstrap(client, monkeypatch)
    root = db.query(PlatformAccount).filter_by(email="origin@example.com").one()
    assert client.patch(f"/api/v1/platform/administrators/{root.id}", headers=_headers(token), json={"role": "admin"}).status_code == 409
    assert client.patch(f"/api/v1/platform/administrators/{root.id}", headers=_headers(token), json={"status": "inactive"}).status_code == 409
    assert client.delete(f"/api/v1/platform/administrators/{root.id}", headers=_headers(token)).status_code == 409
    assert _create(client, token, "root2@example.com", "root").status_code == 201
    assert client.patch(f"/api/v1/platform/administrators/{root.id}", headers=_headers(token), json={"role": "admin"}).status_code == 200


def test_t13_t18_root_creates_accounts_and_uniqueness(client, db, monkeypatch):
    token = _bootstrap(client, monkeypatch)
    created = _create(client, token)
    assert created.status_code == 201 and "password_hash" not in created.json()
    assert _create(client, token).status_code == 409
    assert _create(client, token, "tenant@example.com").status_code == 409
    assert _create(client, token, "root2@example.com", "root").status_code == 201
    assert db.query(User).filter_by(email="admin@example.com").count() == 0


def test_t16_t27_admin_login_authorization_and_reset(client, db, monkeypatch, activate):
    root_token = _bootstrap(client, monkeypatch)
    created = _create(client, root_token).json()
    assert created["activation_pending"] is True and created["invitation_sent"] is True  # SEC-003
    activate("admin@example.com", "PlatformAdmin123!", platform=True)
    login = client.post("/api/v1/platform/login", json={"email": "admin@example.com", "password": "PlatformAdmin123!"})
    assert login.status_code == 200
    admin_token = login.json()["access_token"]
    assert decode_access_token(admin_token)["role"] == "admin"
    assert client.get("/api/v1/platform/administrators", headers=_headers(admin_token)).status_code == 200
    assert _create(client, admin_token, "denied@example.com").status_code == 403
    assert client.patch(f"/api/v1/platform/administrators/{created['id']}", headers=_headers(admin_token), json={"full_name": "Denied"}).status_code == 403
    box = _mailbox(monkeypatch)
    reset = client.post(f"/api/v1/platform/administrators/{created['id']}/reset-password", headers=_headers(root_token),
                        json={"new_password": "ResetPlatform123!", "new_password_confirmation": "ResetPlatform123!"})
    assert reset.status_code == 200 and reset.json()["email"] == "admin@example.com"  # SEC-002: a link, not the chosen password
    assert client.post("/api/v1/platform/login", json={"email": "admin@example.com", "password": "ResetPlatform123!"}).status_code == 401
    done = client.post("/api/v1/platform/auth/reset-password", json={"token": box["admin@example.com"], "new_password": "MyOwnPlatform123!",
                                                                      "new_password_confirmation": "MyOwnPlatform123!"})
    assert done.status_code in (200, 204), done.text
    assert client.get("/api/v1/platform/me", headers=_headers(admin_token)).status_code == 401
    assert client.post("/api/v1/platform/login", json={"email": "admin@example.com", "password": "MyOwnPlatform123!"}).status_code == 200


def test_t28_t32_platform_jwt_isolation(client, monkeypatch):
    token = _bootstrap(client, monkeypatch)
    payload = decode_access_token(token)
    assert payload["role"] == "root" and payload["account_type"] == "platform"
    assert client.get("/api/v1/auth/me", headers=_headers(token)).status_code == 401


def test_t33_t36_self_service_invalidates_session(client, monkeypatch):
    token = _bootstrap(client, monkeypatch)
    response = client.post("/api/v1/platform/account/change-password", headers=_headers(token), json={
        "current_password": "OriginPlatform123!", "new_password": "ChangedPlatform123!",
        "password_confirmation": "ChangedPlatform123!",
    })
    assert response.status_code == 200
    assert client.get("/api/v1/platform/me", headers=_headers(token)).status_code == 401
    assert client.post("/api/v1/platform/login", json={"email": "origin@example.com", "password": "ChangedPlatform123!"}).status_code == 200


def test_t37_t40_platform_accounts_are_independent(client, db, monkeypatch):
    token = _bootstrap(client, monkeypatch)
    _create(client, token)
    assert db.query(PlatformAccount).count() == 2
    assert db.query(User).count() == 1
    assert not hasattr(db.query(PlatformAccount).first(), "organization_id")
