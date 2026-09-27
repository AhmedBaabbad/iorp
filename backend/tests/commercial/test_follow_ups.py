"""Follow-up scheduling, assignment & worklist tests (FOLLOWUP-FIX-001-FINAL).

Uses locally-scoped fixtures (not the shared `auth_headers`/`test_user`
fixtures in conftest.py, which grant zero permissions and cannot express
per-test permission combinations).
"""

from datetime import timedelta

from app.commercial.domain.enums import FollowUpStatus
from app.commercial.infrastructure.models import Customer, CustomerInteraction
from app.core.security import hash_password
from app.core.utils import utc_now
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

ASSIGN_PERMS = [
    "commercial:customers:read",
    "commercial:follow_ups:read",
    "commercial:follow_ups:create",
    "commercial:follow_ups:update",
    "commercial:follow_ups:delete",
    "commercial:follow_ups:assign",
    "commercial:follow_ups:complete",
]
ELIGIBLE_PERMS = [
    "commercial:follow_ups:read",
    "commercial:follow_ups:create",
    "commercial:follow_ups:update",
    "commercial:follow_ups:complete",
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


_customer_counter = {"n": 0}


def _make_customer(db, org, sales_owner_user_id=None, name="Acme Co"):
    _customer_counter["n"] += 1
    customer = Customer(
        organization_id=org.id,
        customer_code=f"CUST-{_customer_counter['n']:04d}",
        name=name,
        sales_owner_user_id=sales_owner_user_id,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def _create_payload(**overrides):
    payload = {
        "reason": "Follow up on quote",
        "due_date": (utc_now() + timedelta(days=1)).isoformat(),
        "priority": "medium",
    }
    payload.update(overrides)
    return payload


# ── T01-T04, T06-T08: create-time assignment scenarios ─────────────────────────

def test_assign_user_can_choose_eligible_assignee(db, client):
    org = _make_org(db)
    assigner, assigner_headers = _headers_for(db, client, org, "assigner", ASSIGN_PERMS)
    assignee, _ = _headers_for(db, client, org, "assignee", ELIGIBLE_PERMS)
    customer = _make_customer(db, org)

    resp = client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(assigned_user_id=str(assignee.id)),
        headers=assigner_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["assigned_user"]["id"] == str(assignee.id)


def test_default_assignee_is_customer_sales_owner(db, client):
    org = _make_org(db)
    assigner, assigner_headers = _headers_for(db, client, org, "assigner", ASSIGN_PERMS)
    sales_owner, _ = _headers_for(db, client, org, "salesowner", ELIGIBLE_PERMS)
    customer = _make_customer(db, org, sales_owner_user_id=sales_owner.id)

    resp = client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(),
        headers=assigner_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["assigned_user"]["id"] == str(sales_owner.id)


def test_eligible_user_without_assign_is_auto_assigned(db, client):
    org = _make_org(db)
    eligible_user, headers = _headers_for(db, client, org, "eligible", ELIGIBLE_PERMS)
    customer = _make_customer(db, org)

    resp = client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(),
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["assigned_user"]["id"] == str(eligible_user.id)


def test_ordinary_user_sending_different_user_id_is_rejected(db, client):
    org = _make_org(db)
    eligible_user, headers = _headers_for(db, client, org, "eligible", ELIGIBLE_PERMS)
    other_user, _ = _headers_for(db, client, org, "other", ELIGIBLE_PERMS)
    customer = _make_customer(db, org)

    resp = client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(assigned_user_id=str(other_user.id)),
        headers=headers,
    )
    assert resp.status_code == 403


def test_non_eligible_user_cannot_create(db, client):
    org = _make_org(db)
    _, headers = _headers_for(db, client, org, "noncreate", NON_ELIGIBLE_PERMS)
    customer = _make_customer(db, org)

    resp = client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(),
        headers=headers,
    )
    assert resp.status_code == 403


