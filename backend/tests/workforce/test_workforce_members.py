"""Workforce members API tests."""

import pytest

from app.core.security import hash_password
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, User


_BASE_MEMBER = {
    "full_name": "Ali Hassan",
    "display_name": "Ali",
    "worker_type": "technician",
    "employment_type": "employee",
    "phone": "+966500000001",
    "email": "ali@example.com",
    "primary_skill": "Extrusion",
    "notes": "Senior floor technician",
}


@pytest.fixture(autouse=True)
def _organization_root_access(db, test_user):
    """These baseline CRUD tests exercise behavior, not RBAC denial paths."""
    test_user.is_organization_root = True
    db.commit()


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_other_org_user(client, db) -> tuple[dict[str, str], User]:
    org = Organization(
        name="Other Workforce Org",
        code="other-workforce-org",
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    user = User(
        organization_id=org.id,
        full_name="Other Workforce User",
        email="other-workforce@example.com",
        password_hash=hash_password("Other1234!"),
        status=UserStatus.ACTIVE,
        is_organization_root=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _login(client, "other-workforce@example.com", "Other1234!"), user


def test_create_workforce_member_generates_employee_code(client, auth_headers):
    response = client.post(
        "/api/v1/workforce-members",
        json=_BASE_MEMBER,
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["employee_code"] == "WF-00001"
    assert data["full_name"] == "Ali Hassan"
    assert data["worker_type"] == "technician"
    assert data["employment_type"] == "employee"
    assert data["status"] == "active"
    assert data["is_system_user"] is False
    assert data["user_id"] is None
    assert "organization_id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_employee_code_sequence_is_not_reused_after_delete(client, auth_headers):
    created = client.post("/api/v1/workforce-members", json=_BASE_MEMBER, headers=auth_headers)
    assert created.status_code == 201

    deleted = client.delete(
        f"/api/v1/workforce-members/{created.json()['id']}",
        headers=auth_headers,
    )
    assert deleted.status_code == 200

    recreated = client.post(
        "/api/v1/workforce-members",
        json={**_BASE_MEMBER, "full_name": "Second Member", "email": "second@example.com"},
        headers=auth_headers,
    )
    assert recreated.status_code == 201
    assert recreated.json()["employee_code"] == "WF-00002"


def test_list_workforce_members_filters_by_status_and_type(client, auth_headers):
    member_a = client.post("/api/v1/workforce-members", json=_BASE_MEMBER, headers=auth_headers)
    assert member_a.status_code == 201
    member_b = client.post(
        "/api/v1/workforce-members",
        json={
            **_BASE_MEMBER,
            "full_name": "Sales Person",
            "worker_type": "sales_rep",
            "employment_type": "contractor",
            "email": "sales@example.com",
        },
        headers=auth_headers,
    )
    assert member_b.status_code == 201
    client.patch(
        f"/api/v1/workforce-members/{member_b.json()['id']}",
        json={"status": "inactive"},
        headers=auth_headers,
    )

    response = client.get(
        "/api/v1/workforce-members?worker_type=sales_rep&status=inactive&employment_type=contractor",
        headers=auth_headers,
    )

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["full_name"] == "Sales Person"
    assert items[0]["employee_code"] == "WF-00002"


def test_link_and_unlink_user_to_workforce_member(client, auth_headers, test_user):
    created = client.post("/api/v1/workforce-members", json=_BASE_MEMBER, headers=auth_headers)
    member_id = created.json()["id"]

    linked = client.post(
        f"/api/v1/workforce-members/{member_id}/link-user",
        json={"user_id": str(test_user.id)},
        headers=auth_headers,
    )
    assert linked.status_code == 200
    assert linked.json()["user_id"] == str(test_user.id)
    assert linked.json()["is_system_user"] is True

    unlinked = client.delete(
        f"/api/v1/workforce-members/{member_id}/link-user",
        headers=auth_headers,
    )
    assert unlinked.status_code == 200
    assert unlinked.json()["user_id"] is None
    assert unlinked.json()["is_system_user"] is False


def test_workforce_member_deletion_impact_is_not_blocked(client, auth_headers):
    created = client.post("/api/v1/workforce-members", json=_BASE_MEMBER, headers=auth_headers)
    assert created.status_code == 201

    response = client.get(
        f"/api/v1/workforce-members/{created.json()['id']}/deletion-impact",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == {"is_blocked": False}


def test_link_user_rejects_cross_tenant_user(client, db, auth_headers):
    _, other_user = _create_other_org_user(client, db)
    created = client.post("/api/v1/workforce-members", json=_BASE_MEMBER, headers=auth_headers)

    response = client.post(
        f"/api/v1/workforce-members/{created.json()['id']}/link-user",
        json={"user_id": str(other_user.id)},
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_tenant_isolation_for_workforce_members(client, db, auth_headers):
    created = client.post("/api/v1/workforce-members", json=_BASE_MEMBER, headers=auth_headers)
    member_id = created.json()["id"]
    other_headers, _ = _create_other_org_user(client, db)

    list_response = client.get("/api/v1/workforce-members", headers=other_headers)
    assert list_response.status_code == 200
    assert list_response.json() == []

    get_response = client.get(f"/api/v1/workforce-members/{member_id}", headers=other_headers)
    assert get_response.status_code == 404

    update_response = client.patch(
        f"/api/v1/workforce-members/{member_id}",
        json={"full_name": "Cross Tenant"},
        headers=other_headers,
    )
    assert update_response.status_code == 404
