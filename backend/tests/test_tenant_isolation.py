import uuid
from datetime import datetime, timezone

import pytest

from app.commercial.domain.enums import FollowUpPriority, FollowUpStatus
from app.commercial.infrastructure.models import Customer, FollowUp
from app.foundation.domain.permission_catalog import PERMISSIONS
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import (
    Organization,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.core.security import hash_password
from app.core.tenancy import validate_same_organization
from fastapi import HTTPException
from app.workforce.domain.enums import EmploymentType, WorkforceMemberStatus, WorkerType
from app.workforce.infrastructure.models import WorkforceMember
from app.production.domain.enums import WorkCenterType, WorkCenterStatus
from app.production.infrastructure.models import WorkCenter
from app.quality.domain.enums import QualityCheckType
from app.quality.infrastructure.models import QualityCheck


@pytest.fixture
def isolated_tenants(client, db):
    org_a = Organization(name="Organization A", code="ORG-A", status=OrganizationStatus.ACTIVE, timezone="UTC")
    org_b = Organization(name="Organization B", code="ORG-B", status=OrganizationStatus.ACTIVE, timezone="UTC")
    db.add_all([org_a, org_b])
    db.flush()
    user_a = User(organization_id=org_a.id, full_name="User A", email="tenant-a@example.com", password_hash=hash_password("Test1234!"), status=UserStatus.ACTIVE)
    user_b = User(organization_id=org_b.id, full_name="User B", email="tenant-b@example.com", password_hash=hash_password("Test1234!"), status=UserStatus.ACTIVE)
    role_a = Role(organization_id=org_a.id, name="Admin A", code="admin")
    role_b = Role(organization_id=org_b.id, name="Admin B", code="admin")
    db.add_all([user_a, user_b, role_a, role_b])
    db.flush()
    for item in PERMISSIONS:
        permission_a = Permission(organization_id=org_a.id, **item)
        permission_b = Permission(organization_id=org_b.id, **item)
        db.add_all([permission_a, permission_b])
        db.flush()
        db.add_all([RolePermission(role_id=role_a.id, permission_id=permission_a.id), RolePermission(role_id=role_b.id, permission_id=permission_b.id)])
    db.add_all([UserRole(user_id=user_a.id, role_id=role_a.id), UserRole(user_id=user_b.id, role_id=role_b.id)])
    customer_a = Customer(organization_id=org_a.id, customer_code="CUST-A", name="Customer A", created_by_user_id=user_a.id, sales_owner_user_id=user_a.id)
    customer_b = Customer(organization_id=org_b.id, customer_code="CUST-B", name="Customer B", created_by_user_id=user_b.id, sales_owner_user_id=user_b.id)
    db.add_all([customer_a, customer_b])
    db.flush()
    follow_a = FollowUp(customer_id=customer_a.id, assigned_user_id=user_a.id, created_by_user_id=user_a.id, due_date=datetime(2030, 1, 1, tzinfo=timezone.utc), priority=FollowUpPriority.MEDIUM, status=FollowUpStatus.PENDING, reason="A")
    follow_b = FollowUp(customer_id=customer_b.id, assigned_user_id=user_b.id, created_by_user_id=user_b.id, due_date=datetime(2030, 1, 1, tzinfo=timezone.utc), priority=FollowUpPriority.MEDIUM, status=FollowUpStatus.PENDING, reason="B")
    member_a = WorkforceMember(organization_id=org_a.id, employee_code="EMP-A", full_name="Worker A", worker_type=WorkerType.OPERATOR, employment_type=EmploymentType.EMPLOYEE, status=WorkforceMemberStatus.ACTIVE)
    member_b = WorkforceMember(organization_id=org_b.id, employee_code="EMP-B", full_name="Worker B", worker_type=WorkerType.OPERATOR, employment_type=EmploymentType.EMPLOYEE, status=WorkforceMemberStatus.ACTIVE)
    work_center_a = WorkCenter(organization_id=org_a.id, code="WC-A", name="Work Center A", center_type=WorkCenterType.EXTRUSION, status=WorkCenterStatus.ACTIVE)
    work_center_b = WorkCenter(organization_id=org_b.id, code="WC-B", name="Work Center B", center_type=WorkCenterType.EXTRUSION, status=WorkCenterStatus.ACTIVE)
    quality_check_a = QualityCheck(organization_id=org_a.id, inspection_code="QI-A-0001", check_datetime=datetime(2030, 1, 1, tzinfo=timezone.utc), check_type=QualityCheckType.IN_PROCESS_INSPECTION, qty_inspected=10, qty_accepted=10, qty_rejected=0, checked_by_user_id=user_a.id)
    quality_check_b = QualityCheck(organization_id=org_b.id, inspection_code="QI-B-0001", check_datetime=datetime(2030, 1, 1, tzinfo=timezone.utc), check_type=QualityCheckType.IN_PROCESS_INSPECTION, qty_inspected=10, qty_accepted=10, qty_rejected=0, checked_by_user_id=user_b.id)
    db.add_all([follow_a, follow_b, member_a, member_b, work_center_a, work_center_b, quality_check_a, quality_check_b])
    db.commit()
    login = client.post("/api/v1/auth/login", json={"email": user_a.email, "password": "Test1234!"})
    return {
        "org_a": org_a, "org_b": org_b, "user_a": user_a, "user_b": user_b,
        "role_a": role_a, "role_b": role_b, "customer_a": customer_a, "customer_b": customer_b,
        "follow_a": follow_a, "follow_b": follow_b, "member_a": member_a, "member_b": member_b,
        "work_center_a": work_center_a, "work_center_b": work_center_b,
        "quality_check_a": quality_check_a, "quality_check_b": quality_check_b,
        "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
    }


def test_t01_t02_user_read_isolation(client, isolated_tenants):
    data = isolated_tenants
    listed = client.get("/api/v1/admin/users", headers=data["headers"])
    assert listed.status_code == 200
    assert {item["id"] for item in listed.json()} == {str(data["user_a"].id)}
    assert client.get(f"/api/v1/admin/users/{data['user_b'].id}", headers=data["headers"]).status_code == 404


def test_t03_t04_role_read_isolation(client, isolated_tenants):
    data = isolated_tenants
    listed = client.get("/api/v1/admin/roles", headers=data["headers"])
    assert listed.status_code == 200
    assert {item["id"] for item in listed.json()} == {str(data["role_a"].id)}
    assert client.get(f"/api/v1/admin/roles/{data['role_b'].id}", headers=data["headers"]).status_code == 404


def test_t05_t07_customer_isolation_and_body_override(client, isolated_tenants):
    data = isolated_tenants
    listed = client.get("/api/v1/commercial/customers", headers=data["headers"])
    assert listed.status_code == 200
    assert str(data["customer_b"].id) not in {item["id"] for item in listed.json()["items"]}
    assert client.get(f"/api/v1/commercial/customers/{data['customer_b'].id}", headers=data["headers"]).status_code == 404
    created = client.post(
        "/api/v1/commercial/customers",
        headers=data["headers"],
        json={"name": "Scoped", "organization_id": str(data["org_b"].id), "sales_owner_user_id": str(data["user_a"].id)},
    )
    assert created.status_code == 201
    assert created.json()["organization_id"] == str(data["org_a"].id)


def test_t08_t09_follow_up_isolation(client, isolated_tenants):
    data = isolated_tenants
    listed = client.get("/api/v1/commercial/follow-ups", headers=data["headers"])
    assert listed.status_code == 200
    ids = {item["id"] for item in listed.json()["items"]}
    assert str(data["follow_a"].id) in ids and str(data["follow_b"].id) not in ids
    assert client.get(f"/api/v1/commercial/follow-ups/{data['follow_b'].id}", headers=data["headers"]).status_code == 404


def test_t10_t11_workforce_isolation(client, isolated_tenants):
    data = isolated_tenants
    listed = client.get("/api/v1/workforce-members", headers=data["headers"])
    assert listed.status_code == 200
    assert {item["id"] for item in listed.json()} == {str(data["member_a"].id)}
    assert client.get(f"/api/v1/workforce-members/{data['member_b'].id}", headers=data["headers"]).status_code == 404


def test_t12_cross_tenant_sales_owner_rejected(client, isolated_tenants):
    data = isolated_tenants
    response = client.patch(f"/api/v1/commercial/customers/{data['customer_a'].id}", headers=data["headers"], json={"sales_owner_user_id": str(data["user_b"].id)})
    assert response.status_code == 400


def test_t13_cross_tenant_follow_up_assignee_rejected(client, isolated_tenants):
    data = isolated_tenants
    response = client.patch(f"/api/v1/commercial/follow-ups/{data['follow_a'].id}", headers=data["headers"], json={"assigned_user_id": str(data["user_b"].id)})
    assert response.status_code == 400


def test_t14_cross_tenant_workforce_link_rejected(client, isolated_tenants):
    data = isolated_tenants
    response = client.post(f"/api/v1/workforce-members/{data['member_a'].id}/link-user", headers=data["headers"], json={"user_id": str(data["user_b"].id)})
    assert response.status_code == 400


def test_t15_t17_organization_profile_and_logo_isolation(client, isolated_tenants):
    data = isolated_tenants
    profile = client.get("/api/v1/auth/me", headers=data["headers"])
    assert profile.status_code == 200
    assert profile.json()["organization_id"] == str(data["org_a"].id)
    assert client.get(f"/api/v1/organizations/{data['org_b'].id}/logo", headers=data["headers"]).status_code == 404


def test_tenant_scope_validator_rejects_cross_organization(isolated_tenants):
    data = isolated_tenants
    with pytest.raises(HTTPException) as exc:
        validate_same_organization(data["org_b"].id, data["org_a"].id, "user")
    assert exc.value.status_code == 404
    assert "organization" not in exc.value.detail.lower()


# ─── PLATFORM-TENANCY-001 additions ─────────────────────────────────────────
# Expanded coverage: production/quality modules, UUID enumeration, auth-context
# override prevention, mutation-endpoint isolation, and the reassign-by-owner
# from_user regression fix.

@pytest.mark.parametrize(
    ("method", "path", "foreign_key", "body"),
    [
        ("patch", "/api/v1/commercial/customers/{id}", "customer_b", {"name": "x"}),
        ("delete", "/api/v1/commercial/customers/{id}", "customer_b", None),
        ("patch", "/api/v1/commercial/follow-ups/{id}", "follow_b", {"notes": "x"}),
        ("patch", "/api/v1/admin/roles/{id}", "role_b", {"name": "x"}),
        ("delete", "/api/v1/admin/roles/{id}", "role_b", None),
        ("patch", "/api/v1/admin/users/{id}", "user_b", {"full_name": "x"}),
        ("post", "/api/v1/admin/users/{id}/lock", "user_b", None),
        ("get", "/api/v1/admin/users/{id}/deactivation-impact", "user_b", None),
        ("patch", "/api/v1/workforce-members/{id}", "member_b", {"full_name": "x"}),
        ("delete", "/api/v1/workforce-members/{id}", "member_b", None),
    ],
)
def test_write_mutations_return_404_for_cross_tenant_resources(client, isolated_tenants, method, path, foreign_key, body):
    data = isolated_tenants
    url = path.format(id=data[foreign_key].id)
    request = getattr(client, method)
    response = request(url, headers=data["headers"], json=body) if body is not None else request(url, headers=data["headers"])
    assert response.status_code == 404


def test_cross_org_role_assignment_rejected(client, isolated_tenants):
    data = isolated_tenants
    response = client.post(
        f"/api/v1/admin/users/{data['user_a'].id}/roles",
        headers=data["headers"],
        json={"role_id": str(data["role_b"].id)},
    )
    assert response.status_code == 404
    nonexistent = client.post(
        f"/api/v1/admin/users/{data['user_a'].id}/roles",
        headers=data["headers"],
        json={"role_id": str(uuid.uuid4())},
    )
    assert response.json() == nonexistent.json() == {"detail": "Role not found."}


def test_eligible_sales_owners_excludes_other_org_users(client, isolated_tenants):
    data = isolated_tenants
    response = client.get("/api/v1/commercial/customers/eligible-sales-owners", headers=data["headers"])
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert str(data["user_b"].id) not in ids


def test_eligible_assignees_excludes_other_org_users(client, isolated_tenants):
    data = isolated_tenants
    response = client.get("/api/v1/commercial/follow-ups/eligible-assignees", headers=data["headers"])
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert str(data["user_b"].id) not in ids


def test_production_module_isolation(client, isolated_tenants):
    data = isolated_tenants
    h = data["headers"]
    listed = client.get("/api/v1/production/work-centers", headers=h)
    assert listed.status_code == 200
    ids = {item["id"] for item in listed.json()}
    assert str(data["work_center_a"].id) in ids and str(data["work_center_b"].id) not in ids
    assert client.get(f"/api/v1/production/work-centers/{data['work_center_b'].id}", headers=h).status_code == 404
    assert client.patch(f"/api/v1/production/work-centers/{data['work_center_b'].id}", headers=h, json={"name": "x"}).status_code == 404


def test_quality_module_isolation(client, isolated_tenants):
    data = isolated_tenants
    h = data["headers"]
    listed = client.get("/api/v1/quality/quality-checks", headers=h)
    assert listed.status_code == 200
    ids = {item["id"] for item in listed.json()["items"]}
    assert str(data["quality_check_a"].id) in ids and str(data["quality_check_b"].id) not in ids
    assert client.get(f"/api/v1/quality/quality-checks/{data['quality_check_b'].id}", headers=h).status_code == 404
    assert client.patch(f"/api/v1/quality/quality-checks/{data['quality_check_b'].id}", headers=h, json={"notes": "x"}).status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/admin/users/{id}",
        "/api/v1/admin/roles/{id}",
        "/api/v1/commercial/customers/{id}",
        "/api/v1/commercial/follow-ups/{id}",
        "/api/v1/workforce-members/{id}",
        "/api/v1/production/work-centers/{id}",
        "/api/v1/quality/quality-checks/{id}",
    ],
)
def test_uuid_enumeration_returns_404_not_500(client, isolated_tenants, path):
    response = client.get(path.format(id=uuid.uuid4()), headers=isolated_tenants["headers"])
    assert response.status_code == 404
    assert set(response.json().keys()) == {"detail"}


