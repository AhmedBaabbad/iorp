"""Customer Sales Owner user binding tests (CUST-FIX-004-FINAL).

Covers: eligibility (T11-T14), auto-assignment / permission scenarios
(T01-T10), human-readable responses (T15-T16), and tenant/data safety (T17).

Uses locally-scoped fixtures (not the shared `auth_headers`/`test_user`
fixtures in conftest.py, which grant zero permissions and cannot express
per-test permission combinations).
"""

from app.core.security import hash_password
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import (
    Organization,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.workforce.domain.enums import EmploymentType, WorkerType, WorkforceMemberStatus
from app.workforce.infrastructure.models import WorkforceMember

ASSIGN_OWNER_PERMS = [
    "commercial:customers:create",
    "commercial:customers:read",
    "commercial:customers:update",
    "commercial:customers:assign_owner",
]
ELIGIBLE_PERMS = [
    "commercial:customers:create",
    "commercial:customers:read",
    "commercial:customers:update",
]
NON_ELIGIBLE_PERMS = ["production:work_centers:read"]


def _make_org(db, code="test-org"):
    org = Organization(name="Test Org", code=code, status=OrganizationStatus.ACTIVE, timezone="UTC")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _make_permission(db, org, code):
    existing = db.query(Permission).filter_by(organization_id=org.id, code=code).first()
    if existing is not None:
        return existing
    parts = code.split(":")
    perm = Permission(organization_id=org.id, code=code, name=code, description=code, module_name=parts[0], resource_name=parts[1], action_name=parts[2])
    db.add(perm)
    db.flush()
    return perm


def _make_role(db, org, code, permission_codes):
    role = Role(organization_id=org.id, code=code, name=code)
    db.add(role)
    db.flush()
    for perm_code in permission_codes:
        perm = _make_permission(db, org, perm_code)
        db.add(RolePermission(role_id=role.id, permission_id=perm.id))
    db.commit()
    db.refresh(role)
    return role


def _make_user(db, org, email, role=None, status=UserStatus.ACTIVE, full_name=None):
    user = User(
        organization_id=org.id,
        full_name=full_name or email,
        email=email,
        password_hash=hash_password("Test1234!"),
        status=status,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    if role is not None:
        db.add(UserRole(user_id=user.id, role_id=role.id))
        db.commit()
    return user


def _login(client, email):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "Test1234!"})
    assert resp.status_code == 200, resp.json()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _headers_for(db, client, org, code, permission_codes, status=UserStatus.ACTIVE, full_name=None):
    role = _make_role(db, org, code, permission_codes)
    user = _make_user(db, org, f"{code}@example.com", role=role, status=status, full_name=full_name)
    return user, _login(client, user.email)


# ── T01-T04: assign_owner user create-time validation ──────────────────────────

