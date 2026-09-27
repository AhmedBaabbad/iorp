"""Allocation acceptance and invariant tests (PROD-PLAN-002)."""
from copy import deepcopy
from datetime import date, time
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from app.main import app
from app.dependencies import get_current_user
from app.core.tenancy import TenantContext
from app.commercial.infrastructure.models import Customer
from app.foundation.infrastructure.models import Organization
from app.production.infrastructure.models import ProductionDemand, ProductionDemandItem, ProductionOrder, ProductionAllocation, WorkCenter, ShiftReport, ShiftDefinition

ROOT = "/api/v1/production"
PERMISSIONS = frozenset(["production:planning:allocate", "production:orders:create", "production:planning:read", "production:production_orders:read", "production:production_orders:write", "production:work_centers:write"] + [f"production:demands:{a}" for a in ("read", "create", "update")])
ITEM = {"product_type": "film", "required_quantity": "1000", "unit": "kg", "target_spec_json": {"width": 12, "color": "blue"}}


@pytest.fixture
def env(client, db, test_org, test_user):
    customer = Customer(organization_id=test_org.id, customer_code="C-ALLOC", name="Customer")
    center = WorkCenter(organization_id=test_org.id, code="WC-ALLOC", name="Line")
    db.add_all([customer, center]); db.commit()
    ctx = SimpleNamespace(user=SimpleNamespace(is_organization_root=False), auth_user=SimpleNamespace(permissions=PERMISSIONS), tenant=TenantContext(test_user.id, test_org.id, permissions=PERMISSIONS))
    app.dependency_overrides[get_current_user] = lambda: ctx
    def demand(items=None):
        r = client.post(f"{ROOT}/demands", json={"customer_id": str(customer.id), "items": items or [deepcopy(ITEM)]})
        assert r.status_code == 201, r.text
        demand_id = r.json()["id"]
        assert client.post(f"{ROOT}/demands/{demand_id}/status", json={"status": "ready_for_planning"}).status_code == 200
        return client.get(f"{ROOT}/demands/{demand_id}").json()
    def create(d, qty="600", **kwargs):
        data = dict(allocations=[{"production_demand_item_id": d["items"][0]["id"], "allocated_quantity": qty}], work_center_id=str(center.id), planned_start_date="2026-09-16", planned_end_date="2026-09-17")
        data.update(kwargs)
        return client.post(f"{ROOT}/planning/create-production-order", json=data)
    return SimpleNamespace(db=db, client=client, org=test_org, user=test_user, center=center, customer=customer, ctx=ctx, demand=demand, create=create)


def test_t01_t03_t04_single_order(env):
    d = env.demand(); r = env.create(d)
    assert r.status_code == 201, r.text
    body = r.json()
    assert Decimal(body["planned_quantity"]) == 600
    assert len(body["allocations"]) == 1
    assert body["allocations"][0]["unit"] == "kg"
    assert body["allocations"][0]["customer_name"] == "Customer"
    assert body["work_center"]["id"] == str(env.center.id)


def test_t02_t17_multiple_demands(env):
    a, b = env.demand(), env.demand()
    allocations = [{"production_demand_item_id": d["items"][0]["id"], "allocated_quantity": "300.123"} for d in (a,b)]
    r = env.create(a, allocations=allocations)
    assert r.status_code == 201, r.text
    assert Decimal(r.json()["planned_quantity"]) == Decimal("600.246")
    assert len(r.json()["allocations"]) == 2


def test_t05_t06_t07_t09_t14_t16_t36_split(env):
    d = env.demand()
    assert d["status"] == "ready_for_planning" and Decimal(d["items"][0]["allocated_quantity"]) == 0
    assert env.create(d).status_code == 201
    partial = env.client.get(f"{ROOT}/demands/{d['id']}").json()
    assert partial["status"] == "partially_planned"
    assert Decimal(partial["items"][0]["remaining_quantity"]) == 400
    assert Decimal(partial["allocation_percentage"]) == 60
    assert env.create(d, "400").status_code == 201
    full = env.client.get(f"{ROOT}/demands/{d['id']}").json()
    assert full["status"] == "planned" and Decimal(full["items"][0]["remaining_quantity"]) == 0
    assert len(full["items"][0]["allocations"]) == 2