def test_404_identical_for_nonexistent_vs_wrong_org(client, isolated_tenants):
    data = isolated_tenants
    h = data["headers"]
    nonexistent = client.get(f"/api/v1/commercial/customers/{uuid.uuid4()}", headers=h)
    wrong_org = client.get(f"/api/v1/commercial/customers/{data['customer_b'].id}", headers=h)
    assert nonexistent.status_code == wrong_org.status_code == 404
    assert set(nonexistent.json().keys()) == set(wrong_org.json().keys())
    assert "organization" not in nonexistent.json()["detail"].lower()
    assert "organization" not in wrong_org.json()["detail"].lower()


def test_organization_id_in_body_ignored_on_user_update(client, isolated_tenants):
    data = isolated_tenants
    response = client.patch(
        f"/api/v1/admin/users/{data['user_a'].id}",
        headers=data["headers"],
        json={"full_name": "Still Org A", "organization_id": str(data["org_b"].id)},
    )
    assert response.status_code == 200
    assert response.json()["organization_id"] == str(data["org_a"].id)


def test_organization_id_in_body_rejected_on_workforce_member_create(client, isolated_tenants):
    """WorkforceMemberCreate uses extra="forbid" — an org_id override attempt is
    rejected outright by schema validation (422) rather than silently ignored.
    """
    data = isolated_tenants
    response = client.post(
        "/api/v1/workforce-members",
        headers=data["headers"],
        json={
            "full_name": "New Worker",
            "worker_type": "operator",
            "employment_type": "employee",
            "organization_id": str(data["org_b"].id),
        },
    )
    assert response.status_code == 422


