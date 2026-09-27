"""Baseline auth tests — login flow and /me endpoint.

Covers:
  - Successful login returns a bearer token
  - Wrong password is rejected with 401
  - Unknown email is rejected with 401
  - Inactive user is rejected with 401
  - /me returns the authenticated user's profile
  - Request without a token is rejected with 401
"""

from app.foundation.domain.enums import UserStatus
from app.foundation.infrastructure.models import User
from app.core.security import hash_password


# ── Login ─────────────────────────────────────────────────────────────────────

def test_login_success(client, test_user):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "Test1234!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client, test_user):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "not-the-right-one"},
    )
    assert resp.status_code == 401


def test_login_unknown_email(client, test_org):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "Test1234!"},
    )
    assert resp.status_code == 401


def test_login_inactive_user(client, db, test_org):
    user = User(
        organization_id=test_org.id,
        full_name="Inactive User",
        email="inactive@example.com",
        password_hash=hash_password("Test1234!"),
        status=UserStatus.INACTIVE,
    )
    db.add(user)
    db.commit()

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@example.com", "password": "Test1234!"},
    )
    assert resp.status_code == 403


# ── /me ───────────────────────────────────────────────────────────────────────

def test_get_current_user(client, auth_headers, test_user, test_org):
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert data["organization_id"] == str(test_user.organization_id)
    assert data["organization_code"] == test_org.code


def test_get_current_user_without_token(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
