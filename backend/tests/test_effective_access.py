"""ORG-RBAC-005 effective-access computation and read-only endpoints."""

from app.core.security import hash_password
from app.foundation.application.effective_access import compute_effective_access
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.domain.permission_catalog import ALL_TENANT_PERMISSIONS
from app.foundation.infrastructure.models import Organization, Permission, Role, RolePermission, User, UserRole


PASSWORD = "Test1234!"


def _login(client, email):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _seed(db):
    org = Organization(name="Access Org", code="ACCESS", status=OrganizationStatus.ACTIVE, timezone="UTC", default_locale="en")
    other_org = Organization(name="Other Org", code="OTHER-ACCESS", status=OrganizationStatus.ACTIVE, timezone="UTC")
    db.add_all([org, other_org]); db.flush()
    definitions = {item.code: item for item in ALL_TENANT_PERMISSIONS}
    permissions = {}
    for item in ALL_TENANT_PERMISSIONS:
        row = Permission(organization_id=org.id, code=item.code, name=item.name_en, description=item.description_en, module_name=item.module, resource_name=item.resource, action_name=item.action)
        db.add(row); permissions[item.code] = row
    db.flush()
    root = User(organization_id=org.id, full_name="Root", email="root@access.example.com", password_hash=hash_password(PASSWORD), status=UserStatus.ACTIVE, is_organization_root=True)
    user = User(organization_id=org.id, full_name="Agent", email="agent@access.example.com", password_hash=hash_password(PASSWORD), status=UserStatus.ACTIVE)
    empty = User(organization_id=org.id, full_name="Empty", email="empty@access.example.com", password_hash=hash_password(PASSWORD), status=UserStatus.ACTIVE)
    outsider = User(organization_id=other_org.id, full_name="Outsider", email="outside@access.example.com", password_hash=hash_password(PASSWORD), status=UserStatus.ACTIVE)
    db.add_all([root, user, empty, outsider]); db.flush()
    own = Role(organization_id=org.id, name="Own Reader", code="own_reader")
    broad = Role(organization_id=org.id, name="Broad Reader", code="broad_reader", is_system=True)
    db.add_all([own, broad]); db.flush()
    scoped_code = next(code for code, item in definitions.items() if item.scopable)
    non_scoped_code = next(code for code, item in definitions.items() if not item.scopable)
    db.add_all([
        RolePermission(role_id=own.id, permission_id=permissions[scoped_code].id, scope="own"),
        RolePermission(role_id=own.id, permission_id=permissions[non_scoped_code].id, scope="own"),
        RolePermission(role_id=broad.id, permission_id=permissions[scoped_code].id, scope="organization"),
        UserRole(user_id=user.id, role_id=own.id), UserRole(user_id=user.id, role_id=broad.id),
    ])
    db.commit()
    return locals()


def test_union_scope_sources_grouping_and_missing(db):
    data = _seed(db)
    report = compute_effective_access(db, data["user"].id, data["org"].id)
    effective = {item.code: item for items in report.permissions_by_module.values() for item in items}
    scoped = effective[data["scoped_code"]]
    assert report.total_roles == 2 and report.total_permissions == 2
    assert scoped.effective_scope == "organization"
    assert len(scoped.granted_by_roles) == 2
    assert {"role_code", "role_name", "scope"} <= scoped.granted_by_roles[0].keys()
    assert effective[data["non_scoped_code"]].effective_scope == "organization"
    assert all(items == sorted(items, key=lambda item: (item.resource, item.action)) for items in report.permissions_by_module.values())
    assert [item["code"] for item in report.missing_permissions] == sorted(item["code"] for item in report.missing_permissions)
    assert report.total_permissions + len(report.missing_permissions) == len(ALL_TENANT_PERMISSIONS)


def test_no_roles_and_root_bypass(db):
    data = _seed(db)
    empty = compute_effective_access(db, data["empty"].id, data["org"].id)
    assert empty.total_permissions == 0 and len(empty.missing_permissions) == len(ALL_TENANT_PERMISSIONS)
    root = compute_effective_access(db, data["root"].id, data["org"].id)
    permissions = [item for items in root.permissions_by_module.values() for item in items]
    assert root.total_permissions == len(ALL_TENANT_PERMISSIONS)
    assert root.missing_permissions == []
    assert all(item.is_root_bypass and item.effective_scope == "organization" and item.granted_by_roles == [] for item in permissions)


def test_admin_and_self_endpoints_are_localized_and_tenant_scoped(client, db):
    data = _seed(db)
    root_headers = _login(client, data["root"].email)
    admin = client.get(f"/api/v1/admin/users/{data['user'].id}/effective-access", headers={**root_headers, "Accept-Language": "en"})
    assert admin.status_code == 200
    body = admin.json()
    assert body["user_id"] == str(data["user"].id) and body["missing_permissions_count"] > 0
    assert all("name" in item and "description" in item for items in body["permissions_by_module"].values() for item in items)
    denied = client.get(f"/api/v1/admin/users/{data['outsider'].id}/effective-access", headers=root_headers)
    assert denied.status_code == 404
    self_response = client.get("/api/v1/auth/me/effective-access", headers=_login(client, data["user"].email))
    assert self_response.status_code == 200 and self_response.json()["user_id"] == str(data["user"].id)


def test_admin_endpoint_requires_users_read(client, db):
    data = _seed(db)
    response = client.get(f"/api/v1/admin/users/{data['empty'].id}/effective-access", headers=_login(client, data["user"].email))
    assert response.status_code == 403