def test_reassign_customers_by_owner_rejects_cross_org_from_user(client, isolated_tenants):
    """Regression test for PLATFORM-TENANCY-001 fix: reassign_customers_by_owner
    previously validated only to_user_id's org membership, silently no-op'ing
    (200, reassigned_count=0) for a from_user_id belonging to another org instead
    of rejecting the request. Fails without the fix, passes with it.
    """
    data = isolated_tenants
    response = client.post(
        "/api/v1/commercial/customers/reassign-by-owner",
        headers=data["headers"],
        json={"from_user_id": str(data["user_b"].id), "to_user_id": str(data["user_a"].id)},
    )
    assert response.status_code == 400


def test_reassign_follow_ups_by_user_rejects_cross_org_from_user(client, isolated_tenants):
    data = isolated_tenants
    response = client.post(
        "/api/v1/commercial/follow-ups/reassign-by-user",
        headers=data["headers"],
        json={"from_user_id": str(data["user_b"].id), "to_user_id": str(data["user_a"].id)},
    )
    assert response.status_code == 400


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/admin/users/not-a-uuid",
        "/api/v1/admin/roles/not-a-uuid",
        "/api/v1/commercial/customers/not-a-uuid",
        "/api/v1/commercial/follow-ups/not-a-uuid",
        "/api/v1/workforce-members/not-a-uuid",
        "/api/v1/production/work-centers/not-a-uuid",
        "/api/v1/production/production-orders/not-a-uuid",
        "/api/v1/quality/quality-checks/not-a-uuid",
        "/api/v1/quality/quality-rejections/not-a-uuid",
        "/api/v1/quality/non-conformance-reports/not-a-uuid",
    ],
)
def test_t36_t45_invalid_uuid_is_validation_error(client, isolated_tenants, path):
    response = client.get(path, headers=isolated_tenants["headers"])
    assert response.status_code in (400, 422)


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/admin/users/null",
        "/api/v1/admin/roles/null",
        "/api/v1/commercial/customers/null",
        "/api/v1/commercial/follow-ups/null",
        "/api/v1/workforce-members/null",
        "/api/v1/production/work-centers/null",
        "/api/v1/production/production-orders/null",
        "/api/v1/quality/quality-checks/null",
        "/api/v1/quality/quality-rejections/null",
        "/api/v1/quality/non-conformance-reports/null",
    ],
)
def test_t46_t55_null_uuid_is_validation_error(client, isolated_tenants, path):
    response = client.get(path, headers=isolated_tenants["headers"])
    assert response.status_code in (400, 422)


