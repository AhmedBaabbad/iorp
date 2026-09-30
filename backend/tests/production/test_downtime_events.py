from tests.production.order_fixtures import historical_order
from datetime import date, time
from decimal import Decimal

import pytest

from app.core.security import hash_password
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, User
from app.production.domain.enums import (
    ProductionOrderPriority,
    ProductionOrderStatus,
    ShiftDefinitionStatus,
    ShiftType,
    WorkCenterStatus,
    WorkCenterType,
)
from app.production.infrastructure.models import ProductionOrder, ShiftDefinition, WorkCenter
from tests.production.conftest import grant_production_role


ZERO_UUID = "00000000-0000-0000-0000-000000000000"
DOWNTIME_BASE = "/api/v1/production/downtime-events"


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


def _base_shift_definition(work_center_id: str, code="SD-DT-001") -> dict:
    return {
        "code": code,
        "name": "Morning",
        "shift_type": "morning",
        "start_time": "07:00:00",
        "end_time": "15:00:00",
    }


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


def _base_downtime(work_center_id: str, **overrides) -> dict:
    payload = {
        "work_center_id": work_center_id,
        "start_time": "2026-07-01T06:00:00Z",
        "category": "machine",
        "reason_code": "Bearing failure on motor 2",
    }
    payload.update(overrides)
    return payload