def test_inactive_assignee_rejected(db, client):
    org = _make_org(db)
    assigner, assigner_headers = _headers_for(db, client, org, "assigner", ASSIGN_PERMS)
    eligible_role = _make_role(db, org, "eligible_role_inactive", ELIGIBLE_PERMS)
    inactive_user = _make_user(
        db, org, "inactive@example.com", role=eligible_role, status=UserStatus.INACTIVE,
    )
    customer = _make_customer(db, org)

    resp = client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(assigned_user_id=str(inactive_user.id)),
        headers=assigner_headers,
    )
    assert resp.status_code == 400


def test_cross_org_assignee_rejected(db, client):
    org_a = _make_org(db, "org-a")
    org_b = _make_org(db, "org-b")
    assigner, assigner_headers = _headers_for(db, client, org_a, "assigner", ASSIGN_PERMS)
    other_org_user, _ = _headers_for(db, client, org_b, "otherorg", ELIGIBLE_PERMS)
    customer = _make_customer(db, org_a)

    resp = client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(assigned_user_id=str(other_org_user.id)),
        headers=assigner_headers,
    )
    assert resp.status_code == 400


def test_non_commercial_assignee_rejected(db, client):
    org = _make_org(db)
    assigner, assigner_headers = _headers_for(db, client, org, "assigner", ASSIGN_PERMS)
    non_commercial, _ = _headers_for(db, client, org, "noncommercial", NON_ELIGIBLE_PERMS)
    customer = _make_customer(db, org)

    resp = client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(assigned_user_id=str(non_commercial.id)),
        headers=assigner_headers,
    )
    assert resp.status_code == 400


# ── T09: eligible-assignees excludes workforce-only members ────────────────────

def test_eligible_assignees_excludes_workforce_only_members(db, client):
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

    resp = client.get("/api/v1/commercial/follow-ups/eligible-assignees", headers=headers)
    assert resp.status_code == 200
    assert all("WF-00001" not in str(item) for item in resp.json())


# ── T10: interaction must belong to same customer ───────────────────────────────

def test_interaction_must_belong_to_same_customer(db, client):
    org = _make_org(db)
    _, headers = _headers_for(db, client, org, "eligible", ELIGIBLE_PERMS)
    customer = _make_customer(db, org, name="Cust1")
    other_customer = _make_customer(db, org, name="Cust2")

    creator = db.query(User).filter_by(email="eligible@example.com").first()
    interaction = CustomerInteraction(
        customer_id=other_customer.id,
        interaction_type="call",
        interaction_date=utc_now(),
        subject="Unrelated call",
        created_by_user_id=creator.id,
    )
    db.add(interaction)
    db.commit()
    db.refresh(interaction)

    resp = client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(interaction_id=str(interaction.id)),
        headers=headers,
    )
    assert resp.status_code == 400


# ── T11-T15: status transitions and overdue derivation ──────────────────────────

def test_complete_sets_status_and_completed_at(db, client):
    org = _make_org(db)
    _, headers = _headers_for(db, client, org, "eligible", ELIGIBLE_PERMS)
    customer = _make_customer(db, org)
    created = client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(),
        headers=headers,
    ).json()

    resp = client.post(
        f"/api/v1/commercial/follow-ups/{created['id']}/complete",
        json={},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["completed_at"] is not None


def test_reopen_resets_status_and_completed_at(db, client):
    org = _make_org(db)
    _, headers = _headers_for(db, client, org, "eligible", ELIGIBLE_PERMS)
    customer = _make_customer(db, org)
    created = client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(),
        headers=headers,
    ).json()
    client.post(f"/api/v1/commercial/follow-ups/{created['id']}/complete", json={}, headers=headers)

    resp = client.post(f"/api/v1/commercial/follow-ups/{created['id']}/reopen", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"
    assert body["completed_at"] is None


def test_cancel_sets_status_and_clears_completed_at(db, client):
    org = _make_org(db)
    _, headers = _headers_for(db, client, org, "eligible", ELIGIBLE_PERMS)
    customer = _make_customer(db, org)
    created = client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(),
        headers=headers,
    ).json()

    resp = client.post(f"/api/v1/commercial/follow-ups/{created['id']}/cancel", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["completed_at"] is None


def test_overdue_derived_for_pending_past_due(db, client):
    org = _make_org(db)
    _, headers = _headers_for(db, client, org, "eligible", ELIGIBLE_PERMS)
    customer = _make_customer(db, org)
    past_due = (utc_now() - timedelta(days=2)).isoformat()

    created = client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(due_date=past_due),
        headers=headers,
    ).json()

    resp = client.get(f"/api/v1/commercial/follow-ups/{created['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_overdue"] is True


