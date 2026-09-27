"""ORG-AUTH-001 login protection contract (T01-T44)."""
from datetime import timedelta

import pytest

from app.core.rate_limit import _attempts
from app.core.security import hash_password
from app.core.utils import utc_now
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, User
from app.foundation.infrastructure.models import Permission
from app.platform.domain.enums import PlatformAccountRole, PlatformAccountStatus
from app.platform.infrastructure.models import PlatformAccount
from app.core.config import settings


PASSWORD = "LoginProtection123!"


@pytest.fixture
def protected_accounts(db):
    org = Organization(name="Protected Org", code="protected-org", status=OrganizationStatus.ACTIVE, timezone="UTC")
    db.add(org); db.flush()
    user = User(organization_id=org.id, full_name="Protected User", email="protected@example.com", password_hash=hash_password(PASSWORD), status=UserStatus.ACTIVE)
    root = User(organization_id=org.id, full_name="Root", email="protected-root@example.com", password_hash=hash_password(PASSWORD), status=UserStatus.ACTIVE, is_organization_root=True)
    platform = PlatformAccount(full_name="Platform Admin", email="platform-protected@example.com", password_hash=hash_password(PASSWORD), status=PlatformAccountStatus.ACTIVE, role=PlatformAccountRole.ADMIN)
    platform_root = PlatformAccount(full_name="Platform Root", email="platform-root-protected@example.com", password_hash=hash_password(PASSWORD), status=PlatformAccountStatus.ACTIVE, role=PlatformAccountRole.ROOT, is_root=True)
    db.add_all([user, root, platform, platform_root]); db.commit()
    return org, user, root, platform, platform_root


def _tenant(client, email="protected@example.com", password=PASSWORD, ip="testclient"):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password}, headers={"X-Forwarded-For": ip})


def _platform(client, email="platform-protected@example.com", password=PASSWORD):
    return client.post("/api/v1/platform/login", json={"email": email, "password": password})


def test_t01_t06_ip_rate_limits(client, protected_accounts):
    assert _tenant(client).status_code == 200
    _attempts.clear()
    responses = [_tenant(client, email=f"missing-{i}@example.com") for i in range(11)]
    assert responses[-1].status_code == 429
    assert responses[-1].json()["code"] == "RATE_LIMIT_EXCEEDED"
    assert responses[-1].json()["retry_after_seconds"] > 0
    assert "Retry-After" in responses[-1].headers
    _attempts.clear()
    platform = [_platform(client, email=f"missing-{i}@example.com") for i in range(6)]
    assert platform[-1].status_code == 429


def test_t07_t12_counter_persistence_and_reset(client, db, protected_accounts):
    user = protected_accounts[1]
    assert _tenant(client, password="wrong").status_code == 401
    db.refresh(user); first_at = user.last_failed_login_at
    assert user.failed_login_attempts == 1 and first_at is not None
    assert _tenant(client, password="wrong-again").status_code == 401
    db.refresh(user)
    assert user.failed_login_attempts == 2 and user.last_failed_login_at >= first_at
    assert _tenant(client).status_code == 200
    db.refresh(user)
    assert user.failed_login_attempts == 0 and user.last_failed_login_at is None


def test_t13_t18_t42_temporary_lock_and_expiry(client, db, protected_accounts):
    user = protected_accounts[1]
    responses = [_tenant(client, password="wrong") for _ in range(5)]
    assert responses[-1].status_code == 403
    body = responses[-1].json()
    assert body["code"] == "ACCOUNT_TEMPORARILY_LOCKED" and body["retry_after_seconds"] > 0 and body["locked_until"]
    assert _tenant(client).status_code == 403
    user.auto_locked_until = utc_now() - timedelta(seconds=1); db.commit(); _attempts.clear()
    assert _tenant(client).status_code == 200
    db.refresh(user)
    assert user.failed_login_attempts == 0 and user.auto_locked_until is None


def test_t19_t24_root_exemptions_and_platform_threshold(client, db, protected_accounts):
    root, platform, platform_root = protected_accounts[2:]
    for _ in range(10):
        _attempts.clear(); assert _tenant(client, root.email, "wrong").status_code == 401
    db.refresh(root)
    assert root.failed_login_attempts == 10 and root.auto_locked_until is None
    _attempts.clear(); assert _tenant(client, root.email, PASSWORD).status_code == 200
    for _ in range(10):
        _attempts.clear(); assert _platform(client, platform_root.email, "wrong").status_code == 401
    db.refresh(platform_root); assert platform_root.auto_locked_until is None
    _attempts.clear()
    assert [_platform(client, platform.email, "wrong").status_code for _ in range(3)][-1] == 403


