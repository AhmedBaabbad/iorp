from app.core.config import settings
from app.foundation.infrastructure.models import Organization, Permission, Role, User
from app.foundation.domain.system_roles import SYSTEM_ROLES
from app.platform.infrastructure.models import BootstrapState, PlatformAccount


def payload(token: str = "bootstrap-test-token") -> dict:
    return {
        "bootstrap_token": token,
        "platform_root": {
            "full_name": "Platform Owner",
            "email": "root@example.com",
            "password": "RootPassword123!",
            "password_confirmation": "RootPassword123!",
        },
        "organization": {
            "name": "First Organization",
            "code": "first-org",
            "timezone": "Asia/Riyadh",
            "default_locale": "ar",
        },
        "organization_admin": {
            "full_name": "Organization Admin",
            "email": "admin@example.com",
            "password": "AdminPassword123!",
            "password_confirmation": "AdminPassword123!",
        },
    }


def test_bootstrap_initializes_once(client, db, monkeypatch):
    monkeypatch.setattr(settings, "bootstrap_token", "bootstrap-test-token")
    assert client.get("/api/v1/system/bootstrap/status").json() == {"initialized": False}
    assert client.post("/api/v1/system/bootstrap/initialize", json=payload("wrong")).status_code == 403

    response = client.post("/api/v1/system/bootstrap/initialize", json=payload())
    assert response.status_code == 201
    assert "password" not in response.text
    assert "bootstrap-test-token" not in response.text
    assert db.query(PlatformAccount).count() == 1
    assert db.query(Organization).count() == 1
    assert db.query(User).count() == 1
    assert db.query(Role).count() == len(SYSTEM_ROLES)
    assert db.query(Permission).count() > 0
    root = db.query(PlatformAccount).one()
    admin = db.query(User).one()
    assert not hasattr(root, "organization_id")
    assert admin.organization_id == db.query(Organization).one().id
    assert db.get(BootstrapState, 1).is_initialized is True
    assert client.get("/api/v1/system/bootstrap/status").json() == {"initialized": True}
    duplicate = client.post("/api/v1/system/bootstrap/initialize", json=payload())
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "SYSTEM_ALREADY_INITIALIZED"


def test_bootstrap_validation(client):
    invalid = payload()
    invalid["organization"]["timezone"] = "Invalid/Timezone"
    assert client.post("/api/v1/system/bootstrap/initialize", json=invalid).status_code == 422

    mismatch = payload()
    mismatch["platform_root"]["password_confirmation"] = "different-password"
    assert client.post("/api/v1/system/bootstrap/initialize", json=mismatch).status_code == 422