def _create_work_center(client, auth_headers, code="WC-DT-001"):
    resp = client.post(
        "/api/v1/production/work-centers",
        json={"code": code, "name": "Line 1", "center_type": "extrusion"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp


def _create_shift_definition(client, auth_headers, work_center_id: str, code="SD-DT-001"):
    resp = client.post(
        "/api/v1/production/shift-definitions",
        json=_base_shift_definition(work_center_id, code),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp


def _create_order(client, auth_headers, work_center_id: str, **overrides):
    resp = historical_order(client, auth_headers, _base_order(work_center_id, **overrides))
    assert resp.status_code == 201
    return resp


def _create_downtime(client, auth_headers, work_center_id: str, **overrides):
    resp = client.post(
        DOWNTIME_BASE,
        json=_base_downtime(work_center_id, **overrides),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp


def _create_foreign_work_center(db, org: Organization, code="WC-FOREIGN") -> WorkCenter:
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
    code="SD-FOREIGN",
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


def _create_foreign_production_order(
    db,
    org: Organization,
    user: User,
    work_center: WorkCenter,
    number="PO-FOREIGN-DT-001",
) -> ProductionOrder:
    production_order = ProductionOrder(
        organization_id=org.id,
        production_order_number=number,
        work_center_id=work_center.id,
        product_type="PE Film",
        planned_quantity=Decimal("100.00"),
        unit="kg",
        priority=ProductionOrderPriority.NORMAL,
        status=ProductionOrderStatus.DRAFT,
        planned_start_date=date(2026, 7, 1),
        planned_end_date=date(2026, 7, 2),
        created_by_user_id=user.id,
    )
    db.add(production_order)
    db.commit()
    db.refresh(production_order)
    return production_order


@pytest.fixture
def work_center(client, auth_headers):
    return _create_work_center(client, auth_headers).json()


@pytest.fixture
def shift_definition(client, auth_headers, work_center):
    return _create_shift_definition(client, auth_headers, work_center["id"]).json()


@pytest.fixture
def production_order(client, auth_headers, work_center):
    return _create_order(client, auth_headers, work_center["id"]).json()


def test_create_open_downtime_event(client, auth_headers, work_center):
    resp = client.post(
        DOWNTIME_BASE,
        json=_base_downtime(work_center["id"]),
        headers=auth_headers,
    )

    assert resp.status_code == 201
    assert resp.json()["status"] == "open"
    assert resp.json()["duration_minutes"] is None


def test_create_closed_downtime_event(client, auth_headers, work_center):
    resp = client.post(
        DOWNTIME_BASE,
        json=_base_downtime(
            work_center["id"],
            start_time="2026-07-01T06:00:00Z",
            end_time="2026-07-01T07:30:00Z",
        ),
        headers=auth_headers,
    )

    assert resp.status_code == 201
    assert resp.json()["status"] == "closed"
    assert resp.json()["duration_minutes"] == 90


def test_create_duration_calculation_precision(client, auth_headers, work_center):
    resp = client.post(
        DOWNTIME_BASE,
        json=_base_downtime(
            work_center["id"],
            start_time="2026-07-01T06:00:00Z",
            end_time="2026-07-01T06:45:00Z",
        ),
        headers=auth_headers,
    )

    assert resp.status_code == 201
    assert resp.json()["duration_minutes"] == 45


def test_create_end_time_before_start_time_rejected(client, auth_headers, work_center):
    resp = client.post(
        DOWNTIME_BASE,
        json=_base_downtime(
            work_center["id"],
            start_time="2026-07-01T07:00:00Z",
            end_time="2026-07-01T07:00:00Z",
        ),
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_create_invalid_work_center_rejected(client, db, auth_headers):
    other_org = _create_org(db, code="dt-foreign-wc-org")
    foreign_wc = _create_foreign_work_center(db, other_org)

    resp = client.post(
        DOWNTIME_BASE,
        json=_base_downtime(str(foreign_wc.id)),
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_create_invalid_production_order_rejected(client, db, auth_headers, work_center):
    other_org = _create_org(db, code="dt-foreign-order-org")
    other_user = _create_user(db, other_org, email="dt-foreign-order@example.com")
    foreign_wc = _create_foreign_work_center(db, other_org)
    foreign_order = _create_foreign_production_order(db, other_org, other_user, foreign_wc)

    resp = client.post(
        DOWNTIME_BASE,
        json=_base_downtime(work_center["id"], production_order_id=str(foreign_order.id)),
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_create_empty_reason_code_rejected(client, auth_headers, work_center):
    resp = client.post(
        DOWNTIME_BASE,
        json=_base_downtime(work_center["id"], reason_code=""),
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_list_returns_own_org_only(client, auth_headers, work_center):
    _create_downtime(client, auth_headers, work_center["id"])
    _create_downtime(client, auth_headers, work_center["id"], category="material")

    resp = client.get(DOWNTIME_BASE, headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_cross_tenant_isolation(client, db, auth_headers, work_center):
    first_event = _create_downtime(client, auth_headers, work_center["id"])

    other_org = _create_org(db, code="dt-tenant-org")
    _create_user(db, other_org, email="dt-tenant@example.com")
    other_headers = _login(client, "dt-tenant@example.com")
    other_wc = _create_work_center(client, other_headers, code="WC-DT-TENANT")
    other_event = _create_downtime(client, other_headers, other_wc.json()["id"])

    resp = client.get(DOWNTIME_BASE, headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == first_event.json()["id"]
    assert resp.json()[0]["id"] != other_event.json()["id"]


def test_list_filter_by_work_center_id(client, auth_headers, work_center):
    second_wc = _create_work_center(client, auth_headers, code="WC-DT-002")
    first = _create_downtime(client, auth_headers, work_center["id"])
    _create_downtime(client, auth_headers, second_wc.json()["id"])

    resp = client.get(
        f"{DOWNTIME_BASE}?work_center_id={work_center['id']}",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == first.json()["id"]


def test_list_filter_by_production_order_id(client, auth_headers, work_center, production_order):
    first = _create_downtime(client, auth_headers, work_center["id"], production_order_id=production_order["id"])
    _create_downtime(client, auth_headers, work_center["id"])

    resp = client.get(
        f"{DOWNTIME_BASE}?production_order_id={production_order['id']}",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == first.json()["id"]


def test_list_filter_by_status_open(client, auth_headers, work_center):
    open_event = _create_downtime(client, auth_headers, work_center["id"])
    _create_downtime(client, auth_headers, work_center["id"], end_time="2026-07-01T07:00:00Z")

    resp = client.get(f"{DOWNTIME_BASE}?status=open", headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == open_event.json()["id"]
    assert resp.json()[0]["status"] == "open"


def test_list_filter_by_category(client, auth_headers, work_center):
    machine_event = _create_downtime(client, auth_headers, work_center["id"], category="machine")
    _create_downtime(client, auth_headers, work_center["id"], category="material")

    resp = client.get(f"{DOWNTIME_BASE}?category=machine", headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == machine_event.json()["id"]
    assert resp.json()[0]["category"] == "machine"


def test_get_by_id_returns_notes(client, auth_headers, work_center):
    create_resp = _create_downtime(client, auth_headers, work_center["id"], notes="test note")
    event_id = create_resp.json()["id"]

    resp = client.get(f"{DOWNTIME_BASE}/{event_id}", headers=auth_headers)

    assert resp.status_code == 200
    assert "notes" in resp.json()
    assert resp.json()["notes"] == "test note"


def test_get_by_id_wrong_org_returns_404(client, db, auth_headers):
    other_org = _create_org(db, code="dt-wrong-org")
    _create_user(db, other_org, email="dt-wrong-org@example.com")
    other_headers = _login(client, "dt-wrong-org@example.com")
    other_wc = _create_work_center(client, other_headers, code="WC-DT-WRONG")
    other_event = _create_downtime(client, other_headers, other_wc.json()["id"])

    resp = client.get(f"{DOWNTIME_BASE}/{other_event.json()['id']}", headers=auth_headers)

    assert resp.status_code == 404


def test_patch_close_open_event(client, auth_headers, work_center):
    create_resp = _create_downtime(
        client,
        auth_headers,
        work_center["id"],
        start_time="2026-07-01T06:00:00Z",
    )

    resp = client.patch(
        f"{DOWNTIME_BASE}/{create_resp.json()['id']}",
        json={"end_time": "2026-07-01T07:30:00Z"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "closed"
    assert resp.json()["duration_minutes"] == 90


def test_patch_recalculates_duration_from_stored_start(client, auth_headers, work_center):
    create_resp = _create_downtime(
        client,
        auth_headers,
        work_center["id"],
        start_time="2026-07-01T06:00:00Z",
        end_time="2026-07-01T07:00:00Z",
    )
    assert create_resp.json()["duration_minutes"] == 60

    resp = client.patch(
        f"{DOWNTIME_BASE}/{create_resp.json()['id']}",
        json={"end_time": "2026-07-01T08:00:00Z"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["duration_minutes"] == 120


def test_patch_set_work_center_null_rejected(client, auth_headers, work_center):
    create_resp = _create_downtime(client, auth_headers, work_center["id"])

    resp = client.patch(
        f"{DOWNTIME_BASE}/{create_resp.json()['id']}",
        json={"work_center_id": None},
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_patch_set_start_time_null_rejected(client, auth_headers, work_center):
    create_resp = _create_downtime(client, auth_headers, work_center["id"])

    resp = client.patch(
        f"{DOWNTIME_BASE}/{create_resp.json()['id']}",
        json={"start_time": None},
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_patch_end_time_before_stored_start_rejected(client, auth_headers, work_center):
    create_resp = _create_downtime(
        client,
        auth_headers,
        work_center["id"],
        start_time="2026-07-01T08:00:00Z",
    )

    resp = client.patch(
        f"{DOWNTIME_BASE}/{create_resp.json()['id']}",
        json={"end_time": "2026-07-01T07:00:00Z"},
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_unauthenticated_request_rejected(client, work_center):
    resp = client.post(
        DOWNTIME_BASE,
        json=_base_downtime(work_center["id"]),
    )
    assert resp.status_code == 401
