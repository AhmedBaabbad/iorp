import re
"""Contract coverage for the platform organization detail and health view."""

from uuid import uuid4

import pytest

from app.core.config import settings
from app.foundation.infrastructure.models import Organization


PLATFORM_PASSWORD = "PlatformDetail123!"
TENANT_PASSWORD = "TenantDetail123!"
NEW_PASSWORD = "TenantDetail456!"
PIXEL_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="



def _mailbox(monkeypatch):
    """SEC-002: the reset e-mails sent, as {address: reset token}."""
    box = {}

    def send(self, to, subject, html, text=None):
        found = re.search(r"token=([A-Za-z0-9_\-]+)", text or html)
        box[to] = found.group(1) if found else None
        return True
    monkeypatch.setattr("app.core.email.service.EmailService.send_email", send)
    return box

@pytest.fixture
def detail_env(client, db, monkeypatch, activate):
    monkeypatch.setattr(settings, "bootstrap_token", "detail-token")
    initialized = client.post("/api/v1/system/bootstrap/initialize", json={
        "bootstrap_token": "detail-token",
        "platform_root": {"full_name": "Detail Root", "email": "detail-platform@example.com", "password": PLATFORM_PASSWORD, "password_confirmation": PLATFORM_PASSWORD},
        "organization": {"name": "Detail Base", "code": "detail-base", "industry_type": "manufacturing", "timezone": "Asia/Riyadh", "default_locale": "ar"},
        "organization_admin": {"full_name": "Detail Tenant Root", "email": "detail-tenant@example.com", "password": TENANT_PASSWORD, "password_confirmation": TENANT_PASSWORD},
    })
    assert initialized.status_code == 201
    root_login = client.post("/api/v1/platform/login", json={"email": "detail-platform@example.com", "password": PLATFORM_PASSWORD})
    tenant_login = client.post("/api/v1/auth/login", json={"email": "detail-tenant@example.com", "password": TENANT_PASSWORD})
    root = {"Authorization": f"Bearer {root_login.json()['access_token']}"}
    tenant = {"Authorization": f"Bearer {tenant_login.json()['access_token']}"}
    admin_created = client.post("/api/v1/platform/administrators", headers=root, json={
        "full_name": "Detail Admin", "email": "detail-admin@example.com", "role": "admin",
        "password": "DetailAdmin123!", "password_confirmation": "DetailAdmin123!",
    })
    assert admin_created.status_code == 201
    activate("detail-admin@example.com", "DetailAdmin123!", platform=True)  # SEC-003: the owner chooses the password
    admin_login = client.post("/api/v1/platform/login", json={"email": "detail-admin@example.com", "password": "DetailAdmin123!"})
    admin = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    organization = db.query(Organization).filter_by(code="DETAIL-BASE").one()
    return {"client": client, "root": root, "admin": admin, "tenant": tenant, "organization": organization}


def _detail(env, headers=None, organization_id=None):
    target = organization_id or env["organization"].id
    return env["client"].get(f"/api/v1/platform/organizations/{target}", headers=headers or env["root"])


def test_t01_detail_returns_200_and_object(detail_env):
    response = _detail(detail_env)
    assert response.status_code == 200 and isinstance(response.json(), dict)


def test_t02_detail_includes_identity_and_profile_fields(detail_env):
    assert {"name", "code", "status", "industry_type", "timezone", "default_locale"} <= _detail(detail_env).json().keys()


def test_t03_detail_includes_created_and_updated_timestamps(detail_env):
    payload = _detail(detail_env).json()
    assert payload["created_at"] and payload["updated_at"]


def test_t04_detail_includes_logo_contract(detail_env):
    payload = _detail(detail_env).json()
    assert "has_logo" in payload and "logo_url" in payload


def test_t05_detail_includes_root_user_shape(detail_env):
    root = _detail(detail_env).json()["root_user"]
    assert {"full_name", "email", "status", "last_login_at"} <= root.keys()


def test_t06_detail_includes_lifecycle_metadata(detail_env):
    assert {"status_changed_at", "status_changed_by", "status_change_reason"} <= _detail(detail_env).json().keys()


def test_t07_detail_includes_allowed_transitions(detail_env):
    assert isinstance(_detail(detail_env).json()["allowed_transitions"], list)


def test_t08_nonexistent_organization_returns_404(detail_env):
    assert _detail(detail_env, organization_id=uuid4()).status_code == 404


def test_t09_tenant_token_cannot_read_platform_detail(detail_env):
    assert _detail(detail_env, detail_env["tenant"]).status_code == 401


def test_t10_platform_admin_can_read_detail(detail_env):
    assert _detail(detail_env, detail_env["admin"]).status_code == 200


def test_t11_logo_endpoint_returns_image(detail_env):
    created = detail_env["client"].post("/api/v1/platform/organizations", headers=detail_env["root"], json={
        "organization": {"name": "Logo Org", "code": "logo-org", "timezone": "Asia/Riyadh", "default_locale": "en", "logo_base64": PIXEL_PNG},
        "organization_admin": {"full_name": "Logo Root", "email": "logo-root@example.com", "password": "LogoTenant123!", "password_confirmation": "LogoTenant123!"},
    })
    assert created.status_code == 201
    response = detail_env["client"].get(f"/api/v1/platform/organizations/{created.json()['organization']['id']}/logo", headers=detail_env["root"])
    assert response.status_code == 200 and response.headers["content-type"].startswith("image/")


def test_t12_logo_endpoint_returns_404_when_missing(detail_env):
    response = detail_env["client"].get(f"/api/v1/platform/organizations/{detail_env['organization'].id}/logo", headers=detail_env["root"])
    assert response.status_code == 404


def test_t13_root_can_send_the_organization_root_a_reset_link(detail_env, monkeypatch):
    box = _mailbox(monkeypatch)
    response = detail_env["client"].post(f"/api/v1/platform/organizations/{detail_env['organization'].id}/reset-root-password", headers=detail_env["root"], json={})
    assert response.status_code == 200 and response.json()["root_user_email"] in box  # SEC-002


@pytest.mark.xfail(reason="Backend currently grants ORGANIZATIONS_UPDATE to Platform Admin; UI-002 requires Root-only reset.", strict=True)
def test_t14_admin_cannot_reset_organization_root_password(detail_env):
    response = detail_env["client"].post(f"/api/v1/platform/organizations/{detail_env['organization'].id}/reset-root-password", headers=detail_env["admin"], json={"new_password": NEW_PASSWORD, "new_password_confirmation": NEW_PASSWORD})
    assert response.status_code == 403


def test_t15_the_organization_root_chooses_their_own_password_through_the_link(detail_env, monkeypatch):
    box = _mailbox(monkeypatch)
    client = detail_env["client"]
    reset = client.post(f"/api/v1/platform/organizations/{detail_env['organization'].id}/reset-root-password", headers=detail_env["root"],
                        json={"new_password": NEW_PASSWORD, "new_password_confirmation": NEW_PASSWORD})
    assert reset.status_code == 200
    assert client.post("/api/v1/auth/login", json={"email": "detail-tenant@example.com", "password": NEW_PASSWORD}).status_code == 401
    token = box["detail-tenant@example.com"]
    assert client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD, "new_password_confirmation": NEW_PASSWORD}).status_code in (200, 204)
    login = client.post("/api/v1/auth/login", json={"email": "detail-tenant@example.com", "password": NEW_PASSWORD})
    assert login.status_code == 200 and login.json()["access_token"]