def test_t08_t11_t13_overallocation_rollback(env):
    d = env.demand(); assert env.create(d).status_code == 201
    r = env.create(d, "400.001")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "ALLOCATION_QUANTITY_CONFLICT"
    assert r.json()["detail"]["reason"] == "OVER_ALLOCATION"
    assert Decimal(r.json()["detail"]["would_exceed_by"]) == Decimal("0.001")
    assert env.db.scalar(select(func.count()).select_from(ProductionOrder)) == 1
    assert env.db.scalar(select(func.sum(ProductionAllocation.allocated_quantity))) == 600


@pytest.mark.parametrize("quantity", ["0", "-1", "0.0001", "NaN", "Infinity"])
def test_t10_invalid_quantity(env, quantity):
    assert env.create(env.demand(), quantity).status_code == 400


@pytest.mark.parametrize("change", [{"product_type": "other"}, {"unit": "m"}, {"target_spec_json": {"width": 99}}])
def test_t18_t20_incompatible(env, change):
    d = env.demand([deepcopy(ITEM), {**deepcopy(ITEM), **change}])
    r = env.create(d, allocations=[{"production_demand_item_id": i["id"], "allocated_quantity": "100"} for i in d["items"]])
    assert r.status_code == 400 and r.json()["detail"]["code"] == "INCOMPATIBLE_DEMAND_ITEMS"
    assert env.db.scalar(select(func.count()).select_from(ProductionOrder)) == 0


def test_t21_t24_t25_t34_t35_model_columns():
    assert "commercial_order_id" not in ProductionOrder.__table__.c
    assert "shift_definition_id" not in ProductionOrder.__table__.c
    assert "production_order_id" in ShiftReport.__table__.c
    assert "shift_definition_id" in ShiftReport.__table__.c
    assert "allocated_quantity" not in ProductionDemandItem.__table__.c
    assert "remaining_quantity" not in ProductionDemandItem.__table__.c


@pytest.mark.parametrize("field", ["commercial_order_id", "shift_definition_id", "planned_quantity", "organization_id"])
def test_t22_payload_forbids_server_fields(env, field):
    assert env.create(env.demand(), **{field: str(uuid4())}).status_code == 400


def test_t23_t27_snapshot_response_and_readonly(env):
    d = env.demand(); r = env.create(d); assert r.status_code == 201, r.text
    body = r.json()
    assert "commercial_order_id" not in body and "shift_definition_id" not in body
    item = env.db.get(ProductionDemandItem, __import__('uuid').UUID(d["items"][0]["id"]))
    item.target_spec_json = {"width": 99}; env.db.commit()
    r = env.client.get(f"{ROOT}/production-orders/{body['id']}")
    assert r.json()["target_spec_json"] == ITEM["target_spec_json"]
    assert env.client.patch(f"{ROOT}/production-orders/{body['id']}", json={"planned_quantity": "1"}).status_code == 400


def test_t28_t29_foreign_item(env):
    org = Organization(name="Other", code="alloc-other", timezone="UTC")
    env.db.add(org); env.db.flush()
    customer = Customer(organization_id=org.id, customer_code="OTHER", name="Other")
    env.db.add(customer); env.db.flush()
    d = ProductionDemand(organization_id=org.id, customer_id=customer.id, demand_number="OTHER", status="ready_for_planning")
    d.items = [ProductionDemandItem(line_no=1, **deepcopy(ITEM))]
    env.db.add(d); env.db.commit()
    assert env.create({"items": [{"id": str(d.items[0].id)}]}).status_code == 404


@pytest.mark.parametrize("missing", ["production:planning:allocate", "production:orders:create"])
def test_t30_t31_permissions(env, missing):
    d = env.demand(); env.ctx.auth_user.permissions = PERMISSIONS - {missing}
    assert env.create(d).status_code == 403


def test_duplicate_item_rejected(env):
    d = env.demand(); alloc = {"production_demand_item_id": d["items"][0]["id"], "allocated_quantity": "600"}
    assert env.create(d, allocations=[alloc, alloc]).status_code == 400
    assert env.db.scalar(select(func.count()).select_from(ProductionAllocation)) == 0


