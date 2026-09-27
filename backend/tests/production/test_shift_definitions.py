from uuid import UUID

import pytest

from app.core.security import hash_password
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, User
from app.production.domain.enums import WorkCenterStatus, WorkCenterType
from app.production.infrastructure.models import WorkCenter
from tests.production.conftest import grant_production_role


ZERO_UUID = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def work_center(client, auth_headers):
    resp = client.post(
        "/api/v1/production/work-centers",
        json={"code": "WC-001", "name": "Line 1", "center_type": "extrusion"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.json()


def _base_shift_definition(work_center_id: str, code: str = "SD-001") -> dict[str, str]:
    return {
        "code": code,
        "name": "Morning",
        "shift_type": "morning",
        "start_time": "07:00:00",
        "end_time": "15:00:00",
    }


def _create_shift_definition(client, auth_headers, work_center_id: str, code: str = "SD-001"):
    resp = client.post(
        "/api/v1/production/shift-definitions",
        json=_base_shift_definition(work_center_id, code),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp


def _create_org(db, code: str = "other-org") -> Organization:
    org = Organization(
        name="Other Org",
        code=code,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _create_user(db, org: Organization, email: str = "other@example.com") -> User:
    user = User(
        organization_id=org.id,
        full_name="Other User",
        email=email,
        password_hash=hash_password("Other1234!"),
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    grant_production_role(db, org, user)
    return user


def _login(client, email: str = "other@example.com") -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Other1234!"},
    )
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_create_shift_definition(client, auth_headers, work_center):
    resp = client.post(
        "/api/v1/production/shift-definitions",
        json={
            "code": "SD-001",
            "name": "Morning",
            "shift_type": "morning",
            "start_time": "07:00:00",
            "end_time": "15:00:00",
        },
        headers=auth_headers,
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "active"
    assert data["crosses_midnight"] is False
    assert data["duration_hours"] == "8.00"
    assert "organization_id" in data


def test_create_night_shift_crosses_midnight(client, auth_headers, work_center):
    resp = client.post(
        "/api/v1/production/shift-definitions",
        json={
            **_base_shift_definition(work_center["id"]),
            "shift_type": "night",
            "start_time": "23:00:00",
            "end_time": "07:00:00",
        },
        headers=auth_headers,
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["crosses_midnight"] is True
    assert data["duration_hours"] == "8.00"


def test_create_evening_shift_no_midnight(client, auth_headers, work_center):
    resp = client.post(
        "/api/v1/production/shift-definitions",
        json={
            **_base_shift_definition(work_center["id"]),
            "shift_type": "evening",
            "start_time": "15:00:00",
            "end_time": "23:00:00",
        },
        headers=auth_headers,
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["crosses_midnight"] is False
    assert data["duration_hours"] == "8.00"


def test_create_requires_auth(client, work_center):
    resp = client.post(
        "/api/v1/production/shift-definitions",
        json=_base_shift_definition(work_center["id"]),
    )
    assert resp.status_code == 401


def test_create_work_center_not_in_org(client, db, auth_headers):
    other_org = _create_org(db, code="foreign-org")
    foreign_work_center = WorkCenter(
        organization_id=other_org.id,
        code="WC-FOREIGN",
        name="Foreign Line",
        center_type=WorkCenterType.EXTRUSION,
        status=WorkCenterStatus.ACTIVE,
    )
    db.add(foreign_work_center)
    db.commit()
    db.refresh(foreign_work_center)

    resp = client.post(
        "/api/v1/production/shift-definitions",
        json={**_base_shift_definition(str(foreign_work_center.id)), "work_center_id": str(foreign_work_center.id)},
        headers=auth_headers,
    )

    assert resp.status_code == 422


def test_create_duplicate_code_rejected(client, auth_headers, work_center):
    _create_shift_definition(client, auth_headers, work_center["id"])

    resp = client.post(
        "/api/v1/production/shift-definitions",
        json={**_base_shift_definition(work_center["id"]), "name": "Duplicate Morning"},
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_list_no_filter(client, auth_headers, work_center):
    _create_shift_definition(client, auth_headers, work_center["id"], "SD-001")
    _create_shift_definition(client, auth_headers, work_center["id"], "SD-002")

    resp = client.get("/api/v1/production/shift-definitions", headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_filter_by_work_center_id(client, auth_headers, work_center):
    second_wc = client.post(
        "/api/v1/production/work-centers",
        json={"code": "WC-002", "name": "Line 2", "center_type": "packing"},
        headers=auth_headers,
    )
    assert second_wc.status_code == 201

    _create_shift_definition(client, auth_headers, work_center["id"], "SD-001")
    _create_shift_definition(client, auth_headers, second_wc.json()["id"], "SD-002")

    resp = client.get(
        f"/api/v1/production/shift-definitions?work_center_id={work_center['id']}",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert all("work_center_id" not in item for item in data)


def test_list_unknown_work_center_id(client, auth_headers):
    resp = client.get(
        f"/api/v1/production/shift-definitions?work_center_id={ZERO_UUID}",
        headers=auth_headers,
    )
    assert resp.status_code == 200


def test_get_shift_definition(client, auth_headers, work_center):
    create_resp = _create_shift_definition(client, auth_headers, work_center["id"])
    shift_definition_id = create_resp.json()["id"]

    resp = client.get(
        f"/api/v1/production/shift-definitions/{shift_definition_id}",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == "SD-001"
    assert "notes" in data


def test_get_not_found(client, auth_headers):
    resp = client.get(
        f"/api/v1/production/shift-definitions/{ZERO_UUID}",
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_update_status(client, auth_headers, work_center):
    create_resp = _create_shift_definition(client, auth_headers, work_center["id"])
    shift_definition_id = create_resp.json()["id"]
    original_crosses_midnight = create_resp.json()["crosses_midnight"]

    resp = client.patch(
        f"/api/v1/production/shift-definitions/{shift_definition_id}",
        json={"status": "inactive"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "inactive"
    assert data["crosses_midnight"] == original_crosses_midnight


def test_update_times_recalculates_crosses_midnight(client, auth_headers, work_center):
    create_resp = _create_shift_definition(client, auth_headers, work_center["id"])
    assert create_resp.json()["crosses_midnight"] is False
    shift_definition_id = create_resp.json()["id"]

    resp = client.patch(
        f"/api/v1/production/shift-definitions/{shift_definition_id}",
        json={"start_time": "22:00:00", "end_time": "06:00:00"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["crosses_midnight"] is True
    assert data["duration_hours"] == "8.00"


def test_update_not_found(client, auth_headers):
    resp = client.patch(
        f"/api/v1/production/shift-definitions/{ZERO_UUID}",
        json={"status": "inactive"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_update_work_center_id_null_rejected(client, auth_headers, work_center):
    create_resp = _create_shift_definition(client, auth_headers, work_center["id"])
    shift_definition_id = create_resp.json()["id"]

    resp = client.patch(
        f"/api/v1/production/shift-definitions/{shift_definition_id}",
        json={"work_center_id": None},
        headers=auth_headers,
    )

    assert resp.status_code == 422


def test_tenant_isolation(client, db, auth_headers, work_center):
    first_shift = _create_shift_definition(client, auth_headers, work_center["id"], "SD-FIRST")

    other_org = _create_org(db, code="tenant-isolation-org")
    _create_user(db, other_org, email="tenant-isolation@example.com")
    other_headers = _login(client, email="tenant-isolation@example.com")

    second_wc = client.post(
        "/api/v1/production/work-centers",
        json={"code": "WC-SECOND", "name": "Second Org Line", "center_type": "extrusion"},
        headers=other_headers,
    )
    assert second_wc.status_code == 201
    second_shift = _create_shift_definition(
        client,
        other_headers,
        second_wc.json()["id"],
        "SD-SECOND",
    )

    list_resp = client.get("/api/v1/production/shift-definitions", headers=auth_headers)

    assert list_resp.status_code == 200
    data = list_resp.json()
    assert len(data) == 1
    assert data[0]["id"] == first_shift.json()["id"]
    assert data[0]["id"] != second_shift.json()["id"]

    get_resp = client.get(
        f"/api/v1/production/shift-definitions/{second_shift.json()['id']}",
        headers=auth_headers,
    )
    assert get_resp.status_code == 404
