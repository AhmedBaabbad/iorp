from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.foundation.domain.permission_catalog import PERMISSIONS
from app.core.security import ALGORITHM, create_access_token, hash_password
from app.core.config import settings
from app.foundation.infrastructure.models import Permission, Role, RolePermission, UserRole
from app.platform.domain.enums import PlatformAccountStatus
from app.platform.infrastructure.models import PlatformAccount


@pytest.fixture
def tenant_headers_with_permissions(client, db, test_org, test_user):
    role = Role(organization_id=test_org.id, name="All Access", code="all_access")
    db.add(role)
    db.flush()
    for item in PERMISSIONS:
        permission = Permission(organization_id=test_org.id, **item)
        db.add(permission)
        db.flush()
        db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    db.add(UserRole(user_id=test_user.id, role_id=role.id))
    db.commit()
    response = client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "Test1234!"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def platform_identity(db):
    account = PlatformAccount(
        full_name="Platform Root",
        email="root@platform.test",
        password_hash=hash_password("PlatformRoot123!"),
        status=PlatformAccountStatus.ACTIVE,
        is_root=True,
        token_version=0,
    )
    db.add(account)
    db.commit()
    token = create_access_token(
        str(account.id),
        {"account_id": str(account.id), "account_type": "platform", "token_version": 0},
    )
    return account, {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "/api/v1/admin/users", None),
        ("get", "/api/v1/commercial/customers", None),
        ("get", "/api/v1/commercial/follow-ups", None),
        ("get", "/api/v1/workforce-members", None),
        ("post", "/api/v1/commercial/customers", {"name": "Blocked"}),
    ],
)
def test_t18_t22_platform_token_cannot_use_tenant_routes(
    client, platform_identity, method, path, body
):
    _, headers = platform_identity
    response = getattr(client, method)(path, headers=headers, json=body) if body else getattr(client, method)(path, headers=headers)
    assert response.status_code == 401


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "/api/v1/platform/organizations", None),
        ("post", "/api/v1/platform/organizations", {}),
        ("post", "/api/v1/platform/change-password", {}),
    ],
)
def test_t23_t25_tenant_token_cannot_use_platform_routes(
    client, tenant_headers_with_permissions, method, path, body
):
    response = getattr(client, method)(path, headers=tenant_headers_with_permissions, json=body) if body is not None else getattr(client, method)(path, headers=tenant_headers_with_permissions)
    assert response.status_code == 401


def test_t26_platform_root_not_in_tenant_user_list(
    client, tenant_headers_with_permissions, platform_identity
):
    account, _ = platform_identity
    response = client.get("/api/v1/admin/users", headers=tenant_headers_with_permissions)
    assert response.status_code == 200
    assert account.email not in {item["email"] for item in response.json()}


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/commercial/customers/eligible-sales-owners",
        "/api/v1/commercial/follow-ups/eligible-assignees",
    ],
)
def test_t27_t28_platform_root_not_in_tenant_selectors(
    client, tenant_headers_with_permissions, platform_identity, path
):
    account, _ = platform_identity
    response = client.get(path, headers=tenant_headers_with_permissions)
    assert response.status_code == 200
    assert account.email not in {item["email"] for item in response.json()}


def test_t29_platform_root_cannot_be_sales_owner(
    client, tenant_headers_with_permissions, platform_identity
):
    account, _ = platform_identity
    response = client.post(
        "/api/v1/commercial/customers",
        headers=tenant_headers_with_permissions,
        json={"name": "Cross Identity", "sales_owner_user_id": str(account.id)},
    )
    assert response.status_code == 400


def test_t30_platform_root_cannot_be_follow_up_assignee(
    client, tenant_headers_with_permissions, platform_identity, test_user
):
    account, _ = platform_identity
    customer = client.post(
        "/api/v1/commercial/customers",
        headers=tenant_headers_with_permissions,
        json={"name": "Tenant Customer", "sales_owner_user_id": str(test_user.id)},
    )
    assert customer.status_code == 201
    response = client.post(
        f"/api/v1/commercial/customers/{customer.json()['id']}/follow-ups",
        headers=tenant_headers_with_permissions,
        json={
            "assigned_user_id": str(account.id),
            "due_date": "2030-01-01T10:00:00Z",
            "priority": "medium",
            "reason": "Identity isolation",
            "notes": "Must be rejected",
        },
    )
    assert response.status_code == 400


def test_t31_platform_root_cannot_link_to_workforce_member(
    client, tenant_headers_with_permissions, platform_identity
):
    account, _ = platform_identity
    member = client.post(
        "/api/v1/workforce-members",
        headers=tenant_headers_with_permissions,
        json={
            "full_name": "Tenant Worker",
            "worker_type": "operator",
            "employment_type": "employee",
        },
    )
    assert member.status_code == 201
    response = client.post(
        f"/api/v1/workforce-members/{member.json()['id']}/link-user",
        headers=tenant_headers_with_permissions,
        json={"user_id": str(account.id)},
    )
    assert response.status_code == 400


def test_t32_legacy_tenant_token_without_account_type_is_rejected(client, test_user):
    token = jwt.encode(
        {"sub": str(test_user.id), "organization_id": str(test_user.organization_id), "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        settings.secret_key,
        algorithm=ALGORITHM,
    )
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_t33_invalid_account_type_is_rejected(client, test_user):
    token = jwt.encode(
        {"sub": str(test_user.id), "account_type": "invalid", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        settings.secret_key,
        algorithm=ALGORITHM,
    )
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_t34_expired_token_is_rejected(client, test_user):
    token = jwt.encode(
        {"sub": str(test_user.id), "account_type": "user", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
        settings.secret_key,
        algorithm=ALGORITHM,
    )
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_t35_wrong_platform_token_version_is_rejected(client, platform_identity):
    account, _ = platform_identity
    token = create_access_token(
        str(account.id),
        {"account_id": str(account.id), "account_type": "platform", "token_version": 99},
    )
    response = client.get("/api/v1/platform/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
