"""Contract coverage for the platform dashboard's client-side data sources."""

import pytest

from app.core.config import settings


PLATFORM_PASSWORD = "PlatformDash123!"
TENANT_PASSWORD = "TenantDash123!"


@pytest.fixture
def dashboard_env(client, db, monkeypatch, activate):
    monkeypatch.setattr(settings, "bootstrap_token", "dash-token")
    initialized = client.post("/api/v1/system/bootstrap/initialize", json={
        "bootstrap_token": "dash-token",
        "platform_root": {"full_name": "Dash Root", "email": "dash-platform@example.com", "password": PLATFORM_PASSWORD, "password_confirmation": PLATFORM_PASSWORD},
        "organization": {"name": "Dash Base", "code": "dash-base", "industry_type": "manufacturing", "timezone": "Asia/Riyadh", "default_locale": "ar"},
        "organization_admin": {"full_name": "Dash Tenant Root", "email": "dash-tenant@example.com", "password": TENANT_PASSWORD, "password_confirmation": TENANT_PASSWORD},
    })
    assert initialized.status_code == 201
    root_login = client.post("/api/v1/platform/login", json={"email": "dash-platform@example.com", "password": PLATFORM_PASSWORD})
    tenant_login = client.post("/api/v1/auth/login", json={"email": "dash-tenant@example.com", "password": TENANT_PASSWORD})
    root = {"Authorization": f"Bearer {root_login.json()['access_token']}"}
    tenant = {"Authorization": f"Bearer {tenant_login.json()['access_token']}"}
    admin_created = client.post("/api/v1/platform/administrators", headers=root, json={
        "full_name": "Dash Admin", "email": "dash-admin@example.com", "role": "admin",
        "password": "DashAdmin123!", "password_confirmation": "DashAdmin123!",
    })
    assert admin_created.status_code == 201
    activate("dash-admin@example.com", "DashAdmin123!", platform=True)  # SEC-003: the owner chooses the password
    admin_login = client.post("/api/v1/platform/login", json={"email": "dash-admin@example.com", "password": "DashAdmin123!"})
    admin = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    return {"client": client, "root": root, "admin": admin, "tenant": tenant}


def test_t01_organizations_list_returns_200(dashboard_env):
    response = dashboard_env["client"].get("/api/v1/platform/organizations", headers=dashboard_env["root"])
    assert response.status_code == 200 and isinstance(response.json(), list)


def test_t02_organizations_include_status_for_counting(dashboard_env):
    items = dashboard_env["client"].get("/api/v1/platform/organizations", headers=dashboard_env["root"]).json()
    assert all("status" in item for item in items)


def test_t03_organizations_include_created_at_for_sorting(dashboard_env):
    items = dashboard_env["client"].get("/api/v1/platform/organizations", headers=dashboard_env["root"]).json()
    assert all(item["created_at"] for item in items)


def test_t04_administrators_list_returns_200(dashboard_env):
    response = dashboard_env["client"].get("/api/v1/platform/administrators", headers=dashboard_env["root"])
    assert response.status_code == 200 and isinstance(response.json(), list)


def test_t05_administrators_include_role_and_status(dashboard_env):
    items = dashboard_env["client"].get("/api/v1/platform/administrators", headers=dashboard_env["root"]).json()
    assert all({"role", "status", "full_name"} <= item.keys() for item in items)


def test_t06_admin_token_can_read_organizations(dashboard_env):
    response = dashboard_env["client"].get("/api/v1/platform/organizations", headers=dashboard_env["admin"])
    assert response.status_code == 200


def test_t07_admin_token_can_read_administrators(dashboard_env):
    response = dashboard_env["client"].get("/api/v1/platform/administrators", headers=dashboard_env["admin"])
    assert response.status_code == 200


def test_t08_tenant_token_cannot_read_organizations(dashboard_env):
    response = dashboard_env["client"].get("/api/v1/platform/organizations", headers=dashboard_env["tenant"])
    assert response.status_code == 401


def test_t09_tenant_token_cannot_read_administrators(dashboard_env):
    response = dashboard_env["client"].get("/api/v1/platform/administrators", headers=dashboard_env["tenant"])
    assert response.status_code == 401


def test_t10_both_endpoints_provide_dashboard_computation_fields(dashboard_env):
    orgs = dashboard_env["client"].get("/api/v1/platform/organizations", headers=dashboard_env["root"]).json()
    admins = dashboard_env["client"].get("/api/v1/platform/administrators", headers=dashboard_env["root"]).json()
    assert all({"status", "created_at"} <= item.keys() for item in orgs)
    assert all({"role", "full_name", "status"} <= item.keys() for item in admins)
