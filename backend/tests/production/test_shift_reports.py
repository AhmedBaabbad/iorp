from tests.production.order_fixtures import historical_order
from datetime import date, time
from decimal import Decimal
from uuid import UUID

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
SHIFT_REPORTS_BASE = "/api/v1/production/shift-reports"


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


def _base_shift_definition(work_center_id: str, code: str = "SD-001") -> dict:
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


def _base_report(work_center_id: str, shift_definition_id: str, **overrides) -> dict:
    payload = {
        "work_center_id": work_center_id,
        "shift_definition_id": shift_definition_id,
        "report_date": "2026-07-01",
        "summary": "Morning shift summary",
    }
    payload.update(overrides)
    return payload


def _create_work_center(client, auth_headers, code="WC-SR-001"):
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


def _create_report(client, auth_headers, work_center_id: str, shift_definition_id: str, **overrides):
    resp = client.post(
        SHIFT_REPORTS_BASE,
        json=_base_report(work_center_id, shift_definition_id, **overrides),
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


def test_create_shift_report_minimal(client, auth_headers, work_center, shift_definition):
    resp = client.post(
        SHIFT_REPORTS_BASE,
        json=_base_report(work_center["id"], shift_definition["id"]),
        headers=auth_headers,
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "draft"
    assert "organization_id" in data
    assert "created_by_user_id" in data


def test_create_with_timestamps(client, auth_headers, work_center, shift_definition):
    resp = client.post(
        SHIFT_REPORTS_BASE,
        json=_base_report(
            work_center["id"],
            shift_definition["id"],
            shift_started_at="2026-07-01T06:00:00+00:00",
            shift_ended_at="2026-07-01T14:00:00+00:00",
        ),
        headers=auth_headers,
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["shift_started_at"] == "2026-07-01T06:00:00+00:00"
    assert data["shift_ended_at"] == "2026-07-01T14:00:00+00:00"


def test_create_ended_before_started_rejected(client, auth_headers, work_center, shift_definition):
    resp = client.post(
        SHIFT_REPORTS_BASE,
        json=_base_report(
            work_center["id"],
            shift_definition["id"],
            shift_started_at="2026-07-01T14:00:00+00:00",
            shift_ended_at="2026-07-01T06:00:00+00:00",
        ),
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_create_with_production_order_id(client, auth_headers, work_center, shift_definition):
    production_order = _create_order(client, auth_headers, work_center["id"])

    resp = client.post(
        SHIFT_REPORTS_BASE,
        json=_base_report(
            work_center["id"],
            shift_definition["id"],
            production_order_id=production_order.json()["id"],
        ),
        headers=auth_headers,
    )

    assert resp.status_code == 201
    assert resp.json()["production_order_id"] == production_order.json()["id"]


def test_create_requires_auth(client, work_center, shift_definition):
    resp = client.post(
        SHIFT_REPORTS_BASE,
        json=_base_report(work_center["id"], shift_definition["id"]),
    )
    assert resp.status_code == 401


def test_create_work_center_not_in_org(client, db, auth_headers, shift_definition):
    other_org = _create_org(db, code="shift-report-foreign-wc-org")
    foreign_work_center = _create_foreign_work_center(db, other_org)

    resp = client.post(
        SHIFT_REPORTS_BASE,
        json=_base_report(str(foreign_work_center.id), shift_definition["id"]),
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_create_shift_definition_not_in_org(client, db, auth_headers, work_center):
    other_org = _create_org(db, code="shift-report-foreign-sd-org")
    foreign_work_center = _create_foreign_work_center(db, other_org)
    foreign_shift_definition = _create_foreign_shift_definition(db, other_org, foreign_work_center)

    resp = client.post(
        SHIFT_REPORTS_BASE,
        json=_base_report(work_center["id"], str(foreign_shift_definition.id)),
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_create_production_order_not_in_org(client, db, auth_headers, work_center, shift_definition):
    other_org = _create_org(db, code="shift-report-foreign-po-org")
    other_user = _create_user(db, other_org, email="shift-report-foreign-po@example.com")
    foreign_work_center = _create_foreign_work_center(db, other_org)
    foreign_order = _create_foreign_production_order(
        db,
        other_org,
        other_user,
        foreign_work_center,
    )

    resp = client.post(
        SHIFT_REPORTS_BASE,
        json=_base_report(
            work_center["id"],
            shift_definition["id"],
            production_order_id=str(foreign_order.id),
        ),
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_list_no_filter(client, auth_headers, work_center, shift_definition):
    _create_report(client, auth_headers, work_center["id"], shift_definition["id"])
    _create_report(client, auth_headers, work_center["id"], shift_definition["id"], report_date="2026-07-02")

    resp = client.get(SHIFT_REPORTS_BASE, headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_filter_by_status(client, auth_headers, work_center, shift_definition):
    _create_report(client, auth_headers, work_center["id"], shift_definition["id"])

    draft_resp = client.get(f"{SHIFT_REPORTS_BASE}?status=draft", headers=auth_headers)
    submitted_resp = client.get(f"{SHIFT_REPORTS_BASE}?status=submitted", headers=auth_headers)

    assert draft_resp.status_code == 200
    assert len(draft_resp.json()) >= 1
    assert all(item["status"] == "draft" for item in draft_resp.json())
    assert submitted_resp.status_code == 200
    assert submitted_resp.json() == []


def test_list_filter_by_work_center_id(client, auth_headers, work_center, shift_definition):
    second_wc = _create_work_center(client, auth_headers, code="WC-SR-002")
    second_sd = _create_shift_definition(client, auth_headers, second_wc.json()["id"], code="SD-002")
    _create_report(client, auth_headers, work_center["id"], shift_definition["id"])
    _create_report(client, auth_headers, second_wc.json()["id"], second_sd.json()["id"])

    resp = client.get(
        f"{SHIFT_REPORTS_BASE}?work_center_id={work_center['id']}",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["work_center_id"] == str(UUID(work_center["id"]))


def test_list_filter_by_shift_definition_id(client, auth_headers, work_center, shift_definition):
    second_wc = _create_work_center(client, auth_headers, code="WC-SR-002")
    second_sd = _create_shift_definition(client, auth_headers, second_wc.json()["id"], code="SD-002")
    _create_report(client, auth_headers, work_center["id"], shift_definition["id"])
    _create_report(client, auth_headers, second_wc.json()["id"], second_sd.json()["id"])

    resp = client.get(
        f"{SHIFT_REPORTS_BASE}?shift_definition_id={shift_definition['id']}",
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_filter_by_report_date(client, auth_headers, work_center, shift_definition):
    _create_report(client, auth_headers, work_center["id"], shift_definition["id"], report_date="2026-07-01")
    _create_report(client, auth_headers, work_center["id"], shift_definition["id"], report_date="2026-07-02")

    resp = client.get(f"{SHIFT_REPORTS_BASE}?report_date=2026-07-01", headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_shift_report(client, auth_headers, work_center, shift_definition):
    create_resp = _create_report(client, auth_headers, work_center["id"], shift_definition["id"])
    shift_report_id = create_resp.json()["id"]

    resp = client.get(f"{SHIFT_REPORTS_BASE}/{shift_report_id}", headers=auth_headers)

    assert resp.status_code == 200
    assert "notes" in resp.json()


def test_get_not_found(client, auth_headers):
    resp = client.get(f"{SHIFT_REPORTS_BASE}/{ZERO_UUID}", headers=auth_headers)
    assert resp.status_code == 404


def test_update_status_to_submitted(client, auth_headers, work_center, shift_definition):
    create_resp = _create_report(client, auth_headers, work_center["id"], shift_definition["id"])
    shift_report_id = create_resp.json()["id"]

    resp = client.patch(
        f"{SHIFT_REPORTS_BASE}/{shift_report_id}",
        json={"status": "submitted"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "submitted"
    assert data["shift_ended_at"] is not None


def test_update_status_to_approved(client, auth_headers, work_center, shift_definition):
    create_resp = _create_report(client, auth_headers, work_center["id"], shift_definition["id"])
    shift_report_id = create_resp.json()["id"]

    submitted_resp = client.patch(
        f"{SHIFT_REPORTS_BASE}/{shift_report_id}",
        json={"status": "submitted"},
        headers=auth_headers,
    )
    approved_resp = client.patch(
        f"{SHIFT_REPORTS_BASE}/{shift_report_id}",
        json={"status": "approved"},
        headers=auth_headers,
    )

    assert submitted_resp.status_code == 200
    assert approved_resp.status_code == 200
    assert approved_resp.json()["status"] == "approved"


def test_tenant_isolation(client, db, auth_headers, work_center, shift_definition):
    first_report = _create_report(client, auth_headers, work_center["id"], shift_definition["id"])

    other_org = _create_org(db, code="shift-report-tenant-org")
    _create_user(db, other_org, email="shift-report-tenant@example.com")
    other_headers = _login(client, "shift-report-tenant@example.com")

    other_wc = _create_work_center(client, other_headers, code="WC-SR-TENANT")
    other_sd = _create_shift_definition(client, other_headers, other_wc.json()["id"], code="SD-TENANT")
    other_report = _create_report(client, other_headers, other_wc.json()["id"], other_sd.json()["id"])

    list_resp = client.get(SHIFT_REPORTS_BASE, headers=auth_headers)
    get_resp = client.get(f"{SHIFT_REPORTS_BASE}/{other_report.json()['id']}", headers=auth_headers)

    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1
    assert list_resp.json()[0]["id"] == first_report.json()["id"]
    assert get_resp.status_code == 404