def test_t25_t32_admin_lock_unlock_and_success_reset(client, db, protected_accounts):
    user = protected_accounts[1]
    user.status = UserStatus.LOCKED; user.failed_login_attempts = 4; user.auto_locked_until = utc_now() + timedelta(minutes=10); db.commit()
    response = _tenant(client)
    assert response.status_code == 403 and response.json()["code"] == "ACCOUNT_LOCKED"
    user.status = UserStatus.ACTIVE; user.auto_locked_until = None; db.commit(); _attempts.clear()
    assert _tenant(client).status_code == 200
    db.refresh(user); assert user.failed_login_attempts == 0
    assert _tenant(client, password="wrong").status_code == 401
    db.refresh(user); assert user.failed_login_attempts == 1


def test_t33_t37_tenant_remaining_attempts_are_shown_only_for_non_root(client, protected_accounts):
    missing = _tenant(client, "absent@example.com", "wrong")
    existing = _tenant(client, password="wrong")
    assert missing.status_code == existing.status_code == 401
    assert missing.json() == {"detail": "Invalid credentials."}
    assert existing.json() == {
        "code": "INVALID_CREDENTIALS",
        "message": "Invalid credentials.",
        "failed_login_attempts": 1,
        "remaining_attempts": 4,
    }


def test_organization_root_failure_does_not_expose_attempt_counter(client, protected_accounts):
    root = protected_accounts[2]
    response = _tenant(client, root.email, "wrong")
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials."}


@pytest.mark.parametrize("failure_number,remaining", [(1, 4), (2, 3), (3, 2), (4, 1)])
def test_non_root_response_counts_down_before_lock(client, protected_accounts, failure_number, remaining):
    response = None
    for _ in range(failure_number):
        response = _tenant(client, password="wrong")
    assert response is not None
    assert response.status_code == 401
    assert response.json()["failed_login_attempts"] == failure_number
    assert response.json()["remaining_attempts"] == remaining


def test_t38_t41_admin_fields_not_self_profile(client, db, protected_accounts):
    user = protected_accounts[1]
    user.failed_login_attempts = 2; user.last_failed_login_at = utc_now(); db.commit()
    login = _tenant(client); headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    profile = client.get("/api/v1/auth/me/profile", headers=headers)
    assert profile.status_code == 200
    assert "failed_login_attempts" not in profile.json() and "auto_locked_until" not in profile.json()


def test_t43_t44_inactive_and_organization_priority(client, db, protected_accounts):
    org, user = protected_accounts[:2]
    user.status = UserStatus.INACTIVE; db.commit()
    response = _tenant(client, password="wrong")
    assert response.status_code == 403 and response.json()["code"] == "ACCOUNT_INACTIVE"
    user.status = UserStatus.ACTIVE; user.auto_locked_until = utc_now() + timedelta(minutes=10); org.status = OrganizationStatus.SUSPENDED; db.commit(); _attempts.clear()
    response = _tenant(client)
    assert response.status_code == 403 and response.json()["code"] == "ORGANIZATION_SUSPENDED"


def test_t04_rate_limit_window_expiry_allows_login(client, protected_accounts, monkeypatch):
    import app.core.rate_limit as limiter
    clock = [1000.0]
    monkeypatch.setattr(limiter, "monotonic", lambda: clock[0])
    _attempts.clear()
    for index in range(10):
        assert _tenant(client, email=f"window-{index}@example.com").status_code == 401
    assert _tenant(client).status_code == 429
    clock[0] += 61
    assert _tenant(client).status_code == 200


def test_t05_different_trusted_forwarded_ips_are_independent(client, protected_accounts, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "trusted_proxy_ips", "testclient")
    _attempts.clear()
    for index in range(10):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": f"ip-a-{index}@example.com", "password": "wrong"},
            headers={"X-Forwarded-For": "198.51.100.10"},
        )
        assert response.status_code == 401
    blocked = client.post("/api/v1/auth/login", json={"email": "absent@example.com", "password": "wrong"}, headers={"X-Forwarded-For": "198.51.100.10"})
    independent = client.post("/api/v1/auth/login", json={"email": "absent@example.com", "password": "wrong"}, headers={"X-Forwarded-For": "198.51.100.11"})
    assert blocked.status_code == 429
    assert independent.status_code == 401


def test_t11_account_counters_are_independent(client, db, protected_accounts):
    org, first = protected_accounts[:2]
    second = User(organization_id=org.id, full_name="Second", email="second-protected@example.com", password_hash=hash_password(PASSWORD), status=UserStatus.ACTIVE)
    db.add(second); db.commit()
    assert _tenant(client, first.email, "wrong").status_code == 401
    db.refresh(first); db.refresh(second)
    assert first.failed_login_attempts == 1
    assert second.failed_login_attempts == 0


