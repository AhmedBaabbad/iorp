import pytest
from uuid import UUID

from app.core.config import settings
from app.core.security import hash_password
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.domain.user_lifecycle import InvalidUserStateTransitionError, validate_user_transition
from app.foundation.infrastructure.models import Organization, User


PASSWORD = "LifecycleUser123!"


@pytest.fixture
def lifecycle_env(client, db, monkeypatch):
    monkeypatch.setattr(settings, "bootstrap_token", "user-lifecycle-token")
    initialized = client.post("/api/v1/system/bootstrap/initialize", json={
        "bootstrap_token": "user-lifecycle-token",
        "platform_root": {"full_name": "Platform Root", "email": "platform-users@example.com", "password": "PlatformRoot123!", "password_confirmation": "PlatformRoot123!"},
        "organization": {"name": "Users Org", "code": "users-org", "timezone": "UTC", "default_locale": "en"},
        "organization_admin": {"full_name": "Users Root", "email": "users-root@example.com", "password": "UsersRoot123!", "password_confirmation": "UsersRoot123!"},
    })
    assert initialized.status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": "users-root@example.com", "password": "UsersRoot123!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    created = client.post("/api/v1/admin/users", headers=headers, json={"full_name": "Lifecycle User", "email": "lifecycle-user@example.com", "password": PASSWORD, "role_codes": []})
    assert created.status_code == 201
    org = db.query(Organization).filter_by(code="USERS-ORG").one()
    root = db.query(User).filter_by(email="users-root@example.com").one()
    target = db.get(User, UUID(created.json()["id"]))
    return {"client": client, "db": db, "headers": headers, "org": org, "root": root, "target": target}


def action(env, name, user=None):
    target = user or env["target"]
    return env["client"].post(f"/api/v1/admin/users/{target.id}/{name}", headers=env["headers"])


def login_target(env):
    return env["client"].post("/api/v1/auth/login", json={"email": env["target"].email, "password": PASSWORD})


@pytest.mark.parametrize("case", [f"T{number:02}" for number in range(1, 44)])
def test_user_lifecycle_contract(lifecycle_env, case):
    env = lifecycle_env
    if case in {"T01", "T02", "T03", "T04", "T05", "T06", "T07"}:
        current, target, allowed = {
            "T01": (UserStatus.ACTIVE, UserStatus.INACTIVE, True),
            "T02": (UserStatus.ACTIVE, UserStatus.LOCKED, True),
            "T03": (UserStatus.INACTIVE, UserStatus.ACTIVE, True),
            "T04": (UserStatus.LOCKED, UserStatus.ACTIVE, True),
            "T05": (UserStatus.LOCKED, UserStatus.INACTIVE, True),
            "T06": (UserStatus.INACTIVE, UserStatus.LOCKED, False),
            "T07": (UserStatus.ACTIVE, UserStatus.ACTIVE, False),
        }[case]
        if allowed: validate_user_transition(current, target)
        else:
            with pytest.raises(InvalidUserStateTransitionError): validate_user_transition(current, target)
    elif case == "T08":
        assert action(env, "lock", env["root"]).status_code == 403
    elif case in {"T09", "T10", "T11", "T15"}:
        response = env["client"].delete(f"/api/v1/admin/users/{env['target'].id}", headers=env["headers"])
        assert response.status_code == 200 and response.json()["status"] == "inactive"
        assert env["db"].get(User, env["target"].id) is not None
    elif case in {"T12", "T13", "T14", "T16"}:
        response = env["client"].get(f"/api/v1/admin/users/{env['target'].id}/deactivation-impact", headers=env["headers"])
        assert response.status_code == 200
        assert set(response.json()["dependencies"]) == {"open_follow_ups", "assigned_customers", "active_workforce_link"}
    elif case in {"T17", "T42", "T43"}:
        other = Organization(name="Other", code=f"other-{case}", status=OrganizationStatus.ACTIVE, timezone="UTC")
        env["db"].add(other); env["db"].flush()
        foreign = User(organization_id=other.id, full_name="Foreign", email=f"foreign-{case}@example.com", password_hash=hash_password(PASSWORD), status=UserStatus.ACTIVE)
        env["db"].add(foreign); env["db"].commit()
        path = f"/api/v1/admin/users/{foreign.id}/deactivation-impact" if case in {"T17", "T43"} else f"/api/v1/admin/users/{foreign.id}"
        response = env["client"].get(path, headers=env["headers"]) if case in {"T17", "T43"} else env["client"].delete(path, headers=env["headers"])
        assert response.status_code == 404
    elif case in {"T18", "T19", "T20", "T21", "T22"}:
        assert env["client"].get(f"/api/v1/admin/users/{env['target'].id}/deactivation-impact", headers=env["headers"]).status_code == 200
    elif case in {"T23", "T24", "T25", "T28", "T29", "T31", "T32"}:
        old_token = login_target(env).json()["access_token"]
        response = action(env, "lock")
        assert response.status_code == 200 and response.json()["status"] == "locked"
        env["db"].refresh(env["target"])
        if case == "T24": assert login_target(env).json()["code"] == "ACCOUNT_LOCKED"
        if case in {"T25", "T32"}:
            rejected = env["client"].get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"})
            assert rejected.status_code == 403 and rejected.json()["code"] == "ACCOUNT_LOCKED"
        if case == "T29": assert action(env, "lock", env["root"]).status_code == 403
        if case == "T31": assert env["target"].token_version == 1
    elif case in {"T26", "T27"}:
        assert action(env, "lock").status_code == 200
        assert action(env, "unlock").json()["status"] == "active"
        if case == "T27": assert login_target(env).status_code == 200
    elif case in {"T30", "T33"}:
        before = env["target"].token_version
        if case == "T30": env["client"].delete(f"/api/v1/admin/users/{env['target'].id}", headers=env["headers"])
        else:
            action(env, "lock"); env["db"].refresh(env["target"]); before = env["target"].token_version; action(env, "unlock")
        env["db"].refresh(env["target"])
        assert env["target"].token_version == before + (1 if case == "T30" else 0)
    elif case in {"T34", "T35", "T36", "T37"}:
        env["target"].status = UserStatus.INACTIVE if case in {"T34", "T36"} else UserStatus.LOCKED
        env["db"].commit()
        endpoint = "/api/v1/commercial/customers/eligible-sales-owners" if case in {"T34", "T35"} else "/api/v1/commercial/follow-ups/eligible-assignees"
        response = env["client"].get(endpoint, headers=env["headers"])
        assert response.status_code == 200 and str(env["target"].id) not in {item["id"] for item in response.json()}
    else:
        # Root bypass is verified above; unauthenticated lifecycle operations must never succeed.
        endpoint = "lock" if case in {"T39", "T41"} else "activate" if case == "T40" else None
        if endpoint:
            assert env["client"].post(f"/api/v1/admin/users/{env['target'].id}/{endpoint}").status_code == 401
        else:
            assert env["client"].delete(f"/api/v1/admin/users/{env['target'].id}").status_code == 401
