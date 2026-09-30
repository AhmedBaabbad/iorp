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
from app.production.infrastructure.models import (
    ProductionOrder,
    ShiftDefinition,
    WorkCenter,
)
from tests.production.conftest import grant_production_role


ZERO_UUID = "00000000-0000-0000-0000-000000000000"
OUTPUTS_BASE = "/api/v1/production/production-outputs"


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


def _base_shift_definition(work_center_id: str, code="SD-001") -> dict:
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


def _base_output(production_order_id: str, work_center_id: str, **overrides) -> dict:
    payload = {
        "production_order_id": production_order_id,
        "work_center_id": work_center_id,
        "output_date": "2026-07-01",
        "quantity_produced": "85.50",
        "unit": "kg",
    }
    payload.update(overrides)
    return payload


def _create_work_center(client, auth_headers, code="WC-OUT-001"):
    resp = client.post(
        "/api/v1/production/work-centers",
        json={"code": code, "name": "Line 1", "center_type": "extrusion"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp


def _create_shift_definition(client, auth_headers, work_center_id: str, code="SD-001"):
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


def _create_output(client, auth_headers, production_order_id: str, work_center_id: str, **overrides):
    resp = client.post(
        OUTPUTS_BASE,
        json=_base_output(production_order_id, work_center_id, **overrides),
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
    number="PO-FOREIGN-001",
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


def test_create_output_minimal(client, auth_headers, production_order, work_center):
    resp = client.post(
        OUTPUTS_BASE,
        json=_base_output(production_order["id"], work_center["id"]),
        headers=auth_headers,
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["output_status"] == "recorded"
    assert "organization_id" in data
    assert "created_by_user_id" in data


def test_create_output_with_recorded_at(client, auth_headers, production_order, work_center):
    resp = client.post(
        OUTPUTS_BASE,
        json=_base_output(
            production_order["id"],
            work_center["id"],
            recorded_at="2026-07-01T08:30:00+00:00",
        ),
        headers=auth_headers,
    )

    assert resp.status_code == 201
    assert resp.json()["recorded_at"] == "2026-07-01T08:30:00+00:00"


def test_create_output_quantity_zero_rejected(client, auth_headers, production_order, work_center):
    resp = client.post(
        OUTPUTS_BASE,
        json=_base_output(production_order["id"], work_center["id"], quantity_produced="0.00"),
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_create_output_quantity_negative_rejected(client, auth_headers, production_order, work_center):
    resp = client.post(
        OUTPUTS_BASE,
        json=_base_output(production_order["id"], work_center["id"], quantity_produced="-10.00"),
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_create_output_requires_auth(client, production_order, work_center):
    resp = client.post(
        OUTPUTS_BASE,
        json=_base_output(production_order["id"], work_center["id"]),
    )
    assert resp.status_code == 401


def test_create_output_production_order_not_in_org(client, db, auth_headers, work_center):
    other_org = _create_org(db, code="output-foreign-order-org")
    other_user = _create_user(db, other_org, email="output-foreign-order@example.com")
    foreign_wc = _create_foreign_work_center(db, other_org)
    foreign_order = _create_foreign_production_order(db, other_org, other_user, foreign_wc)

    resp = client.post(
        OUTPUTS_BASE,
        json=_base_output(str(foreign_order.id), work_center["id"]),
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_create_output_work_center_not_in_org(client, db, auth_headers, production_order):
    other_org = _create_org(db, code="output-foreign-wc-org")
    foreign_wc = _create_foreign_work_center(db, other_org)

    resp = client.post(
        OUTPUTS_BASE,
        json=_base_output(production_order["id"], str(foreign_wc.id)),
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_list_no_filter(client, auth_headers, production_order, work_center):
    _create_output(client, auth_headers, production_order["id"], work_center["id"])
    _create_output(client, auth_headers, production_order["id"], work_center["id"], output_date="2026-07-02")

    resp = client.get(OUTPUTS_BASE, headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_filter_by_production_order_id(client, auth_headers, production_order, work_center):
    second_order = _create_order(
        client,
        auth_headers,
        work_center["id"],
        production_order_number="PO-OUT-SECOND",
    )
    _create_output(client, auth_headers, production_order["id"], work_center["id"])
    _create_output(client, auth_headers, second_order.json()["id"], work_center["id"])

    resp = client.get(
        f"{OUTPUTS_BASE}?production_order_id={production_order['id']}",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_filter_by_work_center_id(client, auth_headers, production_order, work_center):
    second_wc = _create_work_center(client, auth_headers, code="WC-OUT-002")
    second_order = _create_order(
        client,
        auth_headers,
        second_wc.json()["id"],
        production_order_number="PO-OUT-WC-002",
    )
    _create_output(client, auth_headers, production_order["id"], work_center["id"])
    _create_output(client, auth_headers, second_order.json()["id"], second_wc.json()["id"])

    resp = client.get(
        f"{OUTPUTS_BASE}?work_center_id={work_center['id']}",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_filter_by_output_date(client, auth_headers, production_order, work_center):
    _create_output(client, auth_headers, production_order["id"], work_center["id"], output_date="2026-07-01")
    _create_output(client, auth_headers, production_order["id"], work_center["id"], output_date="2026-07-02")

    resp = client.get(f"{OUTPUTS_BASE}?output_date=2026-07-01", headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_filter_by_output_status(client, auth_headers, production_order, work_center):
    _create_output(client, auth_headers, production_order["id"], work_center["id"])

    recorded_resp = client.get(f"{OUTPUTS_BASE}?output_status=recorded", headers=auth_headers)
    verified_resp = client.get(f"{OUTPUTS_BASE}?output_status=verified", headers=auth_headers)

    assert recorded_resp.status_code == 200
    assert len(recorded_resp.json()) >= 1
    assert all(item["output_status"] == "recorded" for item in recorded_resp.json())
    assert verified_resp.status_code == 200
    assert verified_resp.json() == []


def test_get_output(client, auth_headers, production_order, work_center):
    create_resp = _create_output(client, auth_headers, production_order["id"], work_center["id"])
    production_output_id = create_resp.json()["id"]

    resp = client.get(f"{OUTPUTS_BASE}/{production_output_id}", headers=auth_headers)

    assert resp.status_code == 200
    assert "notes" in resp.json()


def test_get_not_found(client, auth_headers):
    resp = client.get(f"{OUTPUTS_BASE}/{ZERO_UUID}", headers=auth_headers)
    assert resp.status_code == 404


def test_update_output_status(client, auth_headers, production_order, work_center):
    create_resp = _create_output(client, auth_headers, production_order["id"], work_center["id"])
    production_output_id = create_resp.json()["id"]

    resp = client.patch(
        f"{OUTPUTS_BASE}/{production_output_id}",
        json={"output_status": "verified"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["output_status"] == "verified"


def test_update_quantity(client, auth_headers, production_order, work_center):
    create_resp = _create_output(client, auth_headers, production_order["id"], work_center["id"])
    production_output_id = create_resp.json()["id"]

    resp = client.patch(
        f"{OUTPUTS_BASE}/{production_output_id}",
        json={"quantity_produced": "120.00"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["quantity_produced"] == "120.00"


def test_tenant_isolation(client, db, auth_headers, production_order, work_center):
    first_output = _create_output(client, auth_headers, production_order["id"], work_center["id"])

    other_org = _create_org(db, code="output-tenant-org")
    _create_user(db, other_org, email="output-tenant@example.com")
    other_headers = _login(client, "output-tenant@example.com")

    other_wc = _create_work_center(client, other_headers, code="WC-OUT-TENANT")
    other_order = _create_order(client, other_headers, other_wc.json()["id"])
    other_output = _create_output(client, other_headers, other_order.json()["id"], other_wc.json()["id"])

    list_resp = client.get(OUTPUTS_BASE, headers=auth_headers)
    get_resp = client.get(f"{OUTPUTS_BASE}/{other_output.json()['id']}", headers=auth_headers)

    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1
    assert list_resp.json()[0]["id"] == first_output.json()["id"]
    assert get_resp.status_code == 404
