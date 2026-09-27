"""Foundation admin API tests."""

from app.core.security import hash_password
from app.foundation.domain.enums import UserStatus
from app.foundation.infrastructure.models import Permission, Role, RolePermission, UserRole


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _permission(db, organization_id, code: str, name: str = "Permission") -> Permission:
    module_name, resource, action = code.split(":")
    permission = Permission(
        organization_id=organization_id, code=code,
        name=name,
        description=name,
        module_name=module_name,
        resource_name=resource,
        action_name=action,
    )
    db.add(permission)
    db.commit()
    db.refresh(permission)
    return permission


def _role_with_permissions(db, test_org, *codes: str) -> Role:
    role = Role(
        organization_id=test_org.id,
        name="Admin Role",
        code="admin_role",
        description="Admin test role",
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    for code in codes:
        permission = _permission(db, test_org.id, code, code)
        db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    db.commit()
    return role


def _assign_role(db, test_user, role: Role) -> None:
    db.add(UserRole(user_id=test_user.id, role_id=role.id))
    db.commit()


def test_admin_users_requires_read_permission(client, auth_headers):
    response = client.get("/api/v1/admin/users", headers=auth_headers)

    assert response.status_code == 403


def test_auth_me_returns_roles_and_permissions(client, db, test_org, test_user):
    role = _role_with_permissions(db, test_org, "foundation:users:read")
    _assign_role(db, test_user, role)

    headers = _login(client, "test@example.com", "Test1234!")
    response = client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["roles"] == ["admin_role"]
    assert response.json()["permissions"] == ["foundation:users:read"]


def test_admin_users_list_is_scoped_to_current_organization(client, db, test_org, test_user):
    role = _role_with_permissions(db, test_org, "foundation:users:read")
    _assign_role(db, test_user, role)
    other = test_user.__class__(
        organization_id=test_org.id,
        full_name="Other User",
        email="other@example.com",
        password_hash=hash_password("Other1234!"),
        status=UserStatus.ACTIVE,
    )
    db.add(other)
    db.commit()

    headers = _login(client, "test@example.com", "Test1234!")
    response = client.get("/api/v1/admin/users", headers=headers)

    assert response.status_code == 200
    assert {item["email"] for item in response.json()} == {"test@example.com", "other@example.com"}
