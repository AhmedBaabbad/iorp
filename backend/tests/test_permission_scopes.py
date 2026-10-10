"""ORG-RBAC-004 -- row-level scope model (own/team/organization)."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.commercial.domain.enums import FollowUpPriority, FollowUpStatus
from app.commercial.infrastructure.models import Customer, FollowUp
from app.core.interfaces.authorization_policy import AccessScope
from app.core.security import hash_password
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.domain.permission_catalog import ALL_TENANT_PERMISSIONS, SCOPABLE_PERMISSIONS
from app.foundation.infrastructure.models import (
    Organization,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)


PASSWORD = "Test1234!"


def _grant(db, role, permission, scope="organization"):
    db.add(RolePermission(role_id=role.id, permission_id=permission.id, scope=scope))


@pytest.fixture
def scoped_env(client, db):
    org = Organization(name="Scope Org", code="SCOPE-ORG", status=OrganizationStatus.ACTIVE, timezone="UTC")
    db.add(org)
    db.flush()

    permissions: dict[str, Permission] = {}
    for item in ALL_TENANT_PERMISSIONS:
        if item.module == "platform":
            continue
        permission = Permission(
            organization_id=org.id, code=item.code, name=item.name_en,
            description=item.description_en, module_name=item.module,
            resource_name=item.resource, action_name=item.action,
        )
        db.add(permission)
        permissions[item.code] = permission
    db.flush()

    root = User(organization_id=org.id, full_name="Root User", email="root@scope.example.com", password_hash=hash_password(PASSWORD), status=UserStatus.ACTIVE, is_organization_root=True)
    owner = User(organization_id=org.id, full_name="Owner Rep", email="owner@scope.example.com", password_hash=hash_password(PASSWORD), status=UserStatus.ACTIVE)
    other = User(organization_id=org.id, full_name="Other Rep", email="other@scope.example.com", password_hash=hash_password(PASSWORD), status=UserStatus.ACTIVE)
    org_wide = User(organization_id=org.id, full_name="Org Wide Manager", email="orgwide@scope.example.com", password_hash=hash_password(PASSWORD), status=UserStatus.ACTIVE)
    db.add_all([root, owner, other, org_wide])
    db.flush()

    role_admin = Role(organization_id=org.id, name="Admin", code="admin_role")
    role_own = Role(organization_id=org.id, name="Own Scope Rep", code="own_scope_rep")
    role_org = Role(organization_id=org.id, name="Org Scope Manager", code="org_scope_manager")
    role_system = Role(organization_id=org.id, name="System Role", code="system_role", is_system=True, is_editable=False)
    db.add_all([role_admin, role_own, role_org, role_system])
    db.flush()

    for permission in permissions.values():
        _grant(db, role_admin, permission, "organization")
    _grant(db, role_own, permissions["commercial:customers:read"], "own")
    _grant(db, role_own, permissions["commercial:customers:update"], "own")
    _grant(db, role_own, permissions["commercial:customers:create"], "organization")
    _grant(db, role_own, permissions["commercial:follow_ups:read"], "own")
    _grant(db, role_own, permissions["commercial:follow_ups:create"], "organization")
    _grant(db, role_own, permissions["commercial:follow_ups:update"], "own")
    _grant(db, role_own, permissions["commercial:interactions:read"], "own")
    _grant(db, role_org, permissions["commercial:customers:read"], "organization")
    _grant(db, role_org, permissions["commercial:follow_ups:read"], "organization")
    _grant(db, role_system, permissions["commercial:customers:read"], "organization")
    db.flush()

    db.add_all([
        UserRole(user_id=root.id, role_id=role_admin.id),
        UserRole(user_id=owner.id, role_id=role_own.id),
        UserRole(user_id=other.id, role_id=role_own.id),
        UserRole(user_id=org_wide.id, role_id=role_org.id),
    ])

    customer_owner = Customer(organization_id=org.id, customer_code="CUST-OWN", name="Owner's Customer", created_by_user_id=owner.id, sales_owner_user_id=owner.id)
    customer_other = Customer(organization_id=org.id, customer_code="CUST-OTH", name="Other's Customer", created_by_user_id=other.id, sales_owner_user_id=other.id)
    db.add_all([customer_owner, customer_other])
    db.flush()

    follow_owner = FollowUp(customer_id=customer_owner.id, assigned_user_id=owner.id, created_by_user_id=owner.id, due_date=datetime(2030, 1, 1, tzinfo=timezone.utc), priority=FollowUpPriority.MEDIUM, status=FollowUpStatus.PENDING, reason="owner's")
    follow_other = FollowUp(customer_id=customer_other.id, assigned_user_id=other.id, created_by_user_id=other.id, due_date=datetime(2030, 1, 1, tzinfo=timezone.utc), priority=FollowUpPriority.MEDIUM, status=FollowUpStatus.PENDING, reason="other's")
    db.add_all([follow_owner, follow_other])
    db.commit()

    def login(email):
        response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return {
        "org": org, "root": root, "owner": owner, "other": other, "org_wide": org_wide,
        "role_own": role_own, "role_org": role_org, "role_system": role_system,
        "customer_owner": customer_owner, "customer_other": customer_other,
        "follow_owner": follow_owner, "follow_other": follow_other,
        "headers_root": login(root.email), "headers_owner": login(owner.email),
        "headers_other": login(other.email), "headers_org_wide": login(org_wide.email),
        "db": db, "permissions": permissions,
    }


# ── Scope Column ─────────────────────────────────────────────────────────────

def test_t01_role_permission_has_scope_column():
    assert "scope" in RolePermission.__table__.columns


def test_t02_default_scope_is_organization(scoped_env):
    data = scoped_env
    rp = data["db"].scalar(select(RolePermission).where(RolePermission.role_id == data["role_org"].id).limit(1))
    assert rp.scope in ("organization",)


def test_t04_assign_rejects_invalid_scope(client, scoped_env):
    data = scoped_env
    resp = client.post(
        f"/api/v1/admin/roles/{data['role_own'].id}/permissions",
        headers=data["headers_root"],
        json={"permission_code": "commercial:customers:read", "scope": "bogus"},
    )
    assert resp.status_code == 422


# ── Scope Resolver ────────────────────────────────────────────────────────────

def test_t05_single_role_own_scope_resolves_own(scoped_env):
    from app.core.authorization.scope_resolver import resolve_effective_scope
    data = scoped_env
    scope = resolve_effective_scope(data["db"], data["owner"].id, data["org"].id, "commercial:customers:read", False)
    assert scope == AccessScope.OWN


def test_t06_single_role_organization_scope_resolves_organization(scoped_env):
    from app.core.authorization.scope_resolver import resolve_effective_scope
    data = scoped_env
    scope = resolve_effective_scope(data["db"], data["org_wide"].id, data["org"].id, "commercial:customers:read", False)
    assert scope == AccessScope.ORGANIZATION


def test_t07_broadest_scope_wins_across_roles(scoped_env):
    from app.core.authorization.scope_resolver import resolve_effective_scope
    data = scoped_env
    data["db"].add(UserRole(user_id=data["owner"].id, role_id=data["role_org"].id))
    data["db"].commit()
    scope = resolve_effective_scope(data["db"], data["owner"].id, data["org"].id, "commercial:customers:read", False)
    assert scope == AccessScope.ORGANIZATION


def test_t08_organization_root_always_bypasses(scoped_env):
    from app.core.authorization.scope_resolver import resolve_effective_scope
    data = scoped_env
    scope = resolve_effective_scope(data["db"], data["root"].id, data["org"].id, "commercial:customers:read", True)
    assert scope == AccessScope.ORGANIZATION


def test_t09_permission_not_granted_falls_back_to_own(scoped_env):
    from app.core.authorization.scope_resolver import resolve_effective_scope
    data = scoped_env
    scope = resolve_effective_scope(data["db"], data["owner"].id, data["org"].id, "commercial:orders:read", False)
    assert scope == AccessScope.OWN


# ── Own Scope -- Customer List ───────────────────────────────────────────────

def test_t10_t11_own_scope_customer_list_shows_only_own(client, scoped_env):
    data = scoped_env
    response = client.get("/api/v1/commercial/customers", headers=data["headers_owner"])
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert ids == {str(data["customer_owner"].id)}


def test_t12_root_sees_all_customers(client, scoped_env):
    data = scoped_env
    response = client.get("/api/v1/commercial/customers", headers=data["headers_root"])
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert {str(data["customer_owner"].id), str(data["customer_other"].id)} <= ids


def test_t13_organization_scope_sees_all_customers(client, scoped_env):
    data = scoped_env
    response = client.get("/api/v1/commercial/customers", headers=data["headers_org_wide"])
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert {str(data["customer_owner"].id), str(data["customer_other"].id)} <= ids


# ── Own Scope -- Customer Get By ID ──────────────────────────────────────────

def test_t14_own_scope_can_get_own_customer(client, scoped_env):
    data = scoped_env
    response = client.get(f"/api/v1/commercial/customers/{data['customer_owner'].id}", headers=data["headers_owner"])
    assert response.status_code == 200


def test_t15_own_scope_gets_404_for_others_customer(client, scoped_env):
    data = scoped_env
    response = client.get(f"/api/v1/commercial/customers/{data['customer_other'].id}", headers=data["headers_owner"])
    assert response.status_code == 404


def test_t16_root_can_get_any_customer(client, scoped_env):
    data = scoped_env
    response = client.get(f"/api/v1/commercial/customers/{data['customer_other'].id}", headers=data["headers_root"])
    assert response.status_code == 200


def test_t17_organization_scope_can_get_any_customer(client, scoped_env):
    data = scoped_env
    response = client.get(f"/api/v1/commercial/customers/{data['customer_owner'].id}", headers=data["headers_org_wide"])
    assert response.status_code == 200


# ── Own Scope -- Follow-ups ──────────────────────────────────────────────────

def test_t18_own_scope_follow_ups_shows_only_assigned(client, scoped_env):
    data = scoped_env
    response = client.get("/api/v1/commercial/follow-ups?scope=all", headers=data["headers_owner"])
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert ids == {str(data["follow_owner"].id)}


def test_t19_organization_scope_follow_ups_shows_all(client, scoped_env):
    data = scoped_env
    response = client.get("/api/v1/commercial/follow-ups?scope=all", headers=data["headers_org_wide"])
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert {str(data["follow_owner"].id), str(data["follow_other"].id)} <= ids


def test_t18b_nested_customer_follow_ups_route_also_respects_own_scope(client, scoped_env):
    """The nested GET /customers/{id}/follow-ups route uses a different repository
    method (list_by_customer) than the top-level list -- must not be a scope
    bypass path. The customer itself is org-wide visible for this check, but the
    follow-ups on it are still narrowed to the caller's own-scope: owner is not
    assigned to any follow-up on customer_other, so the list comes back empty
    rather than leaking follow_other (assigned to a different user)."""
    data = scoped_env
    response = client.get(
        f"/api/v1/commercial/customers/{data['customer_other'].id}/follow-ups",
        headers=data["headers_owner"],
    )
    assert response.status_code == 200
    assert response.json() == []


def test_t18c_nested_customer_follow_ups_route_org_wide_sees_all(client, scoped_env):
    data = scoped_env
    response = client.get(
        f"/api/v1/commercial/customers/{data['customer_owner'].id}/follow-ups",
        headers=data["headers_org_wide"],
    )
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert str(data["follow_owner"].id) in ids


def test_t20_root_sees_all_follow_ups(client, scoped_env):
    data = scoped_env
    response = client.get("/api/v1/commercial/follow-ups?scope=all", headers=data["headers_root"])
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert {str(data["follow_owner"].id), str(data["follow_other"].id)} <= ids


# ── Team Scope (Fail-Open) ────────────────────────────────────────────────────

def test_t21_team_scope_is_restricted_to_own(scoped_env, caplog):
    data = scoped_env
    permission = data["permissions"]["commercial:customers:read"]
    rp = data["db"].scalar(select(RolePermission).where(RolePermission.role_id == data["role_own"].id, RolePermission.permission_id == permission.id))
    rp.scope = "team"
    data["db"].commit()

    from app.core.authorization.scoped_policy import ScopedAuthorizationPolicy
    from app.core.interfaces.authorization_policy import AuthorizationContext

    policy = ScopedAuthorizationPolicy()
    ctx = AuthorizationContext(
        user_id=data["owner"].id, organization_id=data["org"].id, is_organization_root=False,
        permission_code="commercial:customers:read", effective_scope=AccessScope.TEAM,
    )
    query = select(Customer).where(Customer.organization_id == data["org"].id)
    with caplog.at_level("WARNING"):
        filtered = policy.apply_query_filter(ctx, query, owner_field="sales_owner_user_id")
        results = list(data["db"].scalars(filtered))
    assert [c.id for c in results] == [data["customer_owner"].id]


def test_t22_team_scope_logs_warning(scoped_env, caplog):
    from app.core.authorization.scoped_policy import ScopedAuthorizationPolicy
    from app.core.interfaces.authorization_policy import AuthorizationContext
    data = scoped_env
    policy = ScopedAuthorizationPolicy()
    ctx = AuthorizationContext(
        user_id=data["owner"].id, organization_id=data["org"].id, is_organization_root=False,
        permission_code="commercial:customers:read", effective_scope=AccessScope.TEAM,
    )
    with caplog.at_level("WARNING"):
        policy.can_access_record(ctx, record_owner_id=data["other"].id)
    assert any("Team scope not implemented" in record.message for record in caplog.records)


# ── Write Operations Not Scoped ──────────────────────────────────────────────

def test_t23_own_scope_can_create_customer(client, scoped_env):
    data = scoped_env
    response = client.post(
        "/api/v1/commercial/customers", headers=data["headers_owner"],
        json={"name": "New Lead", "sales_owner_user_id": str(data["owner"].id)},
    )
    assert response.status_code == 201


def test_t24_own_scope_can_update_own_customer(client, scoped_env):
    data = scoped_env
    response = client.patch(
        f"/api/v1/commercial/customers/{data['customer_owner'].id}", headers=data["headers_owner"],
        json={"name": "Renamed"},
    )
    assert response.status_code == 200


def test_t25_write_permission_cannot_bypass_read_scope(client, scoped_env):
    data = scoped_env
    response = client.patch(f"/api/v1/commercial/customers/{data['customer_other'].id}", headers=data["headers_owner"], json={"name": "Forbidden edit"})
    assert response.status_code == 404
    data["db"].refresh(data["customer_other"])
    assert data["customer_other"].name != "Forbidden edit"


# ── System Role Scopes ────────────────────────────────────────────────────────

def test_t28_sales_rep_customers_read_scope_is_own():
    from app.foundation.domain.system_roles import scope_for
    assert scope_for("sales_rep", "commercial:customers:read") == "own"


def test_t29_commercial_manager_customers_read_scope_is_organization():
    from app.foundation.domain.system_roles import scope_for
    assert scope_for("commercial_manager", "commercial:customers:read") == "organization"


def test_t30_organization_admin_defaults_to_organization():
    from app.foundation.domain.system_roles import scope_for
    assert scope_for("organization_admin", "commercial:customers:read") == "organization"


def test_t31_new_org_provisioning_creates_sales_rep_with_own_scope(client, db):
    from app.core.config import settings
    unique = "provscope"
    resp = client.post("/api/v1/system/bootstrap/initialize", json={
        "bootstrap_token": settings.bootstrap_token,
        "platform_root": {"full_name": "Prov Root", "email": f"{unique}-platform@example.com", "password": "PlatformRoot123!", "password_confirmation": "PlatformRoot123!"},
        "organization": {"name": "Prov Org", "code": unique, "industry_type": "manufacturing", "timezone": "UTC", "default_locale": "en"},
        "organization_admin": {"full_name": "Prov Admin", "email": f"{unique}-admin@example.com", "password": "ProvAdmin123!", "password_confirmation": "ProvAdmin123!"},
    })
    if resp.status_code != 201:
        pytest.skip("bootstrap already initialized in this test session")
    org = db.scalar(select(Organization).where(Organization.code == unique.upper()))
    role = db.scalar(select(Role).where(Role.organization_id == org.id, Role.code == "sales_rep"))
    permission = db.scalar(select(Permission).where(Permission.organization_id == org.id, Permission.code == "commercial:customers:read"))
    rp = db.scalar(select(RolePermission).where(RolePermission.role_id == role.id, RolePermission.permission_id == permission.id))
    assert rp.scope == "own"


# ── Scope API ─────────────────────────────────────────────────────────────────

def test_t32_role_detail_permissions_include_scope(client, scoped_env):
    data = scoped_env
    response = client.get(f"/api/v1/admin/roles/{data['role_own'].id}", headers=data["headers_root"])
    assert response.status_code == 200
    all_items = [item for group in response.json()["permissions"] for item in group["permissions"]]
    matching = [item for item in all_items if item["code"] == "commercial:customers:read"]
    assert matching and matching[0]["scope"] == "own"


def test_t33_patch_can_set_scope_for_scopable_permission(client, scoped_env):
    data = scoped_env
    response = client.patch(
        f"/api/v1/admin/roles/{data['role_own'].id}/permissions/commercial:follow_ups:read",
        headers=data["headers_root"], json={"scope": "organization"},
    )
    assert response.status_code == 200


def test_t34_assign_non_scopable_permission_with_own_scope_rejected(client, scoped_env):
    data = scoped_env
    response = client.post(
        f"/api/v1/admin/roles/{data['role_own'].id}/permissions",
        headers=data["headers_root"],
        json={"permission_code": "foundation:users:read", "scope": "own"},
    )
    assert response.status_code == 400


def test_t35_system_role_permission_scope_is_not_editable(client, scoped_env):
    data = scoped_env
    response = client.patch(
        f"/api/v1/admin/roles/{data['role_system'].id}/permissions/commercial:customers:read",
        headers=data["headers_root"], json={"scope": "own"},
    )
    assert response.status_code == 403


# ── Scopable Registry ─────────────────────────────────────────────────────────

def test_t36_registry_contains_customers_read():
    assert SCOPABLE_PERMISSIONS.get("commercial:customers:read") == "sales_owner_user_id"


def test_t37_registry_contains_follow_ups_read():
    assert SCOPABLE_PERMISSIONS.get("commercial:follow_ups:read") == "assigned_user_id"


def test_t38_registry_excludes_users_read():
    assert "foundation:users:read" not in SCOPABLE_PERMISSIONS


def test_t39_every_scopable_permission_owner_field_is_a_real_column():
    from app.commercial.infrastructure.models import Customer as CustomerModel
    from app.commercial.infrastructure.models import FollowUp as FollowUpModel
    from app.commercial.infrastructure.models import CustomerInteraction

    from app.commercial.infrastructure.models import CommercialOrder, Quote, Sample

    model_by_prefix = {
        "commercial:customers:": CustomerModel,
        "commercial:follow_ups:": FollowUpModel,
        "commercial:interactions:": CustomerInteraction,
        # RBAC-002: a quotation, order or sample is owned through its customer ("customer.sales_owner_user_id").
        "commercial:quotes:": Quote,
        "commercial:orders:": CommercialOrder,
        "commercial:samples:": Sample,
    }
    for code, owner_field in SCOPABLE_PERMISSIONS.items():
        model = next(model for prefix, model in model_by_prefix.items() if code.startswith(prefix))
        if "." in owner_field:
            relation, column = owner_field.split(".")
            assert hasattr(model, f"{relation}_id") and hasattr(CustomerModel, column), f"{code} -> {owner_field}"
        else:
            assert hasattr(model, owner_field), f"{code} -> {owner_field} not on {model}"


# ── Count Queries ──────────────────────────────────────────────────────────────

def test_t40_customer_count_respects_own_scope(client, scoped_env):
    data = scoped_env
    response = client.get("/api/v1/dashboard/summary", headers=data["headers_owner"])
    assert response.status_code == 200
    assert response.json()["customers_count"] == 1


def test_t42_root_dashboard_count_is_org_wide(client, scoped_env):
    data = scoped_env
    response = client.get("/api/v1/dashboard/summary", headers=data["headers_root"])
    assert response.status_code == 200
    assert response.json()["customers_count"] == 2


# ── Backward Compatibility ───────────────────────────────────────────────────

def test_t43_repository_without_policy_param_returns_unfiltered(scoped_env):
    from app.commercial.infrastructure.repositories import CustomerRepository
    data = scoped_env
    repo = CustomerRepository(data["db"])
    results = repo.list_by_organization(data["org"].id)
    assert len(results) == 2


# ── Tenant Isolation (additive, not replacing) ───────────────────────────────

def test_t45_t46_scope_is_additive_to_organization_filter(client, db, scoped_env):
    data = scoped_env
    org_b = Organization(name="Org B", code="SCOPE-ORG-B", status=OrganizationStatus.ACTIVE, timezone="UTC")
    db.add(org_b)
    db.flush()
    customer_b = Customer(organization_id=org_b.id, customer_code="CUST-B", name="Org B Customer", created_by_user_id=data["owner"].id, sales_owner_user_id=data["owner"].id)
    db.add(customer_b)
    db.commit()

    response = client.get("/api/v1/commercial/customers", headers=data["headers_owner"])
    ids = {item["id"] for item in response.json()["items"]}
    assert str(customer_b.id) not in ids

    detail = client.get(f"/api/v1/commercial/customers/{customer_b.id}", headers=data["headers_owner"])
    assert detail.status_code == 404
