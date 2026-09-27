"""HTTP verification for safe organization role assignment (T01-T38)."""

from datetime import datetime, timezone

import pytest

from app.core.security import hash_password
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.domain.permission_catalog import PERMISSION_BY_CODE
from app.foundation.infrastructure.models import Organization, Permission, Role, RolePermission, User, UserRole


PASSWORD = "TestPassword123!"


def _login(client, email):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _permission(db, org, code):
    definition = PERMISSION_BY_CODE[code]
    permission = Permission(organization_id=org.id, code=code, name=definition.name_en, description=definition.description_en, module_name=definition.module, resource_name=definition.resource, action_name=definition.action)
    db.add(permission); db.flush(); return permission


def _role(db, org, code, permission_codes=(), system=False, protected=False):
    role = Role(organization_id=org.id, code=code, name=code.replace("_", " ").title(), is_system=system, is_protected=protected, is_editable=not system)
    db.add(role); db.flush()
    for permission_code in permission_codes:
        permission = db.query(Permission).filter_by(organization_id=org.id, code=permission_code).first() or _permission(db, org, permission_code)
        db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    db.flush(); return role


def _user(db, org, email, root=False):
    user = User(organization_id=org.id, full_name=email.split("@")[0], email=email, password_hash=hash_password(PASSWORD), status=UserStatus.ACTIVE, is_organization_root=root)
    db.add(user); db.flush(); return user


@pytest.fixture
def safety(client, db):
    org_a = Organization(name="Org A", code="ROLE-SAFE-A", status=OrganizationStatus.ACTIVE, timezone="UTC")
    org_b = Organization(name="Org B", code="ROLE-SAFE-B", status=OrganizationStatus.ACTIVE, timezone="UTC")
    db.add_all([org_a, org_b]); db.flush()
    management = ("foundation:user_roles:write", "foundation:users:read", "foundation:roles:read", "commercial:customers:read", "commercial:customers:update")
    caller_role = _role(db, org_a, "caller_admin", management)
    low_role = _role(db, org_a, "low_role", ("commercial:customers:read", "commercial:customers:update"))
    high_role = _role(db, org_a, "high_role", ("commercial:customers:read", "commercial:customers:update", "commercial:customers:delete"))
    custom_role = _role(db, org_a, "custom_role", ("commercial:customers:read",))
    org_admin = _role(db, org_a, "organization_admin", tuple(management) + ("commercial:customers:delete",), True, True)
    foreign_role = _role(db, org_b, "foreign_role", ())
    caller = _user(db, org_a, "caller@example.com")
    target = _user(db, org_a, "target@example.com")
    root = _user(db, org_a, "root@example.com", True)
    other_admin = _user(db, org_a, "other@example.com")
    foreign_user = _user(db, org_b, "foreign@example.com")
    db.add_all([
        UserRole(user_id=caller.id, role_id=caller_role.id), UserRole(user_id=other_admin.id, role_id=caller_role.id),
        UserRole(user_id=root.id, role_id=org_admin.id, assigned_by=None),
    ])
    db.commit()
    return {"client": client, "db": db, "org": org_a, "caller": caller, "target": target, "root": root, "other": other_admin, "foreign_user": foreign_user, "low": low_role, "high": high_role, "custom": custom_role, "org_admin": org_admin, "foreign_role": foreign_role, "caller_headers": _login(client, caller.email), "root_headers": _login(client, root.email), "target_headers": _login(client, target.email)}


def _assign(s, target, role, headers=None):
    return s["client"].post(f"/api/v1/admin/users/{target.id}/roles", headers=headers or s["caller_headers"], json={"role_id": str(role.id)})


def _remove(s, target, role, headers=None):
    return s["client"].delete(f"/api/v1/admin/users/{target.id}/roles/{role.id}", headers=headers or s["caller_headers"])


def test_t01_assign_same_org_role(safety): assert _assign(safety, safety["target"], safety["low"]).status_code == 201
def test_t02_assign_foreign_role_is_hidden_as_404(safety):
    r = _assign(safety, safety["target"], safety["foreign_role"]); assert r.status_code == 404 and r.json() == {"detail": "Role not found."}
