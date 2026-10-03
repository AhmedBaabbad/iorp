"""Service and real-HTTP coverage for organization role governance."""

import pytest
from sqlalchemy import func, select
from uuid import UUID

from app.core.config import settings
from app.core.security import hash_password
from app.core.storage import LocalFileStorage
from app.foundation.api.schemas import RoleCreateRequest, RoleUpdateRequest
from app.foundation.application.services import FoundationService, RoleGovernanceError
from app.foundation.domain.system_roles import SYSTEM_ROLE_BY_CODE, SYSTEM_ROLES, permission_matches
from app.foundation.domain.enums import UserStatus
from app.foundation.infrastructure.models import Organization, Role, RolePermission, User, UserRole
from app.foundation.infrastructure.organization_queries import FoundationOrganizationQueries


ADMIN_PASSWORD = "AdminPassword123!"


def _bootstrap_payload() -> dict:
    return {
        "bootstrap_token": "bootstrap-test-token",
        "platform_root": {"full_name": "Platform Owner", "email": "root@example.com", "password": "RootPassword123!", "password_confirmation": "RootPassword123!"},
        "organization": {"name": "First Organization", "code": "first-org", "timezone": "Asia/Riyadh", "default_locale": "ar"},
        "organization_admin": {"full_name": "Organization Admin", "email": "admin@example.com", "password": ADMIN_PASSWORD, "password_confirmation": ADMIN_PASSWORD},
    }


def _bootstrap(client, db, monkeypatch):
    monkeypatch.setattr(settings, "bootstrap_token", "bootstrap-test-token")
    response = client.post("/api/v1/system/bootstrap/initialize", json=_bootstrap_payload())
    assert response.status_code == 201, response.text
    login = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": ADMIN_PASSWORD})
    assert login.status_code == 200, login.text
    organization = db.scalar(select(Organization).where(Organization.code == "FIRST-ORG"))
    administrator = db.scalar(select(User).where(User.email == "admin@example.com"))
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, organization, administrator


def _role(db, organization, code: str) -> Role:
    return db.scalar(select(Role).where(Role.organization_id == organization.id, Role.code == code))


def _create_custom(client, headers, code: str = "custom_role") -> dict:
    response = client.post("/api/v1/admin/roles", headers=headers, json={"name": "Custom Role", "code": code, "description": "Test role"})
    assert response.status_code == 201, response.text
    return response.json()


def _other_user(db, administrator):
    user = User(organization_id=administrator.organization_id, full_name="Role Target", email="role-target@example.com", password_hash=hash_password("TargetPassword123!"), status=UserStatus.ACTIVE)
    db.add(user); db.commit(); db.refresh(user)
    return user


# Existing service-level coverage
def test_factory_department_catalog_contains_shipping_and_maintenance_managers():
    assert {"factory_manager", "shipping_manager", "maintenance_manager"} <= SYSTEM_ROLE_BY_CODE.keys()
    assert permission_matches("commercial:orders:update", "commercial:*")
    assert permission_matches("production:downtime_events:close", "production:downtime_events:*")


def test_custom_role_defaults_are_safe_and_code_is_unique_per_organization(db, test_org):
    service = FoundationService(db)
    role = service.create_role_for_tenant(test_org.id, RoleCreateRequest(name="Dispatch Coordinator", code="dispatch_coordinator"))
    assert (role.is_system, role.is_protected, role.is_editable) == (False, False, True)
    with pytest.raises(ValueError):
        service.create_role_for_tenant(test_org.id, RoleCreateRequest(name="Duplicate", code="dispatch_coordinator"))


def test_protected_and_system_roles_cannot_be_modified_or_deleted(db, test_org):
    service = FoundationService(db)
    protected = Role(organization_id=test_org.id, name="Organization Administrator", code="organization_admin", is_system=True, is_protected=True, is_editable=False)
    system = Role(organization_id=test_org.id, name="Shipping Manager", code="shipping_manager", is_system=True, is_protected=False, is_editable=False)
    db.add_all([protected, system]); db.commit()
    with pytest.raises(RoleGovernanceError, match="cannot be edited"):
        service.update_role_for_tenant(test_org.id, system.id, RoleUpdateRequest(name="Changed"))
    with pytest.raises(RoleGovernanceError) as protected_error:
        service.delete_role_for_tenant(test_org.id, protected.id)
    assert protected_error.value.code == "ROLE_IS_PROTECTED"
    with pytest.raises(RoleGovernanceError) as system_error:
        service.delete_role_for_tenant(test_org.id, system.id)
    assert system_error.value.code == "SYSTEM_ROLE_CANNOT_BE_DELETED"


