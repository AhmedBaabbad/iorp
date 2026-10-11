"""PROD-WASTE-001: operational waste records, tied to a production order and optionally a run."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.commercial.infrastructure.models import Customer
from app.core.tenancy import TenantContext
from app.dependencies import get_current_user
from app.main import app
from app.production.infrastructure.execution_models import ProductionRun
from app.production.infrastructure.models import ProductionOrder, ProductionResultEntry, WasteRecord, WasteRecordCategory, WorkCenter
from tests.test_production_allocation_lifecycle import other_org_demand

ROOT = "/api/v1/production"
WASTE = f"{ROOT}/waste-records"
PERMISSIONS = frozenset(
    ["production:production_orders:read", "production:production_orders:update", "production:production_orders:manage_items", "production:planning:read", "production:planning:allocate",
     "production:production_orders:create", "production:waste_records:read", "production:waste_records:create", "production:waste_records:update", "production:waste_records:delete", "production:results:read", "production:results:create", "production:results:update", "production:results:delete"]
    + [f"production:production_orders:{a}" for a in ("release", "start", "hold", "complete", "close", "cancel")]
    + [f"production:demands:{a}" for a in ("read", "create", "update", "release", "cancel")])
CATEGORIES = ["startup_setup", "changeover", "process", "material_defect", "machine_fault", "handling_damage", "contamination", "other"]


@pytest.fixture
def env(client, db, test_org, test_user):
    customer = Customer(organization_id=test_org.id, customer_code="C-WASTE", name="Waste Customer")
    center = WorkCenter(organization_id=test_org.id, code="WC-WASTE", name="Extruder 1")
    other_center = WorkCenter(organization_id=test_org.id, code="WC-WASTE2", name="Extruder 2")
    db.add_all([customer, center, other_center]); db.commit()
    ctx = SimpleNamespace(user=SimpleNamespace(is_organization_root=False), auth_user=SimpleNamespace(permissions=set(PERMISSIONS)),
                          tenant=TenantContext(test_user.id, test_org.id, permissions=PERMISSIONS))
    app.dependency_overrides[get_current_user] = lambda: ctx

    def transition(order_id, action, reason="because", **extra):
        return client.post(f"{ROOT}/production-orders/{order_id}/transitions", json={"action": action, "reason": reason, **extra})

    def order(*specs, to="in_progress"):
        items = [dict(product_type="film", unit="kg", required_quantity="1000", target_spec_json=s) for s in (specs or ({"width_mm": 10},))]
        demand_id = client.post(f"{ROOT}/demands", json={"customer_id": str(customer.id), "items": items}).json()["id"]
        client.post(f"{ROOT}/demands/{demand_id}/status", json={"status": "ready_for_planning"})
        demand = client.get(f"{ROOT}/demands/{demand_id}").json()
        r = client.post(f"{ROOT}/planning/create-production-order", json=dict(
            allocations=[{"production_demand_item_id": i["id"], "allocated_quantity": "400"} for i in demand["items"]],
            work_center_id=str(center.id), planned_start_date="2026-10-01", planned_end_date="2026-10-03"))
        assert r.status_code == 201, r.text
        po = r.json()
        path = {"draft": [], "released": ["release"], "in_progress": ["release", "start"], "on_hold": ["release", "start", "hold"],
                "completed": ["release", "start", "complete"], "closed": ["release", "start", "complete", "close"], "cancelled": ["cancel"]}[to]
        for action in path:
            extra = {"zero_output": True} if action == "close" else {}
            assert transition(po["id"], action, **extra).status_code == 200
        return client.get(f"{ROOT}/production-orders/{po['id']}").json()

    def run(po, status="in_progress", work_center=None):
        row = ProductionRun(organization_id=test_org.id, production_order_id=UUID(po["id"]), work_center_id=(work_center or other_center).id,
                            run_date=date(2026, 10, 1), status=status, created_by_user_id=test_user.id)
        db.add(row); db.commit()
        return row

    def add(po, category="process", quantity="12.5", **extra):
        return client.post(WASTE, json={"production_order_id": po["id"], "waste_date": "2026-10-01", "quantity_wasted": quantity, "unit": "kg",
                                        "categories": [{"category": category}], **extra})

    def added(po, *args, **kwargs):
        r = add(po, *args, **kwargs)
        assert r.status_code == 201, r.text
        return r.json()

    def rows():
        db.expire_all()
        return list(db.scalars(select(WasteRecord).order_by(WasteRecord.created_at)))

    return SimpleNamespace(db=db, client=client, org=test_org, user=test_user, ctx=ctx, center=center, other_center=other_center,
                           order=order, run=run, add=add, added=added, rows=rows, transition=transition)


def code(r):
    return r.json()["detail"]["code"]


# ---- the order decides -------------------------------------------------------------------------

@pytest.mark.parametrize("status", ["in_progress", "on_hold", "completed"])
def test_waste_recorded_while_the_order_runs_or_as_a_late_entry(env, status):
    po = env.order(to=status)
    record = env.added(po, "startup_setup", "30.125", reason_code="WARM-UP", notes="first metres")
    (row,) = env.rows()
    assert (row.production_order_id, row.work_center_id, row.quantity_wasted, row.created_by_user_id) == (
        UUID(po["id"]), env.center.id, Decimal("30.125"), env.user.id)
    # One category alone takes the whole quantity.
    assert [(c.category, c.quantity) for c in row.categories] == [("startup_setup", Decimal("30.125"))]
    assert record["labels"]["order_number"] == po["production_order_number"] and record["labels"]["actions"] == ["edit", "delete"]


@pytest.mark.parametrize("status,expected", [("draft", "WASTE_NOT_AVAILABLE"), ("released", "WASTE_NOT_AVAILABLE"),
                                             ("cancelled", "WASTE_NOT_AVAILABLE"), ("closed", "WASTE_LOCKED")])
def test_waste_rejected_before_production_and_after_close(env, status, expected):
    po = env.order(to=status)
    r = env.add(po)
    assert r.status_code == 409 and code(r) == expected and r.json()["detail"]["order_status"] == status
    assert env.rows() == []


def test_closing_locks_existing_records(env):
    po = env.order(to="completed")
    record = env.added(po)
    assert env.transition(po["id"], "close", zero_output=True).status_code == 200
    for r in (env.client.patch(f"{WASTE}/{record['id']}", json={"quantity_wasted": "1"}), env.client.delete(f"{WASTE}/{record['id']}")):
        assert r.status_code == 409 and code(r) == "WASTE_LOCKED"
    assert env.rows()[0].quantity_wasted == Decimal("12.5")
    assert env.client.get(f"{WASTE}/{record['id']}").json()["labels"]["actions"] == []


def test_order_is_required_and_cannot_be_changed(env):
    po = env.order()
    r = env.client.post(WASTE, json={"waste_date": "2026-10-01", "quantity_wasted": "1", "unit": "kg", "categories": [{"category": "other"}]})
    assert r.status_code == 422
    record = env.added(po)
    other = env.order()
    assert env.client.patch(f"{WASTE}/{record['id']}", json={"production_order_id": other["id"]}).status_code == 422
    assert str(env.rows()[0].production_order_id) == po["id"]


# ---- run, work center and item ----------------------------------------------------------------

def test_run_is_optional_and_gives_the_work_center(env):
    po = env.order()
    run = env.run(po)
    record = env.added(po, production_run_id=str(run.id))
    row = env.rows()[0]
    assert (row.production_run_id, row.work_center_id) == (run.id, env.other_center.id)
    assert record["labels"]["work_center_name"] == "Extruder 2" and record["labels"]["run_date"] == "2026-10-01"
    r = env.add(po, production_run_id=str(run.id), work_center_id=str(env.center.id))
    assert r.status_code == 422 and code(r) == "WORK_CENTER_MISMATCH"
    # Without a run: the given work center, else the order's.
    env.added(po, work_center_id=str(env.other_center.id))
    env.added(po)
    assert [r.work_center_id for r in env.rows()] == [env.other_center.id, env.other_center.id, env.center.id]


def test_run_must_belong_to_the_order_and_not_be_cancelled(env):
    po, other = env.order(), env.order()
    r = env.add(po, production_run_id=str(env.run(other).id))
    assert r.status_code == 422 and code(r) == "RUN_NOT_IN_ORDER"
    r = env.add(po, production_run_id=str(env.run(po, status="cancelled").id))
    assert r.status_code == 422 and code(r) == "RUN_CANCELLED"
    r = env.add(po, production_run_id=str(uuid4()))
    assert code(r) == "RUN_NOT_IN_ORDER"
    assert env.rows() == []


def test_item_must_belong_to_the_order(env):
    po, other = env.order(), env.order()
    env.added(po, production_order_item_id=po["lines"][0]["id"])
    r = env.add(po, production_order_item_id=other["lines"][0]["id"])
    assert r.status_code == 422 and code(r) == "ORDER_ITEM_NOT_IN_ORDER"


# ---- categories and quantities ----------------------------------------------------------------

def test_every_generic_category_is_accepted_and_old_ones_are_not(env):
    po = env.order()
    for category in CATEGORIES:
        env.added(po, category, "1")
    assert {c.category for r in env.rows() for c in r.categories} == set(CATEGORIES)
    # Plastics-specific values are gone, and finished product is scrap in the final result, not waste.
    for old in ("trim_loss", "end_of_roll_loss", "rejected_output"):
        assert env.add(po, old).status_code == 422


@pytest.mark.parametrize("quantity", ["0", "-5", "1.0001"])
def test_quantity_must_be_positive_with_three_decimals(env, quantity):
    po = env.order()
    r = env.add(po, quantity=quantity)
    assert r.status_code == 422 and any(e["loc"][-1] == "quantity_wasted" for e in r.json()["detail"])


def test_edit_and_delete_while_open(env):
    po = env.order()
    run = env.run(po)
    record = env.added(po)
    r = env.client.patch(f"{WASTE}/{record['id']}", json={"quantity_wasted": "7.5", "categories": [{"category": "machine_fault"}], "production_run_id": str(run.id)})
    assert r.status_code == 200, r.text
    row = env.rows()[0]
    assert (row.quantity_wasted, row.work_center_id, row.updated_by_user_id) == (Decimal("7.5"), env.other_center.id, env.user.id)
    assert [(c.category, c.quantity) for c in row.categories] == [("machine_fault", Decimal("7.5"))]
    assert env.client.patch(f"{WASTE}/{record['id']}", json={"quantity_wasted": None}).status_code == 422
    assert env.client.delete(f"{WASTE}/{record['id']}").status_code == 204
    assert env.rows() == []


# ---- summary: apart from the final result ------------------------------------------------------

def test_summary_per_unit_and_category_is_separate_from_the_result(env):
    po = env.order(to="completed")
    env.added(po, "process", "10")
    env.added(po, "process", "5.5")
    env.added(po, "startup_setup", "3")
    env.client.post(WASTE, json={"production_order_id": po["id"], "waste_date": "2026-10-01", "quantity_wasted": "2", "unit": "m", "categories": [{"category": "other"}]})
    summary = env.client.get(f"{WASTE}/summary", params={"production_order_id": po["id"]}).json()
    assert [(t["unit"], Decimal(t["quantity"]), t["count"]) for t in summary["totals"]] == [("kg", Decimal("18.5"), 3), ("m", Decimal("2"), 1)]
    assert [(c["category"], c["unit"], Decimal(c["quantity"])) for c in summary["by_category"]] == [
        ("process", "kg", Decimal("15.5")), ("startup_setup", "kg", Decimal("3")), ("other", "m", Decimal("2"))]
    assert summary["actions"] == ["create"] and summary["available"] and not summary["locked"]
    # Waste never enters the order's final result.
    result = env.client.get(f"{ROOT}/production-orders/{po['id']}/result").json()
    assert all(Decimal(t["scrap_total"]) == 0 and Decimal(t["total_output"]) == 0 for t in result["totals"])
    assert env.db.scalar(select(ProductionResultEntry.id)) is None


# ---- lists, security ---------------------------------------------------------------------------

def test_list_filters(env):
    po, other = env.order(), env.order()
    run = env.run(po)
    env.added(po, "process", production_run_id=str(run.id))
    env.client.post(WASTE, json={"production_order_id": po["id"], "waste_date": "2026-09-20", "quantity_wasted": "1", "unit": "kg", "categories": [{"category": "other"}]})
    env.added(other, "changeover")
    ids = lambda **q: {c["category"] for r in env.client.get(WASTE, params=q).json()["items"] for c in r["categories"]}  # noqa: E731
    assert ids(production_order_id=po["id"]) == {"process", "other"}
    assert ids(waste_category="changeover") == {"changeover"}
    assert ids(production_run_id=str(run.id)) == {"process"}
    assert ids(date_from="2026-10-01") == {"process", "changeover"}
    assert ids(date_to="2026-09-30") == {"other"}
    assert ids(work_center_id=str(env.other_center.id)) == {"process"}


def test_other_organizations_are_invisible_and_body_org_is_refused(env):
    foreign = other_org_demand(env.db)
    foreign.order.status = "in_progress"; env.db.commit()
    r = env.client.post(WASTE, json={"production_order_id": str(foreign.order.id), "waste_date": "2026-10-01", "quantity_wasted": "1", "unit": "kg", "categories": [{"category": "other"}]})
    assert r.status_code == 404 and code(r) == "PRODUCTION_ORDER_NOT_FOUND"
    po = env.order()
    assert env.add(po, organization_id=str(foreign.org.id)).status_code == 422
    env.db.add(WasteRecord(organization_id=foreign.org.id, production_order_id=foreign.order.id, work_center_id=foreign.order.work_center_id,
                           waste_date=date(2026, 10, 1), quantity_wasted=Decimal("9"), unit="kg", created_by_user_id=env.user.id,
                           categories=[WasteRecordCategory(organization_id=foreign.org.id, category="other", quantity=Decimal("9"))]))
    env.db.commit()
    foreign_id = env.db.scalar(select(WasteRecord.id).where(WasteRecord.organization_id == foreign.org.id))
    assert env.client.get(WASTE).json()["items"] == []
    assert env.client.get(f"{WASTE}/{foreign_id}").status_code == 404
    assert env.client.delete(f"{WASTE}/{foreign_id}").status_code == 404
    assert env.client.get(f"{WASTE}/summary", params={"production_order_id": str(foreign.order.id)}).status_code == 404


def test_permissions(env):
    po = env.order()
    record = env.added(po)
    env.ctx.auth_user.permissions = set(PERMISSIONS) - {"production:waste_records:create", "production:waste_records:update", "production:waste_records:delete"}
    assert env.add(po).status_code == 403
    assert env.client.patch(f"{WASTE}/{record['id']}", json={"quantity_wasted": "1"}).status_code == 403
    assert env.client.delete(f"{WASTE}/{record['id']}").status_code == 403
    assert env.client.get(f"{WASTE}/{record['id']}").json()["labels"]["actions"] == []
    assert env.client.get(f"{WASTE}/summary", params={"production_order_id": po["id"]}).json()["actions"] == []
    env.ctx.auth_user.permissions = set(PERMISSIONS) - {"production:waste_records:read"}
    assert env.client.get(WASTE).status_code == 403


def test_work_center_delete_refused_while_waste_exists(env):
    # An order without customer allocations, so only the waste can block the delete.
    order = ProductionOrder(organization_id=env.org.id, production_order_number="PO-BARE", work_center_id=env.other_center.id, product_type="film",
                            planned_quantity=Decimal("100"), unit="kg", status="in_progress", planned_start_date=date(2026, 10, 1),
                            planned_end_date=date(2026, 10, 3), created_by_user_id=env.user.id)
    env.db.add(order); env.db.commit()
    env.added({"id": str(order.id)})
    env.ctx.auth_user.permissions = set(PERMISSIONS) | {"production:work_centers:delete"}
    r = env.client.delete(f"{ROOT}/work-centers/{env.other_center.id}")
    assert r.status_code == 409 and "waste" in r.json()["detail"]
    assert len(env.rows()) == 1 and env.db.get(ProductionOrder, order.id) is not None