def test_t28_t29_t38_t39_admin_detail_and_unlock_endpoint(client, db, protected_accounts):
    org, user, root = protected_accounts[:3]
    db.add_all([
        Permission(organization_id=org.id, code="foundation:users:read", name="Read users", description="Read users", module_name="foundation", resource_name="users", action_name="read"),
        Permission(organization_id=org.id, code="foundation:users:lock", name="Lock users", description="Lock users", module_name="foundation", resource_name="users", action_name="lock"),
    ])
    user.failed_login_attempts = 5
    user.last_failed_login_at = utc_now()
    user.auto_locked_until = utc_now() + timedelta(minutes=10)
    db.commit(); _attempts.clear()
    root_login = _tenant(client, root.email, PASSWORD)
    headers = {"Authorization": f"Bearer {root_login.json()['access_token']}"}
    detail = client.get(f"/api/v1/admin/users/{user.id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["failed_login_attempts"] == 5
    assert detail.json()["auto_locked_until"] is not None
    unlocked = client.post(f"/api/v1/admin/users/{user.id}/unlock", headers=headers)
    assert unlocked.status_code == 200
    db.refresh(user)
    assert user.failed_login_attempts == 0
    assert user.auto_locked_until is None
    assert user.last_failed_login_at is None


@pytest.mark.parametrize("endpoint,email", [
    ("/api/v1/auth/login", "absent-timing@example.com"),
    ("/api/v1/platform/login", "absent-platform-timing@example.com"),
])
def test_t33_t35_unknown_identity_executes_dummy_password_verification(client, protected_accounts, monkeypatch, endpoint, email):
    import app.foundation.application.services as foundation_services
    import app.platform.application.services as platform_services
    calls: list[str | None] = []

    def tracked_verify(password: str, password_hash: str | None) -> bool:
        calls.append(password_hash)
        return False

    monkeypatch.setattr(foundation_services, "verify_password", tracked_verify)
    monkeypatch.setattr(platform_services, "verify_password", tracked_verify)
    response = client.post(endpoint, json={"email": email, "password": "wrong"})
    assert response.status_code == 401
    assert calls == [None]


@pytest.mark.parametrize("attempt_number", [1, 2, 3, 4])
def test_tenant_counter_each_prelock_attempt(client, db, protected_accounts, attempt_number):
    user = protected_accounts[1]
    for _ in range(attempt_number):
        assert _tenant(client, password="wrong").status_code == 401
    db.refresh(user)
    assert user.failed_login_attempts == attempt_number
    assert user.auto_locked_until is None


@pytest.mark.parametrize("attempt_number", [1, 2])
def test_platform_counter_each_prelock_attempt(client, db, protected_accounts, attempt_number):
    platform = protected_accounts[3]
    for _ in range(attempt_number):
        assert _platform(client, platform.email, "wrong").status_code == 401
    db.refresh(platform)
    assert platform.failed_login_attempts == attempt_number
    assert platform.auto_locked_until is None


@pytest.mark.parametrize("attempt_number", list(range(1, 11)))
def test_organization_root_never_auto_locks_at_each_attempt(client, db, protected_accounts, attempt_number):
    root = protected_accounts[2]
    for _ in range(attempt_number):
        _attempts.clear()
        assert _tenant(client, root.email, "wrong").status_code == 401
    db.refresh(root)
    assert root.failed_login_attempts == attempt_number
    assert root.auto_locked_until is None


@pytest.mark.parametrize("field_name,expected", [
    ("login_max_attempts", 5),
    ("login_lockout_minutes", 15),
    ("login_rate_limit", 10),
    ("platform_login_max_attempts", 3),
    ("platform_login_lockout_minutes", 30),
    ("platform_login_rate_limit", 5),
])
def test_login_protection_default_configuration(field_name, expected):
    assert getattr(settings, field_name) == expected


@pytest.mark.parametrize("model,field_name", [
    (User, "failed_login_attempts"),
    (User, "auto_locked_until"),
    (User, "last_failed_login_at"),
    (PlatformAccount, "failed_login_attempts"),
    (PlatformAccount, "auto_locked_until"),
    (PlatformAccount, "last_failed_login_at"),
])
def test_login_protection_columns_exist(model, field_name):
    assert field_name in model.__table__.columns


@pytest.mark.parametrize("email,password", [
    ("absent-one@example.com", "wrong-one"),
    ("absent-two@example.com", "wrong-two"),
    (" ABSENT-THREE@EXAMPLE.COM ", "wrong-three"),
])
def test_unknown_tenant_identities_always_use_generic_response(client, protected_accounts, email, password):
    response = _tenant(client, email, password)
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials."}