@pytest.mark.parametrize(
    ("path", "foreign_id"),
    [
        ("/api/v1/admin/users", "user_b"),
        ("/api/v1/admin/roles", "role_b"),
        ("/api/v1/commercial/customers", "customer_b"),
        ("/api/v1/workforce-members", "member_b"),
        ("/api/v1/production/work-centers", "work_center_b"),
        ("/api/v1/quality/quality-checks", "quality_check_b"),
    ],
)
def test_t56_t61_query_org_override_cannot_expand_scope(client, isolated_tenants, path, foreign_id):
    data = isolated_tenants
    response = client.get(
        path,
        headers=data["headers"],
        params={"organization_id": str(data["org_b"].id)},
    )
    assert response.status_code == 200
    assert str(data[foreign_id].id) not in response.text


def test_t62_legacy_organization_id_logo_route_is_removed(client, isolated_tenants):
    data = isolated_tenants
    response = client.get(
        f"/api/v1/organizations/{data['org_a'].id}/logo",
        headers=data["headers"],
    )
    assert response.status_code == 404


def test_t63_cross_tenant_role_removal_matches_nonexistent(client, isolated_tenants):
    data = isolated_tenants
    foreign = client.delete(
        f"/api/v1/admin/users/{data['user_a'].id}/roles/{data['role_b'].id}",
        headers=data["headers"],
    )
    missing = client.delete(
        f"/api/v1/admin/users/{data['user_a'].id}/roles/{uuid.uuid4()}",
        headers=data["headers"],
    )
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json() == {"detail": "Role not found."}


def test_t64_cross_tenant_user_assignment_matches_nonexistent(client, isolated_tenants):
    data = isolated_tenants
    payload = {"role_id": str(data["role_a"].id)}
    foreign = client.post(f"/api/v1/admin/users/{data['user_b'].id}/roles", headers=data["headers"], json=payload)
    missing = client.post(f"/api/v1/admin/users/{uuid.uuid4()}/roles", headers=data["headers"], json=payload)
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json() == {"detail": "User not found."}


def test_t65_body_org_override_is_forbidden_or_ignored(client, isolated_tenants):
    data = isolated_tenants
    response = client.post(
        "/api/v1/commercial/customers",
        headers=data["headers"],
        json={"name": "Override attempt", "organization_id": str(data["org_b"].id), "sales_owner_user_id": str(data["user_a"].id)},
    )
    assert response.status_code in (201, 422)
    if response.status_code == 201:
        assert response.json()["organization_id"] == str(data["org_a"].id)