def test_assigned_custom_role_cannot_be_deleted(db, test_org, test_user):
    service = FoundationService(db)
    role = service.create_role_for_tenant(test_org.id, RoleCreateRequest(name="Custom", code="custom_role"))
    db.add(UserRole(user_id=test_user.id, role_id=role.id)); db.commit()
    with pytest.raises(RoleGovernanceError) as error:
        service.delete_role_for_tenant(test_org.id, role.id)
    assert error.value.code == "ROLE_HAS_ASSIGNED_USERS" and error.value.user_count == 1


def test_unassigned_custom_role_can_be_updated_and_deleted(db, test_org):
    service = FoundationService(db)
    role = service.create_role_for_tenant(test_org.id, RoleCreateRequest(name="Custom", code="custom_role"))
    updated = service.update_role_for_tenant(test_org.id, role.id, RoleUpdateRequest(name="Updated", code="updated_role", description="Updated description"))
    assert (updated.name, updated.code) == ("Updated", "updated_role")
    service.delete_role_for_tenant(test_org.id, role.id)
    assert db.get(Role, role.id) is None


# HTTP-level protection
def test_http_01_delete_protected_organization_admin(client, db, monkeypatch):
    headers, org, _ = _bootstrap(client, db, monkeypatch)
    response = client.delete(f"/api/v1/admin/roles/{_role(db, org, 'organization_admin').id}", headers=headers)
    assert response.status_code == 403 and response.json()["code"] == "ROLE_IS_PROTECTED"


def test_http_02_patch_protected_role_code(client, db, monkeypatch):
    headers, org, _ = _bootstrap(client, db, monkeypatch)
    response = client.patch(f"/api/v1/admin/roles/{_role(db, org, 'organization_admin').id}", headers=headers, json={"code": "hacked"})
    assert response.status_code == 403 and response.json()["code"] == "ROLE_NOT_EDITABLE"


def test_http_03_delete_non_protected_system_role(client, db, monkeypatch):
    headers, org, _ = _bootstrap(client, db, monkeypatch)
    response = client.delete(f"/api/v1/admin/roles/{_role(db, org, 'sales_rep').id}", headers=headers)
    assert response.status_code == 403 and response.json()["code"] == "SYSTEM_ROLE_CANNOT_BE_DELETED"


# HTTP-level custom CRUD
def test_http_04_create_custom_role_flags_are_safe(client, db, monkeypatch):
    headers, _, _ = _bootstrap(client, db, monkeypatch)
    body = _create_custom(client, headers)
    assert (body["is_system"], body["is_protected"], body["is_editable"]) == (False, False, True)


def test_http_05_update_custom_role_code_and_name(client, db, monkeypatch):
    headers, _, _ = _bootstrap(client, db, monkeypatch)
    role = _create_custom(client, headers)
    response = client.patch(f"/api/v1/admin/roles/{role['id']}", headers=headers, json={"code": "new_code", "name": "New"})
    assert response.status_code == 200
    assert (response.json()["code"], response.json()["name"]) == ("new_code", "New")


def test_http_06_delete_unassigned_custom_role(client, db, monkeypatch):
    headers, _, _ = _bootstrap(client, db, monkeypatch)
    role = _create_custom(client, headers)
    assert client.delete(f"/api/v1/admin/roles/{role['id']}", headers=headers).status_code == 204


# User dependency
def test_http_07_assigned_custom_role_delete_conflict(client, db, monkeypatch):
    headers, _, admin = _bootstrap(client, db, monkeypatch)
    target = _other_user(db, admin)
    role = _create_custom(client, headers)
    assigned = client.post(f"/api/v1/admin/users/{target.id}/roles", headers=headers, json={"role_id": role["id"]})
    assert assigned.status_code == 201
    response = client.delete(f"/api/v1/admin/roles/{role['id']}", headers=headers)
    assert response.status_code == 409
    assert response.json()["code"] == "ROLE_HAS_ASSIGNED_USERS" and response.json()["user_count"] == 1


def test_http_08_delete_after_removing_role_assignment(client, db, monkeypatch):
    headers, _, admin = _bootstrap(client, db, monkeypatch)
    target = _other_user(db, admin)
    role = _create_custom(client, headers)
    assert client.post(f"/api/v1/admin/users/{target.id}/roles", headers=headers, json={"role_id": role["id"]}).status_code == 201
    assert client.delete(f"/api/v1/admin/users/{target.id}/roles/{role['id']}", headers=headers).status_code == 200
    assert client.delete(f"/api/v1/admin/roles/{role['id']}", headers=headers).status_code == 204


# Deletion impact
def test_http_09_deletion_impact_with_assigned_users(client, db, monkeypatch):
    headers, _, admin = _bootstrap(client, db, monkeypatch)
    target = _other_user(db, admin)
    role = _create_custom(client, headers)
    client.post(f"/api/v1/admin/users/{target.id}/roles", headers=headers, json={"role_id": role["id"]})
    body = client.get(f"/api/v1/admin/roles/{role['id']}/deletion-impact", headers=headers).json()
    assert body["can_delete"] is False and body["assigned_user_count"] == 1


