import pytest

from app.core.config import settings
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, User
from app.platform.domain.policies import InvalidStateTransitionError, validate_transition
from app.platform.infrastructure.models import PlatformAccount


PASSWORD = "TenantRoot123!"


@pytest.fixture
def lifecycle(client, db, monkeypatch):
    monkeypatch.setattr(settings, "bootstrap_token", "lifecycle-token")
    initialized = client.post("/api/v1/system/bootstrap/initialize", json={
        "bootstrap_token": "lifecycle-token",
        "platform_root": {"full_name": "Platform Root", "email": "platform@example.com", "password": "PlatformRoot123!", "password_confirmation": "PlatformRoot123!"},
        "organization": {"name": "Lifecycle Org", "code": "lifecycle-org", "timezone": "UTC", "default_locale": "en"},
        "organization_admin": {"full_name": "Organization Root", "email": "tenant@example.com", "password": PASSWORD, "password_confirmation": PASSWORD},
    })
    assert initialized.status_code == 201
    platform_login = client.post("/api/v1/platform/login", json={"email": "platform@example.com", "password": "PlatformRoot123!"})
    assert platform_login.status_code == 200
    org = db.query(Organization).filter_by(code="LIFECYCLE-ORG").one()
    user = db.query(User).filter_by(email="tenant@example.com").one()
    return {
        "client": client, "db": db, "org": org, "user": user,
        "platform_headers": {"Authorization": f"Bearer {platform_login.json()['access_token']}"},
    }


def _set_status(env, value):
    env["org"].status = OrganizationStatus(value)
    env["db"].commit()


def _post(env, action, reason="test reason", headers=None):
    return env["client"].post(
        f"/api/v1/platform/organizations/{env['org'].id}/{action}",
        headers=headers or env["platform_headers"], json={"reason": reason},
    )


def _login(env):
    return env["client"].post("/api/v1/auth/login", json={"email": "tenant@example.com", "password": PASSWORD})


@pytest.mark.parametrize("case,current,action,target,expected", [
    ("T01", "provisioning", "activate", "active", 200),
    ("T02", "active", "suspend", "suspended", 200),
    ("T03", "active", "deactivate", "inactive", 200),
    ("T04", "suspended", "activate", "active", 200),
    ("T05", "suspended", "deactivate", "inactive", 200),
    ("T06", "inactive", "activate", "active", 200),
    ("T07", "inactive", "archive", "archived", 200),
    ("T08", "archived", "activate", "active", 409),
    ("T09", "archived", "suspend", "suspended", 409),
    ("T10", "archived", "deactivate", "inactive", 409),
    ("T11", "active", "archive", "archived", 409),
    ("T12", "active", None, "provisioning", 409),
    ("T13", "suspended", "archive", "archived", 409),
    ("T14", "active", "activate", "active", 409),
], ids=lambda value: value if isinstance(value, str) and value.startswith("T") else None)
def test_state_machine_transitions(lifecycle, case, current, action, target, expected):
    _set_status(lifecycle, current)
    if action is None:
        with pytest.raises(InvalidStateTransitionError) as caught:
            validate_transition(current, target)
        assert caught.value.code == "INVALID_STATE_TRANSITION"
        return
    response = _post(lifecycle, action)
    assert response.status_code == expected
    if expected == 200:
        assert response.json()["status"] == target
        assert response.json()["allowed_transitions"] == sorted({
            "active": ["inactive", "suspended"],
            "suspended": ["active", "inactive"],
            "inactive": ["active", "archived"],
            "archived": [],
        }[target])
    else:
        assert response.json()["code"] == "INVALID_STATE_TRANSITION"


@pytest.mark.parametrize("case", ["T15", "T16", "T17", "T18", "T19", "T20", "T21"])
def test_login_gate(lifecycle, case):
    if case == "T15": assert _login(lifecycle).status_code == 200; return
    if case == "T19":
        token = _login(lifecycle).json()["access_token"]; _post(lifecycle, "suspend")
        assert lifecycle["client"].get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 403; return
    if case == "T20":
        _post(lifecycle, "suspend"); assert _login(lifecycle).status_code == 403
        _post(lifecycle, "activate"); assert _login(lifecycle).status_code == 200; return
    status, action, code = {
        "T16": ("active", "suspend", "ORGANIZATION_SUSPENDED"),
        "T17": ("active", "deactivate", "ORGANIZATION_INACTIVE"),
        "T18": ("inactive", "archive", "ORGANIZATION_ARCHIVED"),
        "T21": ("active", "suspend", "ORGANIZATION_SUSPENDED"),
    }[case]
    _set_status(lifecycle, status); _post(lifecycle, action)
    response = _login(lifecycle); assert response.status_code == 403 and response.json()["code"] == code


