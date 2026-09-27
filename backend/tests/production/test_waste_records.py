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
    ShiftReportStatus,
    ShiftType,
    WorkCenterStatus,
    WorkCenterType,
)
from app.production.infrastructure.models import ProductionOrder, ShiftDefinition, ShiftReport, WorkCenter
from tests.production.conftest import grant_production_role


WASTE_BASE = "/api/v1/production/waste-records"


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


def _base_shift_definition(work_center_id: str, code="SD-WASTE-001") -> dict:
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


def _base_item(**overrides) -> dict:
    payload = {
        "planned_quantity": "12.50",
        "unit": "kg",
        "notes": "Roll line item",
    }
    payload.update(overrides)
    return payload


def _base_shift_report(work_center_id: str, shift_definition_id: str, **overrides) -> dict:
    payload = {
        "work_center_id": work_center_id,
        "shift_definition_id": shift_definition_id,
        "report_date": "2026-07-01",
        "summary": "Morning shift summary",
    }
    payload.update(overrides)
    return payload


def _base_waste(production_order_id: str, work_center_id: str, **overrides) -> dict:
    payload = {
        "production_order_id": production_order_id,
        "work_center_id": work_center_id,
        "waste_date": "2026-07-01",
        "quantity_wasted": "10.25",
        "unit": "kg",
        "waste_category": "startup_loss",
    }
    payload.update(overrides)
    return payload


def _items_url(production_order_id: str) -> str:
    return f"/api/v1/production/production-orders/{production_order_id}/items"


