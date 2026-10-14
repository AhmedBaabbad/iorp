"""User profile and login identity separation contract (T01-T39)."""
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.core.config import settings
from app.foundation.api.schemas import AdminUserResponse, UserProfileResponse, UserProfileUpdate
from app.foundation.infrastructure.models import User


ROOT_PASSWORD = "ProfileRoot123!"
USER_PASSWORD = "ProfileUser123!"


@pytest.fixture
def profile_env(client, db, monkeypatch, activate):
    monkeypatch.setattr(settings, "bootstrap_token", "profile-token")
    initialized = client.post("/api/v1/system/bootstrap/initialize", json={
        "bootstrap_token": "profile-token",
        "platform_root": {"full_name": "Platform Root", "email": "platform-profile@example.com", "password": "PlatformProfile123!", "password_confirmation": "PlatformProfile123!"},
        "organization": {"name": "Profile Org", "code": "profile-org", "timezone": "UTC", "default_locale": "en"},
        "organization_admin": {"full_name": "Profile Root", "email": "profile-root@example.com", "password": ROOT_PASSWORD, "password_confirmation": ROOT_PASSWORD},
    })
    assert initialized.status_code == 201
    root_login = client.post("/api/v1/auth/login", json={"email": "profile-root@example.com", "password": ROOT_PASSWORD})
    root_headers = {"Authorization": f"Bearer {root_login.json()['access_token']}"}
    created = client.post("/api/v1/admin/users", headers=root_headers, json={
        "full_name": "Profile User", "email": "profile-user@example.com", "password": USER_PASSWORD, "role_codes": [],
    })
    assert created.status_code == 201, created.json()
    activate("profile-user@example.com", USER_PASSWORD, platform=False)  # SEC-003: the owner chooses the password
    user_login = client.post("/api/v1/auth/login", json={"email": "profile-user@example.com", "password": USER_PASSWORD})
    user_headers = {"Authorization": f"Bearer {user_login.json()['access_token']}"}
    return {"client": client, "db": db, "root_headers": root_headers, "user_headers": user_headers, "user_id": UUID(created.json()["id"])}


def test_t01_t09_schema_separation():
    for schema in (UserProfileResponse, AdminUserResponse):
        assert "password_hash" not in schema.model_fields
        assert "token_version" not in schema.model_fields
    for forbidden in ("email", "password", "status", "is_organization_root", "organization_id"):
        with pytest.raises(ValidationError):
            UserProfileUpdate.model_validate({forbidden: "forbidden"})


def test_t10_t14_self_service_read(profile_env):
    response = profile_env["client"].get("/api/v1/auth/me", headers=profile_env["user_headers"])
    assert response.status_code == 200
    body = response.json()
    assert body["preferred_locale"] is None
    assert body["organization_name"] == "Profile Org"
    assert body["effective_locale"] == "en"
    assert "password_hash" not in body and "token_version" not in body
    assert profile_env["client"].get("/api/v1/auth/me").status_code == 401
    profile = profile_env["client"].get("/api/v1/auth/me/profile", headers=profile_env["user_headers"])
    assert profile.status_code == 200
    assert set(profile.json()) == set(UserProfileResponse.model_fields)


def test_t15_t22_profile_updates_and_rejects_identity(profile_env):
    client, headers = profile_env["client"], profile_env["user_headers"]
    assert client.patch("/api/v1/auth/me", headers=headers, json={"full_name": "Updated User"}).json()["full_name"] == "Updated User"
    assert client.patch("/api/v1/auth/me", headers=headers, json={"phone": "+966555000000"}).json()["phone"] == "+966555000000"
    assert client.patch("/api/v1/auth/me", headers=headers, json={"preferred_locale": "ar"}).json()["preferred_locale"] == "ar"
    assert client.patch("/api/v1/auth/me", headers=headers, json={"preferred_locale": "en"}).json()["preferred_locale"] == "en"
    assert client.patch("/api/v1/auth/me", headers=headers, json={"preferred_locale": "fr"}).status_code == 400
    for field, value in (("email", "other@example.com"), ("password", "Other123!"), ("status", "inactive")):
        assert client.patch("/api/v1/auth/me", headers=headers, json={field: value}).status_code == 422


def test_t23_t26_root_rules_and_session_stability(profile_env):
    env = profile_env
    root = env["db"].query(User).filter_by(email="profile-root@example.com").one()
    before = root.token_version
    assert env["client"].patch("/api/v1/auth/me", headers=env["root_headers"], json={"full_name": "Changed Root"}).status_code == 403
    assert env["client"].patch("/api/v1/auth/me", headers=env["root_headers"], json={"phone": "+966500000001"}).status_code == 200
    env["db"].refresh(root)
    assert root.token_version == before
    assert env["client"].get("/api/v1/auth/me", headers=env["root_headers"]).status_code == 200


def test_t27_t30_admin_and_self_service_are_separate(profile_env):
    env = profile_env
    admin = env["client"].get(f"/api/v1/admin/users/{env['user_id']}", headers=env["root_headers"])
    own = env["client"].get("/api/v1/auth/me", headers=env["user_headers"])
    assert admin.status_code == own.status_code == 200
    assert "permissions" in admin.json() and "organization" not in admin.json()
    assert "organization" in own.json()
    assert env["client"].patch(f"/api/v1/admin/users/{env['user_id']}", headers=env["root_headers"], json={"full_name": "Admin Updated"}).status_code == 400
    assert env["client"].patch(f"/api/v1/admin/users/{env['user_id']}", headers=env["user_headers"], json={"full_name": "Denied"}).status_code == 403


def test_t31_t33_preferred_and_effective_locale(profile_env):
    env = profile_env
    before = env["client"].get("/api/v1/auth/me", headers=env["user_headers"]).json()
    assert before["preferred_locale"] is None and before["effective_locale"] == "en"
    env["client"].patch("/api/v1/auth/me", headers=env["user_headers"], json={"preferred_locale": "ar"})
    after = env["client"].get("/api/v1/auth/me", headers=env["user_headers"]).json()
    assert after["preferred_locale"] == after["effective_locale"] == "ar"


def test_t34_t37_security_fields_never_leak(profile_env):
    env = profile_env
    responses = [
        env["client"].get("/api/v1/auth/me", headers=env["user_headers"]),
        env["client"].get(f"/api/v1/admin/users/{env['user_id']}", headers=env["root_headers"]),
        env["client"].get("/api/v1/admin/users", headers=env["root_headers"]),
    ]
    for response in responses:
        assert response.status_code == 200
        assert "password_hash" not in response.text and "token_version" not in response.text


def test_t38_t39_self_service_is_bound_to_token_identity(profile_env):
    env = profile_env
    root_before = env["db"].query(User).filter_by(email="profile-root@example.com").one().phone
    own_id = env["client"].get("/api/v1/auth/me", headers=env["user_headers"]).json()["id"]
    assert own_id == str(env["user_id"])
    assert env["client"].patch("/api/v1/auth/me", headers=env["user_headers"], json={"phone": "+966511111111"}).status_code == 200
    root = env["db"].query(User).filter_by(email="profile-root@example.com").one()
    target = env["db"].get(User, env["user_id"])
    assert root.phone == root_before and target.phone == "+966511111111"