@pytest.mark.parametrize("case", ["T22", "T23"])
def test_hard_delete_prevention(lifecycle, case):
    response = lifecycle["client"].delete(f"/api/v1/platform/organizations/{lifecycle['org'].id}", headers=lifecycle["platform_headers"])
    assert response.status_code == 403 and response.json()["code"] == "ORGANIZATION_CANNOT_BE_DELETED"
    if case == "T23": assert lifecycle["db"].get(Organization, lifecycle["org"].id) is not None


@pytest.mark.parametrize("case", ["T24", "T25", "T26", "T27"])
def test_lifecycle_metadata(lifecycle, case):
    if case == "T27":
        _set_status(lifecycle, "inactive"); response = _post(lifecycle, "archive", reason="")
        assert response.status_code == 400 and response.json()["code"] == "ARCHIVE_REASON_REQUIRED"; return
    response = _post(lifecycle, "suspend", reason="Compliance review"); assert response.status_code == 200
    body = response.json()
    if case == "T24": assert body["status_changed_at"]
    if case == "T25": assert body["status_changed_by"]
    if case == "T26": assert body["status_change_reason"] == "Compliance review"


@pytest.mark.parametrize("case", ["T28", "T29", "T30", "T31"])
def test_lifecycle_permissions(lifecycle, case, activate):
    if case == "T28": assert _post(lifecycle, "suspend").status_code == 200; return
    root_headers = lifecycle["platform_headers"]
    created = lifecycle["client"].post("/api/v1/platform/administrators", headers=root_headers, json={
        "full_name": "Read Admin", "email": "read-admin@example.com", "role": "admin",
        "password": "ReadAdmin123!", "password_confirmation": "ReadAdmin123!",
    }); assert created.status_code == 201
    activate("read-admin@example.com", "ReadAdmin123!", platform=True)  # SEC-003: the owner chooses the password
    login = lifecycle["client"].post("/api/v1/platform/login", json={"email": "read-admin@example.com", "password": "ReadAdmin123!"})
    admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    if case == "T29": assert _post(lifecycle, "suspend", headers=admin_headers).status_code == 403
    if case == "T30": assert lifecycle["client"].get("/api/v1/platform/organizations", headers=admin_headers).status_code == 200
    if case == "T31":
        tenant_headers = {"Authorization": f"Bearer {_login(lifecycle).json()['access_token']}"}
        assert _post(lifecycle, "suspend", headers=tenant_headers).status_code == 401


@pytest.mark.parametrize("case", ["T32", "T33", "T34", "T35"])
def test_lifecycle_data_preservation(lifecycle, case):
    user_status = lifecycle["user"].status
    if case in {"T32", "T34", "T35"}: _post(lifecycle, "suspend")
    if case == "T33": _post(lifecycle, "deactivate"); _post(lifecycle, "archive")
    if case == "T34": _post(lifecycle, "activate")
    assert lifecycle["db"].get(Organization, lifecycle["org"].id) is not None
    assert lifecycle["db"].get(User, lifecycle["user"].id) is not None
    if case == "T35": assert lifecycle["db"].get(User, lifecycle["user"].id).status == user_status == UserStatus.ACTIVE


@pytest.mark.parametrize("case", ["T36", "T37", "T38", "T39", "T40"])
def test_lifecycle_edge_cases(lifecycle, case):
    if case == "T36": _post(lifecycle, "suspend"); response = _post(lifecycle, "suspend")
    elif case == "T37": response = _post(lifecycle, "activate")
    elif case == "T38": _post(lifecycle, "deactivate"); _post(lifecycle, "archive"); response = _post(lifecycle, "archive")
    elif case == "T39": response = _post(lifecycle, "suspend", reason="")
    else: _set_status(lifecycle, "inactive"); response = _post(lifecycle, "archive", reason="   ")
    assert response.status_code == (200 if case == "T39" else 400 if case == "T40" else 409)
    if case == "T40": assert response.json()["code"] == "ARCHIVE_REASON_REQUIRED"
