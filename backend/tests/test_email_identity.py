"""Global login email identity contract (T01-T32)."""

import pytest
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.security import hash_password, normalize_email
from app.foundation.api.schemas import LoginRequest, UserCreateRequest
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, User
from app.platform.api.schemas import PlatformAccountCreate, PlatformLoginRequest
from app.platform.infrastructure.models import PlatformAccount


TENANT_PASSWORD = "TenantRoot123!"
PLATFORM_PASSWORD = "OriginPlatform123!"


@pytest.fixture
def identity_env(client, db, monkeypatch):
    monkeypatch.setattr(settings, "bootstrap_token", "email-identity-token")
    response = client.post("/api/v1/system/bootstrap/initialize", json={
        "bootstrap_token": "email-identity-token",
        "platform_root": {"full_name": "Platform Root", "email": "  PLATFORM@Example.COM ", "password": PLATFORM_PASSWORD, "password_confirmation": PLATFORM_PASSWORD},
        "organization": {"name": "Email Org", "code": "email-org", "timezone": "UTC", "default_locale": "en"},
        "organization_admin": {"full_name": "Tenant Root", "email": "  TENANT@Example.COM ", "password": TENANT_PASSWORD, "password_confirmation": TENANT_PASSWORD},
    })
    assert response.status_code == 201, response.json()
    tenant_login = client.post("/api/v1/auth/login", json={"email": " TENANT@EXAMPLE.COM ", "password": TENANT_PASSWORD})
    platform_login = client.post("/api/v1/platform/login", json={"email": " PLATFORM@EXAMPLE.COM ", "password": PLATFORM_PASSWORD})
    assert tenant_login.status_code == platform_login.status_code == 200
    return {
        "client": client,
        "db": db,
        "tenant_headers": {"Authorization": f"Bearer {tenant_login.json()['access_token']}"},
        "platform_headers": {"Authorization": f"Bearer {platform_login.json()['access_token']}"},
    }


def test_t01_t04_normalization_contract():
    assert normalize_email("  User@Example.COM ") == "user@example.com"
    assert LoginRequest(email=" A@EXAMPLE.COM ", password="secret").email == "a@example.com"
    assert PlatformLoginRequest(email=" B@EXAMPLE.COM ", password="secret").email == "b@example.com"
    assert UserCreateRequest(full_name="Name", email=" C@EXAMPLE.COM ", password="Password123!").email == "c@example.com"


def test_t05_t10_storage_login_and_same_tenant_conflict(identity_env):
    env = identity_env
    assert env["db"].query(User).filter_by(email="tenant@example.com").one()
    assert env["db"].query(PlatformAccount).filter_by(email="platform@example.com").one()
    created = env["client"].post("/api/v1/admin/users", headers=env["tenant_headers"], json={
        "full_name": "First", "email": " First@Example.COM ", "password": "FirstUser123!", "role_codes": [],
    })
    assert created.status_code == 201 and created.json()["email"] == "first@example.com"
    duplicate = env["client"].post("/api/v1/admin/users", headers=env["tenant_headers"], json={
        "full_name": "Duplicate", "email": " FIRST@example.com ", "password": "Duplicate123!", "role_codes": [],
    })
    assert duplicate.status_code == 409 and duplicate.json()["code"] == "EMAIL_ALREADY_EXISTS"


def test_t11_t14_database_and_cross_table_conflicts(identity_env):
    env = identity_env
    other = Organization(name="Other", code="OTHER", status=OrganizationStatus.ACTIVE, timezone="UTC")
    env["db"].add(other); env["db"].flush()
    env["db"].add(User(organization_id=other.id, full_name="Duplicate", email="tenant@example.com", password_hash=hash_password("Duplicate123!"), status=UserStatus.ACTIVE))
    with pytest.raises(IntegrityError):
        env["db"].commit()
    env["db"].rollback()
    tenant_conflict = env["client"].post("/api/v1/admin/users", headers=env["tenant_headers"], json={
        "full_name": "Cross", "email": " PLATFORM@example.com ", "password": "CrossUser123!", "role_codes": [],
    })
    assert tenant_conflict.status_code == 409 and tenant_conflict.json()["code"] == "EMAIL_ALREADY_EXISTS"
    platform_conflict = env["client"].post("/api/v1/platform/administrators", headers=env["platform_headers"], json={
        "full_name": "Cross", "email": " TENANT@example.com ", "role": "admin", "password": "CrossPlatform123!", "password_confirmation": "CrossPlatform123!",
    })
    assert platform_conflict.status_code == 409 and platform_conflict.json()["code"] == "EMAIL_ALREADY_EXISTS"


def test_t15_t18_case_insensitive_login(identity_env):
    env = identity_env
    assert env["client"].post("/api/v1/auth/login", json={"email": " TeNaNt@Example.Com ", "password": TENANT_PASSWORD}).status_code == 200
    assert env["client"].post("/api/v1/platform/login", json={"email": " PlAtFoRm@Example.Com ", "password": PLATFORM_PASSWORD}).status_code == 200


def test_t19_t23_constraint_root_immutability_and_provisioning(identity_env):
    env = identity_env
    constraints = {constraint.name for constraint in User.__table__.constraints if isinstance(constraint, UniqueConstraint)}
    assert "uq_foundation_users_email_global" in constraints
    assert "uq_foundation_users_org_email" not in constraints
    root = env["db"].query(User).filter_by(email="tenant@example.com").one()
    response = env["client"].patch(f"/api/v1/admin/users/{root.id}", headers=env["tenant_headers"], json={"email": "changed@example.com"})
    assert response.status_code == 400
    env["db"].refresh(root)
    assert root.email == "tenant@example.com"


@pytest.mark.parametrize("email", ["", "not-an-email", f"{'a' * 244}@example.com", "üser@example.com"])
def test_t24_t27_invalid_email_rejected(email):
    with pytest.raises(ValueError):
        UserCreateRequest(full_name="Name", email=email, password="Password123!")


def test_t28_t30_all_input_schemas_normalize():
    assert PlatformAccountCreate(full_name="Name", email=" ADMIN@Example.COM ", password="PlatformAdmin123!", password_confirmation="PlatformAdmin123!", role="admin").email == "admin@example.com"
    assert LoginRequest(email=" LOGIN@Example.COM ", password="secret").email == "login@example.com"
    assert PlatformLoginRequest(email=" ROOT@Example.COM ", password="secret").email == "root@example.com"


def test_t31_t32_tenant_isolation_and_safe_error(identity_env):
    env = identity_env
    response = env["client"].post("/api/v1/admin/users", headers=env["tenant_headers"], json={
        "full_name": "Conflict", "email": "platform@example.com", "password": "Conflict123!", "role_codes": [],
    })
    assert response.status_code == 409
    body = response.json()
    assert body == {"code": "EMAIL_ALREADY_EXISTS", "message": "This email is already registered in the system"}
    assert "organization" not in str(body).lower() and "table" not in str(body).lower()


# Exercise the same fresh-verification handshake as the Platform UI.
from tests.platform_stepup_client import verified_platform_browser  # noqa: F401
import pytest
pytestmark = pytest.mark.usefixtures("verified_platform_browser")