def test_completed_and_cancelled_are_never_overdue(db, client):
    org = _make_org(db)
    _, headers = _headers_for(db, client, org, "eligible", ELIGIBLE_PERMS)
    customer = _make_customer(db, org)
    past_due = (utc_now() - timedelta(days=2)).isoformat()

    created = client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(due_date=past_due),
        headers=headers,
    ).json()
    completed = client.post(
        f"/api/v1/commercial/follow-ups/{created['id']}/complete", json={}, headers=headers,
    ).json()
    assert completed["is_overdue"] is False

    created2 = client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(due_date=past_due),
        headers=headers,
    ).json()
    cancelled = client.post(
        f"/api/v1/commercial/follow-ups/{created2['id']}/cancel", headers=headers,
    ).json()
    assert cancelled["is_overdue"] is False


# ── T16-T17: reassignment permission ────────────────────────────────────────────

def test_ordinary_user_cannot_reassign(db, client):
    org = _make_org(db)
    eligible_user, headers = _headers_for(db, client, org, "eligible", ELIGIBLE_PERMS)
    other_user, _ = _headers_for(db, client, org, "other", ELIGIBLE_PERMS)
    customer = _make_customer(db, org)
    created = client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(),
        headers=headers,
    ).json()

    resp = client.patch(
        f"/api/v1/commercial/follow-ups/{created['id']}",
        json={"assigned_user_id": str(other_user.id)},
        headers=headers,
    )
    assert resp.status_code == 403


def test_assign_user_can_reassign(db, client):
    org = _make_org(db)
    assigner, assigner_headers = _headers_for(db, client, org, "assigner", ASSIGN_PERMS)
    new_assignee, _ = _headers_for(db, client, org, "newassignee", ELIGIBLE_PERMS)
    customer = _make_customer(db, org)
    created = client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(assigned_user_id=str(assigner.id)),
        headers=assigner_headers,
    ).json()

    resp = client.patch(
        f"/api/v1/commercial/follow-ups/{created['id']}",
        json={"assigned_user_id": str(new_assignee.id)},
        headers=assigner_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["assigned_user"]["id"] == str(new_assignee.id)


# ── T18-T19: tenant isolation and scope ──────────────────────────────────────────

def test_tenant_isolation(db, client):
    org_a = _make_org(db, "org-a")
    org_b = _make_org(db, "org-b")
    _, headers_a = _headers_for(db, client, org_a, "eligiblea", ELIGIBLE_PERMS)
    user_b, headers_b = _headers_for(db, client, org_b, "eligibleb", ELIGIBLE_PERMS)
    customer_a = _make_customer(db, org_a)

    created = client.post(
        f"/api/v1/commercial/customers/{customer_a.id}/follow-ups",
        json=_create_payload(),
        headers=headers_a,
    ).json()

    resp = client.get(f"/api/v1/commercial/follow-ups/{created['id']}", headers=headers_b)
    assert resp.status_code == 404

    list_resp = client.get("/api/v1/commercial/follow-ups?scope=all", headers=headers_b)
    assert list_resp.status_code == 200
    assert all(item["id"] != created["id"] for item in list_resp.json()["items"])


def test_scope_mine_returns_only_current_users_follow_ups(db, client):
    org = _make_org(db)
    user_a, headers_a = _headers_for(db, client, org, "usera", ASSIGN_PERMS)
    user_b, headers_b = _headers_for(db, client, org, "userb", ELIGIBLE_PERMS)
    customer = _make_customer(db, org)

    client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(assigned_user_id=str(user_a.id)),
        headers=headers_a,
    )
    client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(),
        headers=headers_b,
    )

    resp = client.get("/api/v1/commercial/follow-ups", headers=headers_b)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["assigned_user"]["id"] == str(user_b.id)


# ── T20: filters ─────────────────────────────────────────────────────────────────