def test_t03_generic_role_lookup_is_scoped(safety): assert safety["client"].get(f"/api/v1/admin/roles/{safety['foreign_role'].id}", headers=safety["caller_headers"]).status_code == 404
def test_t04_remove_foreign_role_is_hidden_as_404(safety): assert _remove(safety, safety["target"], safety["foreign_role"]).status_code == 404
def test_t05_admin_assigns_other_user(safety): assert _assign(safety, safety["target"], safety["low"]).status_code == 201
def test_t06_self_assignment_blocked(safety):
    r = _assign(safety, safety["caller"], safety["low"]); assert r.status_code == 403 and r.json()["code"] == "SELF_ROLE_ASSIGNMENT"
def test_t07_self_removal_blocked(safety):
    r = _remove(safety, safety["caller"], safety["caller"].user_roles[0].role); assert r.status_code == 403 and r.json()["code"] == "SELF_ROLE_REMOVAL"
def test_t08_assignable_roles_for_self_empty(safety):
    b = safety["client"].get(f"/api/v1/admin/users/{safety['caller'].id}/assignable-roles", headers=safety["caller_headers"]).json(); assert b["is_self"] and b["assignable_roles"] == []
def test_t09_root_role_removal_blocked(safety):
    r = _remove(safety, safety["root"], safety["org_admin"]); assert r.status_code == 403 and r.json()["code"] == "CANNOT_REMOVE_ROOT_ROLE"
def test_t10_custom_role_removal_from_root_blocked(safety):
    safety["db"].add(UserRole(user_id=safety["root"].id, role_id=safety["custom"].id)); safety["db"].commit(); assert _remove(safety, safety["root"], safety["custom"]).status_code == 403
def test_t11_additional_role_can_be_assigned_to_root(safety): assert _assign(safety, safety["root"], safety["low"]).status_code == 201
def test_t12_root_protection_applies_to_other_admin(safety): assert _remove(safety, safety["root"], safety["org_admin"]).status_code == 403
def test_t13_equal_permissions_role_assignment_allowed(safety): assert _assign(safety, safety["target"], safety["low"]).status_code == 201
def test_t14_escalating_role_assignment_blocked(safety):
    r = _assign(safety, safety["target"], safety["high"]); assert r.status_code == 403 and r.json()["code"] == "PRIVILEGE_ESCALATION"
def test_t15_escalation_response_lists_permissions(safety): assert "commercial:customers:delete" in _assign(safety, safety["target"], safety["high"]).json()["escalated_permissions"]
def test_t16_root_bypasses_escalation(safety): assert _assign(safety, safety["target"], safety["high"], safety["root_headers"]).status_code == 201
def test_t17_assignable_filters_escalation(safety):
    ids = {r["id"] for r in safety["client"].get(f"/api/v1/admin/users/{safety['target'].id}/assignable-roles", headers=safety["caller_headers"]).json()["assignable_roles"]}; assert str(safety["low"].id) in ids and str(safety["high"].id) not in ids
def test_t18_only_root_assigns_organization_admin(safety): assert _assign(safety, safety["target"], safety["org_admin"]).status_code == 403
def test_t19_duplicate_assignment_returns_409(safety):
    assert _assign(safety, safety["target"], safety["low"]).status_code == 201; r = _assign(safety, safety["target"], safety["low"]); assert r.status_code == 409 and r.json()["code"] == "ROLE_ALREADY_ASSIGNED"
def test_t20_remove_unassigned_returns_404(safety):
    r = _remove(safety, safety["target"], safety["low"]); assert r.status_code == 404 and r.json()["code"] == "ROLE_NOT_ASSIGNED"
def test_t21_assignment_records_assigner(safety):
    _assign(safety, safety["target"], safety["low"]); row = safety["db"].query(UserRole).filter_by(user_id=safety["target"].id, role_id=safety["low"].id).one(); assert row.assigned_by == safety["caller"].id
