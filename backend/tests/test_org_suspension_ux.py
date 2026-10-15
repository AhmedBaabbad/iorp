import pytest

from app.core.config import settings
from app.foundation.domain.enums import OrganizationStatus
from app.foundation.infrastructure.models import Organization, User


TENANT_PASSWORD = "TenantRoot123!"
PLATFORM_PASSWORD = "PlatformRoot123!"


@pytest.fixture
def suspension_env(client, db, monkeypatch):
    monkeypatch.setattr(settings, "bootstrap_token", "suspension-ux-token")
    response = client.post("/api/v1/system/bootstrap/initialize", json={
        "bootstrap_token": "suspension-ux-token",
        "platform_root": {"full_name": "Platform Root", "email": "platform@example.com", "password": PLATFORM_PASSWORD, "password_confirmation": PLATFORM_PASSWORD},
        "organization": {"name": "Suspension UX Org", "code": "suspension-ux", "timezone": "UTC", "default_locale": "en"},
        "organization_admin": {"full_name": "Tenant Root", "email": "tenant@example.com", "password": TENANT_PASSWORD, "password_confirmation": TENANT_PASSWORD},
    })
    assert response.status_code == 201
    platform_login = client.post("/api/v1/platform/login", json={"email": "platform@example.com", "password": PLATFORM_PASSWORD})
    organization = db.query(Organization).filter_by(code="SUSPENSION-UX").one()
    user = db.query(User).filter_by(email="tenant@example.com").one()
    return {
        "client": client,
        "db": db,
        "organization": organization,
        "user": user,
        "platform_headers": {"Authorization": f"Bearer {platform_login.json()['access_token']}"},
    }


def login(env, password=TENANT_PASSWORD, email="tenant@example.com"):
    return env["client"].post("/api/v1/auth/login", json={"email": email, "password": password})


def set_status(env, status):
    env["organization"].status = OrganizationStatus(status)
    env["db"].commit()


def tenant_headers(env):
    response = login(env)
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def assert_status_error(response, code):
    assert response.status_code == 403
    assert response.json() == {"code": code, "message": response.json()["message"]}
    assert isinstance(response.json()["message"], str)


@pytest.mark.parametrize("case", [f"T{number:02}" for number in range(1, 19)])
def test_organization_suspension_contract(suspension_env, case):
    env = suspension_env
    if case in {"T01", "T02", "T03", "T14"}:
        status, code = {
            "T01": ("suspended", "ORGANIZATION_SUSPENDED"),
            "T02": ("inactive", "ORGANIZATION_INACTIVE"),
            "T03": ("archived", "ORGANIZATION_ARCHIVED"),
            "T14": ("suspended", "ORGANIZATION_SUSPENDED"),
        }[case]
        set_status(env, status)
        assert_status_error(login(env), code)
    elif case == "T04":
        assert login(env).status_code == 200
    elif case == "T05":
        for status in ("suspended", "inactive", "archived"):
            set_status(env, status)
            body = login(env).json()
            assert set(body) == {"code", "message"}
    elif case == "T06":
        assert env["client"].get("/api/v1/auth/me", headers=tenant_headers(env)).status_code == 200
    elif case in {"T07", "T08", "T09", "T15"}:
        headers = tenant_headers(env)
        status, code = {
            "T07": ("suspended", "ORGANIZATION_SUSPENDED"),
            "T08": ("inactive", "ORGANIZATION_INACTIVE"),
            "T09": ("archived", "ORGANIZATION_ARCHIVED"),
            "T15": ("suspended", "ORGANIZATION_SUSPENDED"),
        }[case]
        set_status(env, status)
        assert_status_error(env["client"].get("/api/v1/auth/me", headers=headers), code)
    elif case == "T10":
        headers = tenant_headers(env)
        set_status(env, "suspended")
        assert set(login(env).json()) == set(env["client"].get("/api/v1/auth/me", headers=headers).json()) == {"code", "message"}
    elif case in {"T11", "T12"}:
        set_status(env, "suspended" if case == "T11" else "inactive")
        assert login(env).status_code == 403
        set_status(env, "active")
        assert login(env).status_code == 200
    elif case == "T13":
        original_name = env["organization"].name
        set_status(env, "suspended")
        set_status(env, "active")
        assert env["db"].get(Organization, env["organization"].id).name == original_name
        assert env["db"].get(User, env["user"].id) is not None
    elif case == "T16":
        set_status(env, "suspended")
        assert_status_error(login(env, password="WrongPassword123!"), "ORGANIZATION_SUSPENDED")
    elif case == "T17":
        set_status(env, "suspended")
        assert login(env, email="missing@example.com").status_code == 401
    elif case == "T18":
        set_status(env, "suspended")
        response = env["client"].get(f"/api/v1/platform/organizations/{env['organization'].id}", headers=env["platform_headers"])
        assert response.status_code == 200


# Exercise the same fresh-verification handshake as the Platform UI.
from tests.platform_stepup_client import verified_platform_browser  # noqa: F401
import pytest
pytestmark = pytest.mark.usefixtures("verified_platform_browser")
