"""FOLLOWUP-FIX-001A deactivation, bulk reassignment, and orphan recovery."""

from datetime import timedelta

import pytest

from app.commercial.domain.enums import FollowUpPriority, FollowUpStatus
from app.commercial.infrastructure.models import FollowUp
from app.core.utils import utc_now
from app.foundation.domain.enums import UserStatus
from app.foundation.infrastructure.models import User
from app.workforce.domain.enums import EmploymentType, WorkforceMemberStatus, WorkerType
from app.workforce.infrastructure.models import WorkforceMember
from tests.commercial.test_follow_ups import (
    ASSIGN_PERMS,
    ELIGIBLE_PERMS,
    NON_ELIGIBLE_PERMS,
    _create_payload,
    _headers_for,
    _make_customer,
    _make_org,
    _make_role,
    _make_user,
)


ADMIN_AND_ASSIGN_PERMS = [
    *ASSIGN_PERMS,
    "foundation:users:write",
    "foundation:users:deactivate",
    "foundation:users:delete",  # RBAC-002: the permanent delete has its own permission
]
OPEN_STATUSES = (FollowUpStatus.PENDING, FollowUpStatus.IN_PROGRESS)


def _follow_up(db, customer, assigned_user, status=FollowUpStatus.PENDING):
    item = FollowUp(
        customer_id=customer.id,
        assigned_user_id=assigned_user.id if assigned_user else None,
        created_by_user_id=assigned_user.id if assigned_user else None,
        due_date=utc_now() + timedelta(days=1),
        priority=FollowUpPriority.MEDIUM,
        status=status,
        reason="Deactivation hardening test",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@pytest.mark.parametrize(
    ("statuses", "expected_status", "expected_count"),
    [
        ([], 200, 0),
        ([FollowUpStatus.PENDING], 409, 1),
        ([FollowUpStatus.IN_PROGRESS], 409, 1),
        ([FollowUpStatus.COMPLETED], 200, 0),
        ([FollowUpStatus.CANCELLED], 200, 0),
    ],
)
def test_t01_t05_deactivation_guard_by_status(
    db,
    client,
    statuses,
    expected_status,
    expected_count,
):
    org = _make_org(db)
    actor, headers = _headers_for(db, client, org, "admin_assign", ADMIN_AND_ASSIGN_PERMS)
    target = _make_user(db, org, "target@example.com")
    customer = _make_customer(db, org)
    for follow_up_status in statuses:
        _follow_up(db, customer, target, follow_up_status)

    response = client.delete(f"/api/v1/admin/users/{target.id}", headers=headers)

    assert response.status_code == expected_status
    db.refresh(target)
    if expected_status == 409:
        assert response.json()["code"] == "USER_HAS_OPEN_DEPENDENCIES"
        assert response.json()["dependencies"] == {"open_follow_ups": expected_count, "assigned_customers": 0, "active_workforce_link": False}
        assert response.json()["total_blocking_items"] == expected_count
        assert target.status == UserStatus.ACTIVE
    else:
        assert target.status == UserStatus.INACTIVE
    assert actor.status == UserStatus.ACTIVE


def test_t02_patch_status_change_requires_lifecycle_endpoint(db, client):
    org = _make_org(db)
    _, headers = _headers_for(db, client, org, "admin_assign", ADMIN_AND_ASSIGN_PERMS)
    target = _make_user(db, org, "target@example.com")
    customer = _make_customer(db, org)
    _follow_up(db, customer, target)

    response = client.patch(
        f"/api/v1/admin/users/{target.id}",
        headers=headers,
        json={"status": "inactive"},
    )

    assert response.status_code == 400


def test_t02b_hard_delete_route_is_also_guarded(db, client):
    """The hard-delete escape hatch must not bypass the deactivation guard --
    otherwise a user with open follow-ups could be removed entirely, silently
    orphaning their follow-ups via the assigned_user_id ON DELETE SET NULL."""
    org = _make_org(db)
    _, headers = _headers_for(db, client, org, "admin_assign", ADMIN_AND_ASSIGN_PERMS)
    target = _make_user(db, org, "target@example.com")
    customer = _make_customer(db, org)
    follow_up = _follow_up(db, customer, target)

    response = client.delete(f"/api/v1/admin/users/{target.id}/hard", headers=headers)

    assert response.status_code == 409
    assert response.json()["code"] == "USER_HAS_OPEN_DEPENDENCIES"
    db.refresh(target)
    db.refresh(follow_up)
    assert db.get(User, target.id) is not None
    assert follow_up.assigned_user_id == target.id


def test_t06_t07_impact_endpoint_count_and_tenant_scope(db, client):
    org = _make_org(db, "org-a")
    other_org = _make_org(db, "org-b")
    _, headers = _headers_for(db, client, org, "admin_assign", ADMIN_AND_ASSIGN_PERMS)
    target = _make_user(db, org, "target@example.com")
    other_target = _make_user(db, other_org, "other@example.com")
    customer = _make_customer(db, org)
    _follow_up(db, customer, target, FollowUpStatus.PENDING)
    _follow_up(db, customer, target, FollowUpStatus.IN_PROGRESS)
    _follow_up(db, customer, target, FollowUpStatus.COMPLETED)

    response = client.get(
        f"/api/v1/admin/users/{target.id}/deactivation-impact",
        headers=headers,
    )
    cross_org = client.get(
        f"/api/v1/admin/users/{other_target.id}/deactivation-impact",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["dependencies"]["open_follow_ups"] == 2
    assert response.json()["can_deactivate"] is False
    assert cross_org.status_code == 404


def test_t08_t11_bulk_reassignment_moves_only_open(db, client):
    org = _make_org(db)
    source, headers = _headers_for(db, client, org, "assigner", ADMIN_AND_ASSIGN_PERMS)
    replacement, _ = _headers_for(db, client, org, "replacement", ELIGIBLE_PERMS)
    customer = _make_customer(db, org)
    records = {
        status: _follow_up(db, customer, source, status)
        for status in FollowUpStatus
    }

    response = client.post(
        "/api/v1/commercial/follow-ups/reassign-by-user",
        headers=headers,
        json={"from_user_id": str(source.id), "to_user_id": str(replacement.id)},
    )

    assert response.status_code == 200
    assert response.json()["reassigned_count"] == 2
    for status, record in records.items():
        db.refresh(record)
        expected = replacement.id if status in OPEN_STATUSES else source.id
        assert record.assigned_user_id == expected


@pytest.mark.parametrize("failure_kind", ["inactive", "cross_org", "ineligible", "same"])
def test_t12_t14_t16_t18_invalid_bulk_reassignment_is_atomic(
    db,
    client,
    failure_kind,
):
    org = _make_org(db, "org-a")
    source, headers = _headers_for(db, client, org, "assigner", ADMIN_AND_ASSIGN_PERMS)
    customer = _make_customer(db, org)
    record = _follow_up(db, customer, source)

    if failure_kind == "inactive":
        role = _make_role(db, org, "inactive_role", ELIGIBLE_PERMS)
        replacement = _make_user(
            db,
            org,
            "inactive@example.com",
            role=role,
            status=UserStatus.INACTIVE,
        )
    elif failure_kind == "cross_org":
        other_org = _make_org(db, "org-b")
        role = _make_role(db, other_org, "cross_role", ELIGIBLE_PERMS)
        replacement = _make_user(db, other_org, "cross@example.com", role=role)
    elif failure_kind == "ineligible":
        role = _make_role(db, org, "ineligible_role", NON_ELIGIBLE_PERMS)
        replacement = _make_user(db, org, "ineligible@example.com", role=role)
    else:
        replacement = source

    response = client.post(
        "/api/v1/commercial/follow-ups/reassign-by-user",
        headers=headers,
        json={"from_user_id": str(source.id), "to_user_id": str(replacement.id)},
    )

    assert response.status_code == 400
    db.refresh(record)
    assert record.assigned_user_id == source.id


def test_t15_workforce_only_replacement_is_rejected(db, client):
    org = _make_org(db)
    source, headers = _headers_for(db, client, org, "assigner", ADMIN_AND_ASSIGN_PERMS)
    customer = _make_customer(db, org)
    record = _follow_up(db, customer, source)
    member = WorkforceMember(
        organization_id=org.id,
        employee_code="EMP-9999",
        full_name="Workforce Only",
        worker_type=WorkerType.HELPER,
        employment_type=EmploymentType.EMPLOYEE,
        status=WorkforceMemberStatus.ACTIVE,
    )
    db.add(member)
    db.commit()

    response = client.post(
        "/api/v1/commercial/follow-ups/reassign-by-user",
        headers=headers,
        json={"from_user_id": str(source.id), "to_user_id": str(member.id)},
    )

    assert response.status_code == 400
    db.refresh(record)
    assert record.assigned_user_id == source.id


def test_from_user_in_another_org_is_rejected(db, client):
    org = _make_org(db, "org-a")
    other_org = _make_org(db, "org-b")
    _, headers = _headers_for(db, client, org, "assigner", ADMIN_AND_ASSIGN_PERMS)
    replacement, _ = _headers_for(db, client, org, "replacement", ELIGIBLE_PERMS)
    other_org_source, _ = _headers_for(db, client, other_org, "othersource", ELIGIBLE_PERMS)

    response = client.post(
        "/api/v1/commercial/follow-ups/reassign-by-user",
        headers=headers,
        json={"from_user_id": str(other_org_source.id), "to_user_id": str(replacement.id)},
    )

    assert response.status_code == 400


def test_t17_bulk_reassignment_requires_assign_permission(db, client):
    org = _make_org(db)
    source, headers = _headers_for(db, client, org, "ordinary", ELIGIBLE_PERMS)
    replacement, _ = _headers_for(db, client, org, "replacement", ELIGIBLE_PERMS)

    response = client.post(
        "/api/v1/commercial/follow-ups/reassign-by-user",
        headers=headers,
        json={"from_user_id": str(source.id), "to_user_id": str(replacement.id)},
    )

    assert response.status_code == 403


def test_t19_t20_orphan_schema_and_filter(db, client):
    org = _make_org(db)
    user, headers = _headers_for(db, client, org, "assigner", ASSIGN_PERMS)
    customer = _make_customer(db, org)
    orphan = _follow_up(db, customer, None)
    _follow_up(db, customer, user)

    response = client.get(
        "/api/v1/commercial/follow-ups?scope=all&unassigned=true",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    item = response.json()["items"][0]
    assert item["id"] == str(orphan.id)
    assert item["assigned_user_id"] is None
    assert item["assigned_user"] is None
    assert item["is_unassigned"] is True


def test_t21_creation_requires_valid_assignee(db, client):
    org = _make_org(db)
    _, headers = _headers_for(db, client, org, "assigner", ASSIGN_PERMS)
    customer = _make_customer(db, org)

    response = client.post(
        f"/api/v1/commercial/customers/{customer.id}/follow-ups",
        headers=headers,
        json=_create_payload(),
    )

    assert response.status_code == 400


def test_t22_t24_reassign_then_deactivate_preserves_history(db, client):
    org = _make_org(db)
    _, headers = _headers_for(db, client, org, "admin_assign", ADMIN_AND_ASSIGN_PERMS)
    source, _ = _headers_for(db, client, org, "source", ELIGIBLE_PERMS)
    replacement, _ = _headers_for(db, client, org, "replacement", ELIGIBLE_PERMS)
    customer = _make_customer(db, org)
    open_item = _follow_up(db, customer, source)
    historical_item = _follow_up(db, customer, source, FollowUpStatus.COMPLETED)

    reassignment = client.post(
        "/api/v1/commercial/follow-ups/reassign-by-user",
        headers=headers,
        json={"from_user_id": str(source.id), "to_user_id": str(replacement.id)},
    )
    deactivation = client.delete(f"/api/v1/admin/users/{source.id}", headers=headers)

    assert reassignment.status_code == 200
    assert deactivation.status_code == 200
    assert deactivation.json()["status"] == "inactive"
    db.refresh(source)
    db.refresh(open_item)
    db.refresh(historical_item)
    assert source.status == UserStatus.INACTIVE
    assert db.get(User, source.id) is not None
    assert open_item.assigned_user_id == replacement.id
    assert historical_item.assigned_user_id == source.id
