"""Frontend contract tests for the platform organizations console."""

import pytest

from app.core.config import settings
from app.foundation.domain.enums import OrganizationStatus
from app.foundation.infrastructure.models import Organization


ROOT_PASSWORD = "PlatformRoot123!"


@pytest.fixture
def console(client, db, monkeypatch, activate):
    monkeypatch.setattr(settings, "bootstrap_token", "console-token")
    initialized = client.post("/api/v1/system/bootstrap/initialize", json={
        "bootstrap_token": "console-token",
        "platform_root": {"full_name": "Console Root", "email": "console-root@example.com", "password": ROOT_PASSWORD, "password_confirmation": ROOT_PASSWORD},
        "organization": {"name": "Console Base", "code": "console-base", "industry_type": "manufacturing", "timezone": "Asia/Riyadh", "default_locale": "ar"},
        "organization_admin": {"full_name": "Base Root", "email": "base-root@example.com", "password": "TenantRoot123!", "password_confirmation": "TenantRoot123!"},
    })
    assert initialized.status_code == 201
    root_login = client.post("/api/v1/platform/login", json={"email": "console-root@example.com", "password": ROOT_PASSWORD})
    tenant_login = client.post("/api/v1/auth/login", json={"email": "base-root@example.com", "password": "TenantRoot123!"})
    root = {"Authorization": f"Bearer {root_login.json()['access_token']}"}
    tenant = {"Authorization": f"Bearer {tenant_login.json()['access_token']}"}
    admin_created = client.post("/api/v1/platform/administrators", headers=root, json={
        "full_name": "Read Admin", "email": "console-admin@example.com", "role": "admin",
        "password": "ConsoleAdmin123!", "password_confirmation": "ConsoleAdmin123!",
    })
    assert admin_created.status_code == 201
    activate("console-admin@example.com", "ConsoleAdmin123!", platform=True)  # SEC-003: the owner chooses the password
    admin_login = client.post("/api/v1/platform/login", json={"email": "console-admin@example.com", "password": "ConsoleAdmin123!"})
    admin = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    organization = db.query(Organization).filter_by(code="CONSOLE-BASE").one()
    return {"client": client, "db": db, "root": root, "admin": admin, "tenant": tenant, "organization": organization}


def _payload(code="console-new", email="console-new-root@example.com"):
    return {
        "organization": {"name": "Console New", "code": code, "industry_type": "industrial", "timezone": "Asia/Riyadh", "default_locale": "ar"},
        "organization_admin": {"full_name": "New Root", "email": email, "phone": "+966500000000", "password": "ConsoleTenant123!", "password_confirmation": "ConsoleTenant123!"},
    }


def _list(env, headers=None):
    return env["client"].get("/api/v1/platform/organizations", headers=headers or env["root"])


def test_t01_list_returns_200_and_array(console):
    response = _list(console)
    assert response.status_code == 200 and isinstance(response.json(), list)


def test_t02_list_items_have_console_identity_fields(console):
    assert {"id", "name", "code", "status", "has_logo"} <= _list(console).json()[0].keys()


def test_t03_list_items_have_allowed_transitions(console):
    assert isinstance(_list(console).json()[0]["allowed_transitions"], list)


def test_t04_list_items_have_created_at(console):
    assert _list(console).json()[0]["created_at"]


def test_t05_status_values_match_console_contract(console):
    assert all(item["status"] in {"provisioning", "active", "suspended", "inactive", "archived"} for item in _list(console).json())


def test_t06_create_returns_all_frontend_fields(console):
    response = console["client"].post("/api/v1/platform/organizations", headers=console["root"], json=_payload())
    assert response.status_code == 201
    assert {"id", "name", "code", "status", "default_locale", "timezone", "has_logo", "created_at"} <= response.json()["organization"].keys()


def test_t07_duplicate_code_returns_clear_409(console):
    assert console["client"].post("/api/v1/platform/organizations", headers=console["root"], json=_payload("console-base", "unique@example.com")).json()["code"] == "ORG_CODE_EXISTS"


def test_t08_duplicate_email_returns_clear_409(console):
    response = console["client"].post("/api/v1/platform/organizations", headers=console["root"], json=_payload("unique-code", "base-root@example.com"))
    assert response.status_code == 409 and response.json()["code"] == "EMAIL_ALREADY_EXISTS"


def test_t09_suspend_returns_updated_status(console):
    response = console["client"].post(f"/api/v1/platform/organizations/{console['organization'].id}/suspend", headers=console["root"], json={"reason": "Review"})
    assert response.status_code == 200 and response.json()["status"] == "suspended"


def test_t10_activate_returns_updated_status(console):
    console["organization"].status = OrganizationStatus.SUSPENDED; console["db"].commit()
    response = console["client"].post(f"/api/v1/platform/organizations/{console['organization'].id}/activate", headers=console["root"], json={"reason": "Ready"})
    assert response.status_code == 200 and response.json()["status"] == "active"


def test_t11_archive_without_reason_returns_400(console):
    console["organization"].status = OrganizationStatus.INACTIVE; console["db"].commit()
    response = console["client"].post(f"/api/v1/platform/organizations/{console['organization'].id}/archive", headers=console["root"], json={"reason": ""})
    assert response.status_code == 400 and response.json()["code"] == "ARCHIVE_REASON_REQUIRED"


def test_t12_archive_with_reason_returns_200(console):
    console["organization"].status = OrganizationStatus.INACTIVE; console["db"].commit()
    response = console["client"].post(f"/api/v1/platform/organizations/{console['organization'].id}/archive", headers=console["root"], json={"reason": "Contract ended"})
    assert response.status_code == 200 and response.json()["status"] == "archived"


def test_t13_admin_can_list_organizations(console):
    assert _list(console, console["admin"]).status_code == 200


def test_t14_admin_cannot_suspend(console):
    response = console["client"].post(f"/api/v1/platform/organizations/{console['organization'].id}/suspend", headers=console["admin"], json={"reason": "Denied"})
    assert response.status_code == 403


def test_t15_admin_cannot_create(console):
    assert console["client"].post("/api/v1/platform/organizations", headers=console["admin"], json=_payload()).status_code == 403


def test_t16_tenant_token_cannot_access_platform_organizations(console):
    assert _list(console, console["tenant"]).status_code == 401


# Exercise the same fresh-verification handshake as the Platform UI.
from tests.platform_stepup_client import verified_platform_browser  # noqa: F401
import pytest
pytestmark = pytest.mark.usefixtures("verified_platform_browser")