def _create_work_center(client, auth_headers, code="WC-WASTE-001"):
    resp = client.post(
        "/api/v1/production/work-centers",
        json={"code": code, "name": "Line 1", "center_type": "extrusion"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp


def _create_shift_definition(client, auth_headers, work_center_id: str, code="SD-WASTE-001"):
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


def _create_item(client, auth_headers, production_order_id: str, **overrides):
    resp = client.post(
        _items_url(production_order_id),
        json=_base_item(**overrides),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp


def _create_shift_report(client, auth_headers, work_center_id: str, shift_definition_id: str, **overrides):
    resp = client.post(
        "/api/v1/production/shift-reports",
        json=_base_shift_report(work_center_id, shift_definition_id, **overrides),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp


def _create_waste(client, auth_headers, production_order_id: str, work_center_id: str, **overrides):
    resp = client.post(
        WASTE_BASE,
        json=_base_waste(production_order_id, work_center_id, **overrides),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp


def _create_foreign_work_center(db, org: Organization, code="WC-FOREIGN-WASTE") -> WorkCenter:
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
    code="SD-FOREIGN-WASTE",
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
    number="PO-FOREIGN-WASTE-001",
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


def _create_foreign_shift_report(
    db,
    org: Organization,
    user: User,
    work_center: WorkCenter,
    shift_definition: ShiftDefinition,
) -> ShiftReport:
    shift_report = ShiftReport(
        organization_id=org.id,
        work_center_id=work_center.id,
        shift_definition_id=shift_definition.id,
        report_date=date(2026, 7, 1),
        status=ShiftReportStatus.DRAFT,
        summary="Foreign shift summary",
        created_by_user_id=user.id,
    )
    db.add(shift_report)
    db.commit()
    db.refresh(shift_report)
    return shift_report


@pytest.fixture
def work_center(client, auth_headers):
    return _create_work_center(client, auth_headers).json()


@pytest.fixture
def shift_definition(client, auth_headers, work_center):
    return _create_shift_definition(client, auth_headers, work_center["id"]).json()


@pytest.fixture
def production_order(client, auth_headers, work_center):
    return _create_order(client, auth_headers, work_center["id"]).json()


@pytest.fixture
def production_order_item(client, auth_headers, production_order):
    return _create_item(client, auth_headers, production_order["id"]).json()


@pytest.fixture
def shift_report(client, auth_headers, work_center, shift_definition):
    return _create_shift_report(client, auth_headers, work_center["id"], shift_definition["id"]).json()


def test_create_waste_record_minimal(client, auth_headers, production_order, work_center):
    resp = client.post(
        WASTE_BASE,
        json=_base_waste(production_order["id"], work_center["id"]),
        headers=auth_headers,
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["organization_id"] is not None
    assert data["created_by_user_id"] is not None
    assert data["shift_report_id"] is None
    assert data["production_order_item_id"] is None
    assert data["reason_code"] is None
    assert data["notes"] is None


def test_create_waste_record_full(
    client,
    auth_headers,
    production_order,
    work_center,
    shift_report,
    production_order_item,
):
    resp = client.post(
        WASTE_BASE,
        json=_base_waste(
            production_order["id"],
            work_center["id"],
            shift_report_id=shift_report["id"],
            production_order_item_id=production_order_item["id"],
            waste_date="2026-07-02",
            quantity_wasted="15.75",
            unit="m",
            waste_category="trim_loss",
            reason_code="Edge trimming during size adjustment",
            notes="Observed during rewinding",
        ),
        headers=auth_headers,
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["production_order_id"] == production_order["id"]
    assert data["work_center_id"] == work_center["id"]
    assert data["shift_report_id"] == shift_report["id"]
    assert data["production_order_item_id"] == production_order_item["id"]
    assert data["waste_date"] == "2026-07-02"
    assert data["quantity_wasted"] == "15.75"
    assert data["unit"] == "m"
    assert data["waste_category"] == "trim_loss"
    assert data["reason_code"] == "Edge trimming during size adjustment"
    assert data["notes"] == "Observed during rewinding"


def test_create_quantity_zero_rejected(client, auth_headers, production_order, work_center):
    resp = client.post(
        WASTE_BASE,
        json=_base_waste(production_order["id"], work_center["id"], quantity_wasted="0"),
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_create_quantity_negative_rejected(client, auth_headers, production_order, work_center):
    resp = client.post(
        WASTE_BASE,
        json=_base_waste(production_order["id"], work_center["id"], quantity_wasted="-1"),
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_create_wrong_org_production_order_rejected(client, db, auth_headers, work_center):
    other_org = _create_org(db, code="waste-foreign-order-org")
    other_user = _create_user(db, other_org, email="waste-foreign-order@example.com")
    foreign_wc = _create_foreign_work_center(db, other_org)
    foreign_order = _create_foreign_production_order(db, other_org, other_user, foreign_wc)

    resp = client.post(
        WASTE_BASE,
        json=_base_waste(str(foreign_order.id), work_center["id"]),
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_create_wrong_org_work_center_rejected(client, db, auth_headers, production_order):
    other_org = _create_org(db, code="waste-foreign-wc-org")
    foreign_wc = _create_foreign_work_center(db, other_org)

    resp = client.post(
        WASTE_BASE,
        json=_base_waste(production_order["id"], str(foreign_wc.id)),
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_create_wrong_org_shift_report_rejected(client, db, auth_headers, production_order, work_center):
    other_org = _create_org(db, code="waste-foreign-report-org")
    other_user = _create_user(db, other_org, email="waste-foreign-report@example.com")
    foreign_wc = _create_foreign_work_center(db, other_org)
    foreign_sd = _create_foreign_shift_definition(db, other_org, foreign_wc)
    foreign_report = _create_foreign_shift_report(db, other_org, other_user, foreign_wc, foreign_sd)

    resp = client.post(
        WASTE_BASE,
        json=_base_waste(
            production_order["id"],
            work_center["id"],
            shift_report_id=str(foreign_report.id),
        ),
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_create_item_wrong_order_rejected(client, auth_headers, production_order, work_center):
    second_order = _create_order(
        client,
        auth_headers,
        work_center["id"],
        production_order_number="PO-WASTE-SECOND",
    )
    other_item = _create_item(client, auth_headers, second_order.json()["id"])

    resp = client.post(
        WASTE_BASE,
        json=_base_waste(
            production_order["id"],
            work_center["id"],
            production_order_item_id=other_item.json()["id"],
        ),
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_list_returns_own_org_only(client, auth_headers, production_order, work_center):
    _create_waste(client, auth_headers, production_order["id"], work_center["id"])
    _create_waste(
        client,
        auth_headers,
        production_order["id"],
        work_center["id"],
        waste_category="trim_loss",
    )

    resp = client.get(WASTE_BASE, headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_cross_tenant_isolation(client, db, auth_headers, production_order, work_center):
    first_waste = _create_waste(client, auth_headers, production_order["id"], work_center["id"])

    other_org = _create_org(db, code="waste-tenant-org")
    _create_user(db, other_org, email="waste-tenant@example.com")
    other_headers = _login(client, "waste-tenant@example.com")
    other_wc = _create_work_center(client, other_headers, code="WC-WASTE-TENANT")
    other_order = _create_order(client, other_headers, other_wc.json()["id"])
    other_waste = _create_waste(client, other_headers, other_order.json()["id"], other_wc.json()["id"])

    resp = client.get(WASTE_BASE, headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == first_waste.json()["id"]
    assert resp.json()[0]["id"] != other_waste.json()["id"]


def test_list_filter_by_production_order_id(client, auth_headers, production_order, work_center):
    second_order = _create_order(
        client,
        auth_headers,
        work_center["id"],
        production_order_number="PO-WASTE-FILTER-ORDER",
    )
    first = _create_waste(client, auth_headers, production_order["id"], work_center["id"])
    _create_waste(client, auth_headers, second_order.json()["id"], work_center["id"])

    resp = client.get(
        f"{WASTE_BASE}?production_order_id={production_order['id']}",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == first.json()["id"]


def test_list_filter_by_shift_report_id(client, auth_headers, production_order, work_center, shift_report):
    first = _create_waste(
        client,
        auth_headers,
        production_order["id"],
        work_center["id"],
        shift_report_id=shift_report["id"],
    )
    _create_waste(client, auth_headers, production_order["id"], work_center["id"])

    resp = client.get(
        f"{WASTE_BASE}?shift_report_id={shift_report['id']}",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == first.json()["id"]


def test_list_filter_by_work_center_id(client, auth_headers, production_order, work_center):
    second_wc = _create_work_center(client, auth_headers, code="WC-WASTE-002")
    second_order = _create_order(
        client,
        auth_headers,
        second_wc.json()["id"],
        production_order_number="PO-WASTE-WC-002",
    )
    first = _create_waste(client, auth_headers, production_order["id"], work_center["id"])
    _create_waste(client, auth_headers, second_order.json()["id"], second_wc.json()["id"])

    resp = client.get(
        f"{WASTE_BASE}?work_center_id={work_center['id']}",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == first.json()["id"]


def test_list_filter_by_waste_category(client, auth_headers, production_order, work_center):
    _create_waste(client, auth_headers, production_order["id"], work_center["id"])
    trim_loss = _create_waste(
        client,
        auth_headers,
        production_order["id"],
        work_center["id"],
        waste_category="trim_loss",
    )

    resp = client.get(f"{WASTE_BASE}?waste_category=trim_loss", headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == trim_loss.json()["id"]
    assert resp.json()[0]["waste_category"] == "trim_loss"


def test_list_filter_by_waste_date(client, auth_headers, production_order, work_center):
    first = _create_waste(
        client,
        auth_headers,
        production_order["id"],
        work_center["id"],
        waste_date="2026-07-01",
    )
    _create_waste(
        client,
        auth_headers,
        production_order["id"],
        work_center["id"],
        waste_date="2026-07-02",
    )

    resp = client.get(f"{WASTE_BASE}?waste_date=2026-07-01", headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == first.json()["id"]
    assert resp.json()[0]["waste_date"] == "2026-07-01"


def test_get_by_id_returns_notes(client, auth_headers, production_order, work_center):
    create_resp = _create_waste(
        client,
        auth_headers,
        production_order["id"],
        work_center["id"],
        notes="scrap from startup",
    )

    resp = client.get(f"{WASTE_BASE}/{create_resp.json()['id']}", headers=auth_headers)

    assert resp.status_code == 200
    assert "notes" in resp.json()
    assert resp.json()["notes"] == "scrap from startup"


def test_get_by_id_wrong_org_returns_404(client, db, auth_headers):
    other_org = _create_org(db, code="waste-wrong-org")
    _create_user(db, other_org, email="waste-wrong-org@example.com")
    other_headers = _login(client, "waste-wrong-org@example.com")
    other_wc = _create_work_center(client, other_headers, code="WC-WASTE-WRONG")
    other_order = _create_order(client, other_headers, other_wc.json()["id"])
    other_waste = _create_waste(client, other_headers, other_order.json()["id"], other_wc.json()["id"])

    resp = client.get(f"{WASTE_BASE}/{other_waste.json()['id']}", headers=auth_headers)

    assert resp.status_code == 404


def test_patch_update_quantity(client, auth_headers, production_order, work_center):
    create_resp = _create_waste(client, auth_headers, production_order["id"], work_center["id"])

    resp = client.patch(
        f"{WASTE_BASE}/{create_resp.json()['id']}",
        json={"quantity_wasted": "50.00"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["quantity_wasted"] == "50.00"


def test_patch_set_production_order_null_rejected(client, auth_headers, production_order, work_center):
    create_resp = _create_waste(client, auth_headers, production_order["id"], work_center["id"])

    resp = client.patch(
        f"{WASTE_BASE}/{create_resp.json()['id']}",
        json={"production_order_id": None},
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_patch_set_work_center_null_rejected(client, auth_headers, production_order, work_center):
    create_resp = _create_waste(client, auth_headers, production_order["id"], work_center["id"])

    resp = client.patch(
        f"{WASTE_BASE}/{create_resp.json()['id']}",
        json={"work_center_id": None},
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_patch_quantity_zero_rejected(client, auth_headers, production_order, work_center):
    create_resp = _create_waste(client, auth_headers, production_order["id"], work_center["id"])

    resp = client.patch(
        f"{WASTE_BASE}/{create_resp.json()['id']}",
        json={"quantity_wasted": "0"},
        headers=auth_headers,
    )

    assert resp.status_code == 422


def test_unauthenticated_request_rejected(client, production_order, work_center):
    resp = client.post(
        WASTE_BASE,
        json=_base_waste(production_order["id"], work_center["id"]),
    )
    assert resp.status_code == 401
