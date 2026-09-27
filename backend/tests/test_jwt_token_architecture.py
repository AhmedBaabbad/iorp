from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from jose import jwt
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.core.security import ALGORITHM, TokenValidationError, create_access_token, decode_token, hash_password
from app.core.security_models import AuthSession
from app.platform.domain.enums import PlatformAccountStatus
from app.platform.infrastructure.models import PlatformAccount


def _payload(account_type="tenant", token_type="access"):
    now = datetime.now(timezone.utc)
    value = {
        "sub": str(uuid4()), "account_type": account_type, "token_type": token_type,
        "jti": str(uuid4()), "token_version": 0, "iat": now, "nbf": now,
        "exp": now + timedelta(minutes=5), "iss": settings.jwt_issuer, "aud": settings.jwt_audience,
    }
    if account_type == "tenant":
        value["organization_id"] = str(uuid4())
    return value


def _signed(payload):
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


@pytest.mark.parametrize("account_type", ["tenant", "platform"])
def test_jwt_01_02_access_claim_contract(account_type):
    organization_id = str(uuid4()) if account_type == "tenant" else None
    token = create_access_token(str(uuid4()), {"account_type": account_type, "organization_id": organization_id, "token_version": 3})
    claims = decode_token(token, "access")
    assert claims["account_type"] == account_type and claims["token_type"] == "access"
    assert claims["token_version"] == 3 and claims["jti"]
    assert claims["iss"] == settings.jwt_issuer and claims["aud"] == settings.jwt_audience
    assert ("organization_id" in claims) is (account_type == "tenant")


@pytest.mark.parametrize("claim", ["sub", "account_type", "token_type", "jti", "token_version", "iat", "nbf", "exp", "iss", "aud"])
def test_jwt_03_12_missing_mandatory_claim_is_rejected(claim):
    payload = _payload()
    payload.pop(claim)
    with pytest.raises(TokenValidationError):
        decode_token(_signed(payload))


@pytest.mark.parametrize(
    "mutation,code",
    [
        ({"account_type": "unknown"}, "INVALID_TOKEN"),
        ({"organization_id": None}, "INVALID_TOKEN"),
        ({"account_type": "platform", "organization_id": str(uuid4())}, "INVALID_TOKEN"),
        ({"token_type": "other"}, "TOKEN_TYPE_INVALID"),
        ({"iss": "other"}, "INVALID_TOKEN"),
        ({"aud": "other"}, "INVALID_TOKEN"),
        ({"token_version": "0"}, "INVALID_TOKEN"),
        ({"jti": ""}, "INVALID_TOKEN"),
    ],
)
def test_jwt_13_20_malformed_or_cross_scope_token_is_rejected(mutation, code):
    payload = _payload()
    payload.update(mutation)
    if payload.get("organization_id") is None:
        payload.pop("organization_id", None)
    with pytest.raises(TokenValidationError) as caught:
        decode_token(_signed(payload))
    assert caught.value.code == code


@pytest.mark.parametrize(
    "field,value",
    [
        ("tenant_access_token_minutes", 0), ("tenant_access_token_minutes", 61),
        ("platform_access_token_minutes", 0), ("platform_access_token_minutes", 31),
        ("tenant_refresh_token_days", 0), ("tenant_refresh_token_days", 31),
        ("platform_refresh_token_hours", 0), ("platform_refresh_token_hours", 169),
        ("jwt_clock_skew_seconds", -1), ("jwt_clock_skew_seconds", 121),
        ("refresh_rate_limit", 0), ("refresh_rate_limit", 121),
    ],
)
def test_jwt_21_32_unsafe_configuration_is_rejected(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


def test_jwt_33_tenant_login_sets_httponly_refresh_cookie_without_body_token(client, test_user):
    response = client.post("/api/v1/auth/login", json={"email": test_user.email, "password": "Test1234!"})
    assert response.status_code == 200 and "refresh_token" not in response.json()
    assert "HttpOnly" in response.headers["set-cookie"] and settings.refresh_cookie_name in response.cookies


def test_jwt_34_tenant_refresh_rotates_and_returns_access_only(client, test_user):
    login = client.post("/api/v1/auth/login", json={"email": test_user.email, "password": "Test1234!"})
    old_refresh = login.cookies[settings.refresh_cookie_name]
    refreshed = client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200, refreshed.text
    assert "refresh_token" not in refreshed.json()
    assert refreshed.cookies[settings.refresh_cookie_name] != old_refresh


def test_jwt_35_refresh_reuse_revokes_family(client, test_user):
    login = client.post("/api/v1/auth/login", json={"email": test_user.email, "password": "Test1234!"})
    old_refresh = login.cookies[settings.refresh_cookie_name]
    assert client.post("/api/v1/auth/refresh").status_code == 200
    client.cookies.clear()
    client.cookies.set(settings.refresh_cookie_name, old_refresh, path="/api/v1/auth")
    reused = client.post("/api/v1/auth/refresh")
    assert reused.status_code == 401 and reused.json()["code"] == "TOKEN_REUSED"


def test_jwt_36_logout_revokes_tenant_refresh(client, test_user):
    client.post("/api/v1/auth/login", json={"email": test_user.email, "password": "Test1234!"})
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.post("/api/v1/auth/refresh").status_code == 401


@pytest.fixture
def platform_account(db):
    account = PlatformAccount(full_name="JWT Platform", email="jwt-platform@example.com", password_hash=hash_password("PlatformJwt123!"), status=PlatformAccountStatus.ACTIVE, is_root=True, token_version=0)
    db.add(account); db.commit()
    return account


def test_jwt_37_platform_login_uses_platform_scoped_cookie(client, platform_account):
    response = client.post("/api/v1/platform/login", json={"email": platform_account.email, "password": "PlatformJwt123!"})
    claims = decode_token(response.json()["access_token"], "access")
    assert response.status_code == 200 and claims["account_type"] == "platform" and "organization_id" not in claims
    assert "Path=/api/v1/platform" in response.headers["set-cookie"]


def test_jwt_38_platform_refresh_and_logout(client, platform_account):
    client.post("/api/v1/platform/login", json={"email": platform_account.email, "password": "PlatformJwt123!"})
    assert client.post("/api/v1/platform/refresh").status_code == 200
    assert client.post("/api/v1/platform/logout").status_code == 204


def test_jwt_39_refresh_token_hash_only_at_rest(client, db, test_user):
    response = client.post("/api/v1/auth/login", json={"email": test_user.email, "password": "Test1234!"})
    raw = response.cookies[settings.refresh_cookie_name]
    session = db.query(AuthSession).order_by(AuthSession.created_at.desc()).first()
    assert session and len(session.jti_hash) == 64 and raw != session.jti_hash and raw not in session.jti_hash


def test_jwt_40_refresh_token_cannot_access_api(client, test_user):
    response = client.post("/api/v1/auth/login", json={"email": test_user.email, "password": "Test1234!"})
    raw = response.cookies[settings.refresh_cookie_name]
    protected = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {raw}"})
    assert protected.status_code == 401