def test_assign_owner_can_choose_eligible_owner(db, client):
    org = _make_org(db)
    _make_role(db, org, "assign_owner_role", ASSIGN_OWNER_PERMS)
    assigner, assigner_headers = _headers_for(db, client, org, "assigner", ASSIGN_OWNER_PERMS)
    owner, _ = _headers_for(db, client, org, "owner", ELIGIBLE_PERMS)

    resp = client.post(
        "/api/v1/commercial/customers",
        json={"name": "Acme Co", "sales_owner_user_id": str(owner.id)},
        headers=assigner_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["sales_owner_user_id"] == str(owner.id)


def test_assign_owner_rejects_inactive_owner(db, client):
    org = _make_org(db)
    assigner, assigner_headers = _headers_for(db, client, org, "assigner", ASSIGN_OWNER_PERMS)
    eligible_role = _make_role(db, org, "eligible_role_inactive", ELIGIBLE_PERMS)
    inactive_owner = _make_user(
        db, org, "inactive@example.com", role=eligible_role, status=UserStatus.INACTIVE,
    )

    resp = client.post(
        "/api/v1/commercial/customers",
        json={"name": "Acme Co", "sales_owner_user_id": str(inactive_owner.id)},
        headers=assigner_headers,
    )
    assert resp.status_code == 400


def test_assign_owner_rejects_non_commercial_owner(db, client):
    org = _make_org(db)
    assigner, assigner_headers = _headers_for(db, client, org, "assigner", ASSIGN_OWNER_PERMS)
    non_commercial, _ = _headers_for(db, client, org, "noncommercial", NON_ELIGIBLE_PERMS)

    resp = client.post(
        "/api/v1/commercial/customers",
        json={"name": "Acme Co", "sales_owner_user_id": str(non_commercial.id)},
        headers=assigner_headers,
    )
    assert resp.status_code == 400


def test_assign_owner_rejects_cross_org_owner(db, client):
    org_a = _make_org(db, "org-a")
    org_b = _make_org(db, "org-b")
    assigner, assigner_headers = _headers_for(db, client, org_a, "assigner", ASSIGN_OWNER_PERMS)
    other_org_user, _ = _headers_for(db, client, org_b, "otherorg", ELIGIBLE_PERMS)

    resp = client.post(
        "/api/v1/commercial/customers",
        json={"name": "Acme Co", "sales_owner_user_id": str(other_org_user.id)},
        headers=assigner_headers,
    )
    assert resp.status_code == 400


# ── T05-T07: ordinary / non-eligible create-time behavior ──────────────────────

def test_eligible_user_without_assign_owner_is_auto_assigned(db, client):
    org = _make_org(db)
    eligible_user, headers = _headers_for(db, client, org, "eligible", ELIGIBLE_PERMS)

    resp = client.post("/api/v1/commercial/customers", json={"name": "Acme Co"}, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["sales_owner_user_id"] == str(eligible_user.id)


def test_eligible_user_sending_different_owner_is_rejected(db, client):
    org = _make_org(db)
    eligible_user, headers = _headers_for(db, client, org, "eligible", ELIGIBLE_PERMS)
    other_user, _ = _headers_for(db, client, org, "other", ELIGIBLE_PERMS)

    resp = client.post(
        "/api/v1/commercial/customers",
        json={"name": "Acme Co", "sales_owner_user_id": str(other_user.id)},
        headers=headers,
    )
    assert resp.status_code == 403


def test_non_eligible_user_cannot_create(db, client):
    org = _make_org(db)
    _, headers = _headers_for(db, client, org, "noncreate", NON_ELIGIBLE_PERMS)

    resp = client.post("/api/v1/commercial/customers", json={"name": "Acme Co"}, headers=headers)
    assert resp.status_code == 403


# ── T08-T10: update / reassignment ──────────────────────────────────────────────

def test_assign_owner_can_reassign_on_update(db, client):
    org = _make_org(db)
    assigner, assigner_headers = _headers_for(db, client, org, "assigner", ASSIGN_OWNER_PERMS)
    new_owner, _ = _headers_for(db, client, org, "newowner", ELIGIBLE_PERMS)

    created = client.post(
        "/api/v1/commercial/customers",
        json={"name": "Acme Co", "sales_owner_user_id": str(assigner.id)},
        headers=assigner_headers,
    )
    customer_id = created.json()["id"]

    resp = client.patch(
        f"/api/v1/commercial/customers/{customer_id}",
        json={"sales_owner_user_id": str(new_owner.id)},
        headers=assigner_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["sales_owner_user_id"] == str(new_owner.id)


def test_ordinary_user_cannot_reassign_owner(db, client):
    org = _make_org(db)
    eligible_user, headers = _headers_for(db, client, org, "eligible", ELIGIBLE_PERMS)
    other_user, _ = _headers_for(db, client, org, "other", ELIGIBLE_PERMS)

    created = client.post("/api/v1/commercial/customers", json={"name": "Acme Co"}, headers=headers)
    customer_id = created.json()["id"]

    resp = client.patch(
        f"/api/v1/commercial/customers/{customer_id}",
        json={"sales_owner_user_id": str(other_user.id)},
        headers=headers,
    )
    assert resp.status_code == 403


def test_ordinary_user_can_update_other_fields(db, client):
    org = _make_org(db)
    _, headers = _headers_for(db, client, org, "eligible", ELIGIBLE_PERMS)

    created = client.post("/api/v1/commercial/customers", json={"name": "Acme Co"}, headers=headers)
    customer_id = created.json()["id"]

    resp = client.patch(
        f"/api/v1/commercial/customers/{customer_id}",
        json={"city": "Riyadh"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["city"] == "Riyadh"


# ── T11-T14: eligible-sales-owners endpoint ─────────────────────────────────────

def test_eligible_sales_owners_returns_only_eligible_users(db, client):
    org = _make_org(db)
    eligible_user, headers = _headers_for(db, client, org, "eligible", ELIGIBLE_PERMS)
    _make_role(db, org, "noncommercial_role", NON_ELIGIBLE_PERMS)
    _make_user(db, org, "noncommercial@example.com", role=None)

    resp = client.get("/api/v1/commercial/customers/eligible-sales-owners", headers=headers)
    assert resp.status_code == 200
    ids = {item["id"] for item in resp.json()}
    assert str(eligible_user.id) in ids
    assert len(ids) == 1


def test_eligible_sales_owners_excludes_inactive_users(db, client):
    org = _make_org(db)
    _, headers = _headers_for(db, client, org, "eligible", ELIGIBLE_PERMS)
    eligible_role = _make_role(db, org, "eligible_role_inactive", ELIGIBLE_PERMS)
    inactive_user = _make_user(
        db, org, "inactive@example.com", role=eligible_role, status=UserStatus.INACTIVE,
    )

    resp = client.get("/api/v1/commercial/customers/eligible-sales-owners", headers=headers)
    assert resp.status_code == 200
    ids = {item["id"] for item in resp.json()}
    assert str(inactive_user.id) not in ids


def test_eligible_sales_owners_excludes_other_org_users(db, client):
    org_a = _make_org(db, "org-a")
    org_b = _make_org(db, "org-b")
    _, headers_a = _headers_for(db, client, org_a, "eligiblea", ELIGIBLE_PERMS)
    other_org_user, _ = _headers_for(db, client, org_b, "eligibleb", ELIGIBLE_PERMS)

    resp = client.get("/api/v1/commercial/customers/eligible-sales-owners", headers=headers_a)
    assert resp.status_code == 200
    ids = {item["id"] for item in resp.json()}
    assert str(other_org_user.id) not in ids


def test_eligible_sales_owners_excludes_workforce_only_members(db, client):
    org = _make_org(db)
    _, headers = _headers_for(db, client, org, "eligible", ELIGIBLE_PERMS)

    workforce_only = WorkforceMember(
        organization_id=org.id,
        employee_code="WF-00001",
        full_name="Workforce Only Person",
        worker_type=WorkerType.SALES_REP,
        employment_type=EmploymentType.EMPLOYEE,
        status=WorkforceMemberStatus.ACTIVE,
        user_id=None,
    )
    db.add(workforce_only)
    db.commit()

    resp = client.get("/api/v1/commercial/customers/eligible-sales-owners", headers=headers)
    assert resp.status_code == 200
    # A workforce-only member has no User row at all, so it cannot appear
    # regardless of its employee_code / worker_type.
    assert all("WF-00001" not in str(item) for item in resp.json())


# ── T15-T16: response shape ──────────────────────────────────────────────────

def test_customer_response_includes_human_readable_sales_owner(db, client):
    org = _make_org(db)
    role = _make_role(db, org, "eligible_role", ELIGIBLE_PERMS)
    owner = _make_user(db, org, "owner@example.com", role=role, full_name="Owner Person")
    headers = _login(client, owner.email)

    workforce = WorkforceMember(
        organization_id=org.id,
        employee_code="WF-00099",
        full_name="Owner Person",
        worker_type=WorkerType.SALES_REP,
        employment_type=EmploymentType.EMPLOYEE,
        status=WorkforceMemberStatus.ACTIVE,
        user_id=owner.id,
    )
    db.add(workforce)
    db.commit()

    created = client.post("/api/v1/commercial/customers", json={"name": "Acme Co"}, headers=headers)
    body = created.json()

    assert body["sales_owner"]["full_name"] == "Owner Person"
    assert body["sales_owner"]["email"] == "owner@example.com"
    assert body["sales_owner"]["roles"][0]["code"] == "eligible_role"
    assert body["sales_owner"]["workforce"]["employee_code"] == "WF-00099"


def test_created_by_and_sales_owner_are_independent(db, client):
    org = _make_org(db)
    assigner, assigner_headers = _headers_for(db, client, org, "assigner", ASSIGN_OWNER_PERMS)
    owner, _ = _headers_for(db, client, org, "owner", ELIGIBLE_PERMS)

    created = client.post(
        "/api/v1/commercial/customers",
        json={"name": "Acme Co", "sales_owner_user_id": str(owner.id)},
        headers=assigner_headers,
    )
    body = created.json()
    assert body["created_by"]["id"] == str(assigner.id)
    assert body["sales_owner"]["id"] == str(owner.id)
    assert body["created_by"]["id"] != body["sales_owner"]["id"]


# ── T17: delete customer does not delete the sales owner user ──────────────────

def test_delete_customer_does_not_delete_sales_owner_user(db, client):
    org = _make_org(db)
    role = _make_role(db, org, "eligible_role", ELIGIBLE_PERMS + ["commercial:customers:delete"])
    owner = _make_user(db, org, "owner@example.com", role=role)
    headers = _login(client, owner.email)

    created = client.post("/api/v1/commercial/customers", json={"name": "Acme Co"}, headers=headers)
    customer_id = created.json()["id"]

    delete_resp = client.delete(f"/api/v1/commercial/customers/{customer_id}", headers=headers)
    assert delete_resp.status_code == 200

    still_there = db.query(User).filter_by(id=owner.id).first()
    assert still_there is not None
