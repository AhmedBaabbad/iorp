from app.core.config import settings
from app.foundation.infrastructure.models import Organization, Permission, Role, User
from app.foundation.domain.system_roles import SYSTEM_ROLES


def bootstrap_payload() -> dict:
    return {
        "bootstrap_token": "bootstrap-test-token",
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
            "full_name": "First Org Admin",
            "email": "first-admin@example.com",
            "password": "AdminPassword123!",
            "password_confirmation": "AdminPassword123!",
        },
    }


def second_org_payload(code: str = "second-org") -> dict:
    return {
        "organization": {
            "name": "Second Organization",
            "code": code,
            "timezone": "Europe/London",
            "default_locale": "en",
        },
        "organization_admin": {
            "full_name": "Second Org Admin",
            "email": "second-admin@example.com",
            "password": "AdminPassword123!",
            "password_confirmation": "AdminPassword123!",
        },
    }


def bootstrap_and_get_platform_token(client, monkeypatch) -> str:
    monkeypatch.setattr(settings, "bootstrap_token", "bootstrap-test-token")
    response = client.post("/api/v1/system/bootstrap/initialize", json=bootstrap_payload())
    assert response.status_code == 201
    login = client.post(
        "/api/v1/platform/login",
        json={"email": "root@example.com", "password": "RootPassword123!"},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def test_list_organizations_requires_platform_auth(client, monkeypatch):
    bootstrap_and_get_platform_token(client, monkeypatch)
    assert client.get("/api/v1/platform/organizations").status_code == 401


def test_list_organizations_returns_bootstrap_org_with_summary(client, monkeypatch):
    token = bootstrap_and_get_platform_token(client, monkeypatch)
    response = client.get(
        "/api/v1/platform/organizations", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    orgs = response.json()
    assert len(orgs) == 1
    assert orgs[0]["code"] == "FIRST-ORG"
    assert orgs[0]["status"] == "active"
    assert orgs[0]["user_count"] == 1
    assert orgs[0]["admin_email"] == "first-admin@example.com"


def test_create_second_organization(client, db, monkeypatch):
    token = bootstrap_and_get_platform_token(client, monkeypatch)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post("/api/v1/platform/organizations", json=second_org_payload(), headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["organization"]["code"] == "SECOND-ORG"
    assert body["organization_admin_email"] == "second-admin@example.com"
    assert body["roles_created"] == [str(role["code"]) for role in SYSTEM_ROLES]

    assert db.query(Organization).count() == 2
    assert db.query(User).count() == 2
    # Roles are per-organization; permissions are a single shared catalog, not duplicated.
    assert db.query(Role).count() == len(SYSTEM_ROLES) * 2
    permission_count = db.query(Permission).count()
    assert permission_count > 0

    list_response = client.get("/api/v1/platform/organizations", headers=headers)
    codes = {org["code"] for org in list_response.json()}
    assert codes == {"FIRST-ORG", "SECOND-ORG"}

    # Re-creating with the same code is rejected, and permissions are still not duplicated.
    duplicate = client.post("/api/v1/platform/organizations", json=second_org_payload(), headers=headers)
    assert duplicate.status_code == 409
    assert db.query(Permission).count() == permission_count


def test_get_single_organization(client, monkeypatch):
    token = bootstrap_and_get_platform_token(client, monkeypatch)
    headers = {"Authorization": f"Bearer {token}"}
    org_id = client.get("/api/v1/platform/organizations", headers=headers).json()[0]["id"]

    found = client.get(f"/api/v1/platform/organizations/{org_id}", headers=headers)
    assert found.status_code == 200
    assert found.json()["code"] == "FIRST-ORG"

    missing = client.get(
        "/api/v1/platform/organizations/00000000-0000-0000-0000-000000000000", headers=headers
    )
    assert missing.status_code == 404


def test_suspend_organization_blocks_login_and_active_sessions(client, monkeypatch):
    token = bootstrap_and_get_platform_token(client, monkeypatch)
    headers = {"Authorization": f"Bearer {token}"}
    org_id = client.get("/api/v1/platform/organizations", headers=headers).json()[0]["id"]

    tenant_login = client.post(
        "/api/v1/auth/login", json={"email": "first-admin@example.com", "password": "AdminPassword123!"}
    )
    assert tenant_login.status_code == 200
    tenant_token = tenant_login.json()["access_token"]
    tenant_headers = {"Authorization": f"Bearer {tenant_token}"}
    assert client.get("/api/v1/auth/me", headers=tenant_headers).status_code == 200

    suspend = client.post(
        f"/api/v1/platform/organizations/{org_id}/suspend", json={"reason": "Policy review"}, headers=headers
    )
    assert suspend.status_code == 200
    assert suspend.json()["status"] == "suspended"
    assert suspend.json()["status_change_reason"] == "Policy review"
    assert suspend.json()["status_changed_by"] is not None

    # An already-issued token must stop working immediately, not just new logins.
    assert client.get("/api/v1/auth/me", headers=tenant_headers).status_code == 403
    blocked_login = client.post(
        "/api/v1/auth/login", json={"email": "first-admin@example.com", "password": "AdminPassword123!"}
    )
    assert blocked_login.status_code == 403
    assert blocked_login.json()["code"] == "ORGANIZATION_SUSPENDED"

    reactivate = client.post(
        f"/api/v1/platform/organizations/{org_id}/activate", json={}, headers=headers
    )
    assert reactivate.status_code == 200
    restored_login = client.post(
        "/api/v1/auth/login", json={"email": "first-admin@example.com", "password": "AdminPassword123!"}
    )
    assert restored_login.status_code == 200
