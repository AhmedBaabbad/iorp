from tests.production.order_fixtures import historical_order
from datetime import time
from decimal import Decimal
from uuid import UUID

import pytest

from app.core.security import hash_password
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, User
from app.production.domain.enums import (
    ShiftDefinitionStatus,
    ShiftType,
    WorkCenterStatus,
    WorkCenterType,
)
from app.production.infrastructure.models import ShiftDefinition, WorkCenter
from tests.production.conftest import grant_production_role


ZERO_UUID = "00000000-0000-0000-0000-000000000000"
MISSING_COMMERCIAL_ORDER_ID = "deadbeef-0000-0000-0000-000000000000"


@pytest.fixture
def work_center(client, auth_headers):
    resp = client.post(
        "/api/v1/production/work-centers",
        json={"code": "WC-001", "name": "Line 1", "center_type": "extrusion"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
def shift_definition(client, auth_headers, work_center):
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
    return resp.json()


def _base_order(work_center_id: str, **overrides) -> dict:
    payload = {
        "work_center_id": work_center_id,
        "product_type": "PE Film",
        "planned_quantity": "100.00",
        "unit": "kg",
        "planned_start_date": "2026-07-01",
        "planned_end_date": "2026-07-02",
    }
    payload.update(overrides)
    return payload


def _create_order(client, auth_headers, work_center_id: str, **overrides):
    resp = historical_order(client, auth_headers, _base_order(work_center_id, **overrides))
    assert resp.status_code == 201
    return resp


def _create_org(db, code="other-org") -> Organization:
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


def _create_user(db, org, email="other@example.com") -> User:
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


def _login(client, email, password="Other1234!") -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_foreign_work_center(db, org: Organization, code: str = "WC-FOREIGN") -> WorkCenter:
    work_center = WorkCenter(
        organization_id=org.id,
        code=code,
        name="Foreign Line",
        center_type=WorkCenterType.EXTRUSION,
        status=WorkCenterStatus.ACTIVE,
    )
    db.add(work_center)
    db.commit()
    db.refresh(work_center)
    return work_center


def _create_foreign_shift_definition(
    db,
    org: Organization,
    work_center: WorkCenter,
    code: str = "SD-FOREIGN",
) -> ShiftDefinition:
    shift_definition = ShiftDefinition(
        organization_id=org.id,
        code=code,
        name="Foreign Morning",
        shift_type=ShiftType.MORNING,
        start_time=time(7, 0),
        end_time=time(15, 0),
        duration_hours=Decimal("8.00"),
        crosses_midnight=False,
        status=ShiftDefinitionStatus.ACTIVE,
    )
    db.add(shift_definition)
    db.commit()
    db.refresh(shift_definition)
    return shift_definition


def test_create_production_order_auto_number(client, auth_headers, work_center):
    resp = historical_order(client, auth_headers, _base_order(work_center["id"]))

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "draft"
    assert data["production_order_number"].startswith("PO-")
    assert "organization_id" in data
    assert "created_by_user_id" in data


def test_create_production_order_explicit_number(client, auth_headers, work_center):
    resp = historical_order(client, auth_headers, _base_order(work_center["id"], production_order_number="PO-TEST-001"))

    assert resp.status_code == 201
    assert resp.json()["production_order_number"] == "PO-TEST-001"


def test_create_with_shift_definition(client, auth_headers, work_center, shift_definition):
    resp = client.post(
        "/api/v1/production/production-orders",
        json=_base_order(work_center["id"], shift_definition_id=shift_definition["id"]),
        headers=auth_headers,
    )

    assert resp.status_code in (403, 422)


def test_create_with_commercial_order_id(client, auth_headers, work_center):
    resp = client.post(
        "/api/v1/production/production-orders",
        json=_base_order(work_center["id"], commercial_order_id=MISSING_COMMERCIAL_ORDER_ID),
        headers=auth_headers,
    )

    assert resp.status_code == 422


def test_create_requires_auth(client, work_center):
    resp = client.post(
        "/api/v1/production/production-orders",
        json=_base_order(work_center["id"]),
    )
    assert resp.status_code == 401


def test_create_work_center_not_in_org(client, db, auth_headers):
    other_org = _create_org(db, code="foreign-work-center-org")
    foreign_work_center = _create_foreign_work_center(db, other_org)

    resp = client.post(
        "/api/v1/production/production-orders",
        json=_base_order(str(foreign_work_center.id)),
        headers=auth_headers,
    )

    assert resp.status_code in (403, 422)


def test_create_shift_definition_not_in_org(client, db, auth_headers, work_center):
    other_org = _create_org(db, code="foreign-shift-definition-org")
    foreign_work_center = _create_foreign_work_center(db, other_org)
    foreign_shift_definition = _create_foreign_shift_definition(
        db,
        other_org,
        foreign_work_center,
    )

    resp = client.post(
        "/api/v1/production/production-orders",
        json=_base_order(work_center["id"], shift_definition_id=str(foreign_shift_definition.id)),
        headers=auth_headers,
    )

    assert resp.status_code == 422


def test_create_duplicate_order_number(client, auth_headers, work_center):
    _create_order(
        client,
        auth_headers,
        work_center["id"],
        production_order_number="PO-DUP-001",
    )

    resp = client.post(
        "/api/v1/production/production-orders",
        json=_base_order(work_center["id"], production_order_number="PO-DUP-001"),
        headers=auth_headers,
    )

    assert resp.status_code in (403, 422)


def test_auto_generated_numbers_are_unique(client, auth_headers, work_center):
    first = _create_order(client, auth_headers, work_center["id"])
    second = _create_order(client, auth_headers, work_center["id"])

    first_number = first.json()["production_order_number"]
    second_number = second.json()["production_order_number"]
    assert first_number != second_number
    assert first_number.startswith("PO-")
    assert second_number.startswith("PO-")


def test_list_no_filter(client, auth_headers, work_center):
    _create_order(client, auth_headers, work_center["id"])
    _create_order(client, auth_headers, work_center["id"])

    resp = client.get("/api/v1/production/production-orders", headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2 and resp.json()["total"] == 2


def test_list_filter_by_status(client, auth_headers, work_center):
    _create_order(client, auth_headers, work_center["id"])

    draft_resp = client.get(
        "/api/v1/production/production-orders?status=draft",
        headers=auth_headers,
    )
    released_resp = client.get(
        "/api/v1/production/production-orders?status=released",
        headers=auth_headers,
    )

    assert draft_resp.status_code == 200
    assert len(draft_resp.json()["items"]) >= 1
    assert all(item["status"] == "draft" for item in draft_resp.json()["items"])
    assert released_resp.status_code == 200
    assert released_resp.json()["items"] == []


def test_list_filter_by_work_center_id(client, auth_headers, work_center):
    second_wc = client.post(
        "/api/v1/production/work-centers",
        json={"code": "WC-002", "name": "Line 2", "center_type": "packing"},
        headers=auth_headers,
    )
    assert second_wc.status_code == 201

    _create_order(client, auth_headers, work_center["id"])
    _create_order(client, auth_headers, second_wc.json()["id"])

    resp = client.get(
        f"/api/v1/production/production-orders?work_center_id={work_center['id']}",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()["items"]
    assert len(data) == 1
    assert data[0]["work_center_id"] == str(UUID(work_center["id"]))


def test_list_filter_by_priority(client, auth_headers, work_center):
    _create_order(client, auth_headers, work_center["id"], priority="urgent")
    _create_order(client, auth_headers, work_center["id"], priority="low")

    urgent_resp = client.get(
        "/api/v1/production/production-orders?priority=urgent",
        headers=auth_headers,
    )
    low_resp = client.get(
        "/api/v1/production/production-orders?priority=low",
        headers=auth_headers,
    )

    assert urgent_resp.status_code == 200
    assert len(urgent_resp.json()["items"]) == 1
    assert low_resp.status_code == 200
    assert len(low_resp.json()["items"]) == 1


def test_get_production_order(client, auth_headers, work_center):
    create_resp = _create_order(client, auth_headers, work_center["id"])
    production_order_id = create_resp.json()["id"]

    resp = client.get(
        f"/api/v1/production/production-orders/{production_order_id}",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "notes" in data
    assert "target_spec_json" in data


def test_get_not_found(client, auth_headers):
    resp = client.get(
        f"/api/v1/production/production-orders/{ZERO_UUID}",
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_update_status(client, auth_headers, work_center):
    create_resp = _create_order(client, auth_headers, work_center["id"])
    production_order_id = create_resp.json()["id"]

    # PATCH no longer changes status; the transitions endpoint does.
    rejected = client.patch(
        f"/api/v1/production/production-orders/{production_order_id}",
        json={"status": "released"},
        headers=auth_headers,
    )
    assert rejected.status_code == 422
    resp = client.post(
        f"/api/v1/production/production-orders/{production_order_id}/transitions",
        json={"action": "release"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "released"


def test_update_not_found(client, auth_headers):
    resp = client.patch(
        f"/api/v1/production/production-orders/{ZERO_UUID}",
        json={"notes": "missing"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_tenant_isolation(client, db, auth_headers, work_center):
    first_order = _create_order(client, auth_headers, work_center["id"])

    other_org = _create_org(db, code="production-order-tenant-org")
    _create_user(db, other_org, email="production-order-tenant@example.com")
    other_headers = _login(client, "production-order-tenant@example.com")

    second_wc = client.post(
        "/api/v1/production/work-centers",
        json={"code": "WC-SECOND", "name": "Second Org Line", "center_type": "extrusion"},
        headers=other_headers,
    )
    assert second_wc.status_code == 201
    second_order = _create_order(client, other_headers, second_wc.json()["id"])

    list_resp = client.get("/api/v1/production/production-orders", headers=auth_headers)

    assert list_resp.status_code == 200
    data = list_resp.json()["items"]
    assert len(data) == 1
    assert data[0]["id"] == first_order.json()["id"]
    assert data[0]["id"] != second_order.json()["id"]

    get_resp = client.get(
        f"/api/v1/production/production-orders/{second_order.json()['id']}",
        headers=auth_headers,
    )
    assert get_resp.status_code == 404