def test_http_10_deletion_impact_without_users(client, db, monkeypatch):
    headers, _, _ = _bootstrap(client, db, monkeypatch)
    role = _create_custom(client, headers)
    body = client.get(f"/api/v1/admin/roles/{role['id']}/deletion-impact", headers=headers).json()
    assert body["can_delete"] is True and body["assigned_user_count"] == 0


def test_http_11_system_role_deletion_impact(client, db, monkeypatch):
    headers, org, _ = _bootstrap(client, db, monkeypatch)
    role = _role(db, org, "sales_rep")
    body = client.get(f"/api/v1/admin/roles/{role.id}/deletion-impact", headers=headers).json()
    assert body["can_delete"] is False and "SYSTEM" in body["reason_code"]


# Permission enforcement
def test_http_12_create_requires_roles_write(client, auth_headers):
    assert client.post("/api/v1/admin/roles", headers=auth_headers, json={"name": "Denied", "code": "denied"}).status_code == 403


def test_http_13_delete_requires_roles_write(client, db, test_org, auth_headers):
    role = FoundationService(db).create_role_for_tenant(test_org.id, RoleCreateRequest(name="Target", code="target"))
    assert client.delete(f"/api/v1/admin/roles/{role.id}", headers=auth_headers).status_code == 403


def test_http_14_roles_write_allows_create(client, db, monkeypatch):
    headers, _, _ = _bootstrap(client, db, monkeypatch)
    assert client.post("/api/v1/admin/roles", headers=headers, json={"name": "Allowed", "code": "allowed"}).status_code == 201


# Cross-organization isolation
def _second_organization(client, headers):
    payload = {"organization": {"name": "Second Organization", "code": "second-org", "timezone": "UTC", "default_locale": "en"}, "organization_admin": {"full_name": "Second Admin", "email": "second@example.com", "password": ADMIN_PASSWORD, "password_confirmation": ADMIN_PASSWORD}}
    response = client.post("/api/v1/platform/organizations", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _platform_headers(client):
    login = client.post("/api/v1/platform/login", json={"email": "root@example.com", "password": "RootPassword123!"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_http_15_cross_org_get_returns_404(client, db, monkeypatch):
    tenant_headers, _, _ = _bootstrap(client, db, monkeypatch)
    second = _second_organization(client, _platform_headers(client))
    foreign_role = _role(db, db.get(Organization, UUID(second["organization"]["id"])), "viewer")
    assert client.get(f"/api/v1/admin/roles/{foreign_role.id}", headers=tenant_headers).status_code == 404


def test_http_16_cross_org_delete_returns_404(client, db, monkeypatch):
    tenant_headers, _, _ = _bootstrap(client, db, monkeypatch)
    second = _second_organization(client, _platform_headers(client))
    foreign_role = _role(db, db.get(Organization, UUID(second["organization"]["id"])), "viewer")
    assert client.delete(f"/api/v1/admin/roles/{foreign_role.id}", headers=tenant_headers).status_code == 404


def test_http_17_cross_org_patch_returns_404(client, db, monkeypatch):
    tenant_headers, _, _ = _bootstrap(client, db, monkeypatch)
    second = _second_organization(client, _platform_headers(client))
    foreign_role = _role(db, db.get(Organization, UUID(second["organization"]["id"])), "viewer")
    assert client.patch(f"/api/v1/admin/roles/{foreign_role.id}", headers=tenant_headers, json={"name": "Hacked"}).status_code == 404


# Provisioning and schema safety
def test_http_18_system_role_provisioning_is_idempotent(client, db, monkeypatch, tmp_path):
    _, org, _ = _bootstrap(client, db, monkeypatch)
    query = FoundationOrganizationQueries(db, LocalFileStorage(str(tmp_path)))
    permissions = query._get_or_create_permissions()
    before_grants = db.scalar(select(func.count()).select_from(RolePermission))
    query._seed_roles(org, permissions); db.commit()
    assert db.scalar(select(func.count()).select_from(Role).where(Role.organization_id == org.id)) == len(SYSTEM_ROLES)
    assert db.scalar(select(func.count()).select_from(RolePermission)) == before_grants


def test_http_19_create_ignores_is_system(client, db, monkeypatch):
    headers, _, _ = _bootstrap(client, db, monkeypatch)
    response = client.post("/api/v1/admin/roles", headers=headers, json={"name": "Safe", "code": "safe_system", "is_system": True})
    assert response.status_code == 201 and response.json()["is_system"] is False


def test_http_20_create_ignores_is_protected(client, db, monkeypatch):
    headers, _, _ = _bootstrap(client, db, monkeypatch)
    response = client.post("/api/v1/admin/roles", headers=headers, json={"name": "Safe", "code": "safe_protected", "is_protected": True})
    assert response.status_code == 201 and response.json()["is_protected"] is False