def test_allocated_demand_cannot_be_mutated_or_manually_transitioned(env):
    d = env.demand(); assert env.create(d).status_code == 201
    assert env.client.patch(f"{ROOT}/demands/{d['id']}", json={"items": [ITEM]}).status_code == 409
    assert env.client.post(f"{ROOT}/demands/{d['id']}/status", json={"status": "planned"}).status_code == 409
    assert env.client.post(f"{ROOT}/demands/{d['id']}/status", json={"status": "cancelled"}).status_code == 409


def test_invalid_center_and_dates_are_atomic(env):
    d = env.demand()
    assert env.create(d, work_center_id=str(uuid4())).status_code == 404
    assert env.create(d, planned_end_date="2020-01-01").status_code == 400
    assert env.db.scalar(select(func.count()).select_from(ProductionAllocation)) == 0


def test_queue_totals_remaining_filter(env):
    d = env.demand(); env.create(d)
    r = env.client.get(f"{ROOT}/planning/demands?has_remaining=true")
    assert r.status_code == 200, r.text
    assert Decimal(r.json()["items"][0]["total_remaining"]) == 400
    env.create(d, "400")
    assert env.client.get(f"{ROOT}/planning/demands?has_remaining=true").json()["total"] == 0


def test_t26_multiple_shift_reports_keep_order_link(env):
    from uuid import UUID
    order = env.create(env.demand()).json()
    shift = ShiftDefinition(organization_id=env.org.id, code="SD", name="Morning", start_time=time(7), end_time=time(15), duration_hours=8, crosses_midnight=False)
    env.db.add(shift); env.db.flush()
    for _ in range(2):
        env.db.add(ShiftReport(organization_id=env.org.id, work_center_id=env.center.id, shift_definition_id=shift.id, production_order_id=UUID(order["id"]), report_date=date.today(), summary="Report", created_by_user_id=env.user.id))
    env.db.commit()
    assert env.db.scalar(select(func.count()).select_from(ShiftReport).where(ShiftReport.production_order_id == UUID(order["id"]))) == 2


def test_policy_is_extensible_and_null_specs_are_strict():
    from app.production.domain.compatibility import DemandItemCompatibilityChecker, DemandItemSummary, IncompatibleDemandItemsError
    policy = DemandItemCompatibilityChecker()
    assert policy._specs_compatible(None, None)
    assert not policy._specs_compatible(None, {})
    assert policy._specs_compatible({"a": 1, "b": 2}, {"b": 2, "a": 1})
    class RelaxedPolicy(DemandItemCompatibilityChecker):
        def _specs_compatible(self, a, b):
            return True
    items = [DemandItemSummary("generic", "kg", {"a": 1}), DemandItemSummary("generic", "kg", {"a": 2})]
    with pytest.raises(IncompatibleDemandItemsError):
        policy.validate_compatibility(items)
    RelaxedPolicy().validate_compatibility(items)


def test_old_creation_endpoint_cannot_bypass_allocations(env):
    r = env.client.post(f"{ROOT}/production-orders", json={"work_center_id": str(env.center.id), "product_type": "film", "planned_quantity": "10", "unit": "kg", "planned_start_date": "2026-09-16", "planned_end_date": "2026-09-17"})
    assert r.status_code == 422
    assert env.db.scalar(select(func.count()).select_from(ProductionOrder)) == 0


def test_old_creation_endpoint_accepts_allocation_payload(env):
    d = env.demand()
    r = env.client.post(f"{ROOT}/production-orders", json={"allocations": [{"production_demand_item_id": d["items"][0]["id"], "allocated_quantity": "100.001"}], "work_center_id": str(env.center.id), "planned_start_date": "2026-09-16", "planned_end_date": "2026-09-17"})
    assert r.status_code == 201, r.text
    assert Decimal(r.json()["planned_quantity"]) == Decimal("100.001")


def test_allocations_block_work_center_cascade(env):
    env.create(env.demand())
    r = env.client.delete(f"{ROOT}/work-centers/{env.center.id}")
    assert r.status_code == 409
    assert env.db.scalar(select(func.count()).select_from(ProductionAllocation)) == 1