def test_t22_assignment_records_time(safety):
    before = datetime.now(timezone.utc); _assign(safety, safety["target"], safety["low"]); row = safety["db"].query(UserRole).filter_by(user_id=safety["target"].id, role_id=safety["low"].id).one(); assert row.assigned_at.replace(tzinfo=row.assigned_at.tzinfo or timezone.utc) >= before
def test_t23_role_list_includes_metadata(safety):
    _assign(safety, safety["target"], safety["low"]); b = safety["client"].get(f"/api/v1/admin/users/{safety['target'].id}/roles", headers=safety["caller_headers"]).json()["roles"][0]; assert b["assigned_by"]["id"] == str(safety["caller"].id) and b["assigned_at"]
def test_t24_provisioned_assignment_is_system_attributed(safety):
    b = safety["client"].get(f"/api/v1/admin/users/{safety['root'].id}/roles", headers=safety["caller_headers"]).json()["roles"][0]; assert b["assigned_by"] is None and b["assigned_at"]
def test_t25_assignable_excludes_already_assigned(safety):
    _assign(safety, safety["target"], safety["low"]); ids = {r["id"] for r in safety["client"].get(f"/api/v1/admin/users/{safety['target'].id}/assignable-roles", headers=safety["caller_headers"]).json()["assignable_roles"]}; assert str(safety["low"].id) not in ids
def test_t26_assignable_excludes_escalation(safety):
    ids = {r["id"] for r in safety["client"].get(f"/api/v1/admin/users/{safety['target'].id}/assignable-roles", headers=safety["caller_headers"]).json()["assignable_roles"]}; assert str(safety["high"].id) not in ids
def test_t27_root_sees_all_unassigned_roles(safety):
    b = safety["client"].get(f"/api/v1/admin/users/{safety['target'].id}/assignable-roles", headers=safety["root_headers"]).json(); assert b["restricted_count"] == 0 and str(safety["high"].id) in {r["id"] for r in b["assignable_roles"]}
def test_t28_self_target_is_empty(safety):
    b = safety["client"].get(f"/api/v1/admin/users/{safety['caller'].id}/assignable-roles", headers=safety["caller_headers"]).json(); assert b["is_self"] and not b["assignable_roles"]
def test_t29_cross_org_target_not_found(safety): assert safety["client"].get(f"/api/v1/admin/users/{safety['foreign_user'].id}/assignable-roles", headers=safety["caller_headers"]).status_code == 404
def test_t30_assign_requires_permission(safety): assert _assign(safety, safety["caller"], safety["low"], safety["target_headers"]).status_code == 403
def test_t31_remove_requires_permission(safety): assert _remove(safety, safety["caller"], safety["caller_role"] if "caller_role" in safety else safety["low"], safety["target_headers"]).status_code == 403
def test_t32_view_roles_requires_users_read(safety): assert safety["client"].get(f"/api/v1/admin/users/{safety['caller'].id}/roles", headers=safety["target_headers"]).status_code == 403
def test_t33_tenant_cannot_enumerate_foreign_role_on_assignment(safety): assert _assign(safety, safety["target"], safety["foreign_role"]).status_code == 404
def test_t34_tenant_cannot_enumerate_foreign_role_on_removal(safety): assert _remove(safety, safety["target"], safety["foreign_role"]).status_code == 404
def test_t35_tenant_cannot_view_foreign_user_roles(safety): assert safety["client"].get(f"/api/v1/admin/users/{safety['foreign_user'].id}/roles", headers=safety["caller_headers"]).status_code == 404
def test_t36_root_assigns_any_role(safety): assert _assign(safety, safety["target"], safety["high"], safety["root_headers"]).status_code == 201
def test_t37_root_assignable_has_no_escalation_filter(safety): assert safety["client"].get(f"/api/v1/admin/users/{safety['target'].id}/assignable-roles", headers=safety["root_headers"]).json()["restricted_count"] == 0
def test_t38_root_self_assignment_still_blocked(safety):
    r = _assign(safety, safety["root"], safety["low"], safety["root_headers"]); assert r.status_code == 403 and r.json()["code"] == "SELF_ROLE_ASSIGNMENT"