def test_filters_status_and_overdue(db, client):
    org = _make_org(db)
    _, headers = _headers_for(db, client, org, "eligible", ELIGIBLE_PERMS)
    customer = _make_customer(db, org)
    past_due = (utc_now() - timedelta(days=2)).isoformat()
    future_due = (utc_now() + timedelta(days=3)).isoformat()

    overdue_one = client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(due_date=past_due, reason="Overdue one"),
        headers=headers,
    ).json()
    client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(due_date=future_due, reason="Future one"),
        headers=headers,
    )

    resp = client.get("/api/v1/commercial/follow-ups?overdue=true", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == overdue_one["id"]

    status_resp = client.get("/api/v1/commercial/follow-ups?status=pending", headers=headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["total"] == 2


# ── T21: delete permission ───────────────────────────────────────────────────────

def test_delete_requires_delete_permission(db, client):
    org = _make_org(db)
    _, headers = _headers_for(db, client, org, "eligible", ELIGIBLE_PERMS)
    customer = _make_customer(db, org)
    created = client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(),
        headers=headers,
    ).json()

    resp = client.delete(f"/api/v1/commercial/follow-ups/{created['id']}", headers=headers)
    assert resp.status_code == 403

    assigner, assigner_headers = _headers_for(db, client, org, "assigner", ASSIGN_PERMS)
    resp2 = client.delete(f"/api/v1/commercial/follow-ups/{created['id']}", headers=assigner_headers)
    assert resp2.status_code == 200


# ── T22: customer deletion cascades follow-ups (existing project policy) ────────

def test_customer_deletion_removes_its_follow_ups(db, client):
    org = _make_org(db)
    assigner, headers = _headers_for(db, client, org, "assigner", ASSIGN_PERMS + ["commercial:customers:delete"])
    customer = _make_customer(db, org)
    created = client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(assigned_user_id=str(assigner.id)),
        headers=headers,
    ).json()

    delete_resp = client.delete(f"/api/v1/commercial/customers/{customer.id}", headers=headers)
    assert delete_resp.status_code == 200

    resp = client.get(f"/api/v1/commercial/follow-ups/{created['id']}", headers=headers)
    assert resp.status_code == 404


# ── T23: readable summaries ──────────────────────────────────────────────────────

def test_response_includes_readable_summaries(db, client):
    org = _make_org(db)
    role = _make_role(db, org, "eligible_role", ELIGIBLE_PERMS)
    user = _make_user(db, org, "owner@example.com", role=role, full_name="Owner Person")
    headers = _login(client, user.email)
    customer = _make_customer(db, org, name="ReadableCo")

    resp = client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(),
        headers=headers,
    )
    body = resp.json()
    assert body["customer"]["customer_name"] == customer.name
    assert body["assigned_user"]["full_name"] == "Owner Person"
    assert body["created_by"]["full_name"] == "Owner Person"


# ── T24: dashboard counts ─────────────────────────────────────────────────────────

def test_dashboard_counts_scoped_to_user(db, client):
    org = _make_org(db)
    user_a, headers_a = _headers_for(db, client, org, "usera", ASSIGN_PERMS)
    user_b, headers_b = _headers_for(db, client, org, "userb", ELIGIBLE_PERMS)
    customer = _make_customer(db, org)

    past_due = (utc_now() - timedelta(hours=2)).isoformat()
    client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        json=_create_payload(due_date=past_due, assigned_user_id=str(user_a.id)),
        headers=headers_a,
    )

    resp_a = client.get("/api/v1/dashboard/summary", headers=headers_a)
    assert resp_a.status_code == 200
    assert resp_a.json()["follow_ups_overdue"] == 1

    resp_b = client.get("/api/v1/dashboard/summary", headers=headers_b)
    assert resp_b.status_code == 200
    assert resp_b.json()["follow_ups_overdue"] == 0


# ── T25: route ordering ────────────────────────────────────────────────────────

def test_eligible_assignees_route_does_not_conflict_with_id_route(db, client):
    org = _make_org(db)
    _, headers = _headers_for(db, client, org, "eligible", ELIGIBLE_PERMS)

    resp = client.get("/api/v1/commercial/follow-ups/eligible-assignees", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
