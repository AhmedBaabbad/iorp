"""PROD-QUALITY-FIX-001 item 1: allocations follow one open/locked rule (add, change and release alike).

Open: draft, released, in progress, on hold. Locked: completed, closed, cancelled. An order on the floor keeps its lines
(runs, waste, results and quality may point at them): quantities are adjusted, a new specification becomes a new line.
"""
from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select

from app.core.interfaces.activity_log import get_registered_activity_logger  # noqa: F401  (registers the logger)
from app.production.domain.order_lifecycle import ALLOCATION_LOCKED, ALLOCATION_OPEN, OPEN
from app.production.infrastructure.execution_models import ProductionRun
from app.production.infrastructure.models import ProductionAllocation, ProductionOrder, ProductionOrderItem, WasteRecord
from tests.test_production_allocation_lifecycle import other_org_demand
from tests.test_production_order_lines import ROOT, env, items, spec  # noqa: F401  (env is a fixture)


def set_status(env, order_id, status):
    row = env.db.get(ProductionOrder, UUID(order_id)); row.status = status; env.db.commit()


def add(env, order_id, item_id, quantity):
    return env.client.post(f"{ROOT}/orders/{order_id}/allocations", json=env.pairs((item_id, quantity))[0])


def active(order):
    return [a for a in order["allocations"] if a["status"] == "active"]


def test_state_sets_are_defined_once_next_to_the_state_machine():
    assert ALLOCATION_OPEN == OPEN
    assert {s.value for s in ALLOCATION_OPEN} == {"draft", "released", "in_progress", "on_hold"}
    assert {s.value for s in ALLOCATION_LOCKED} == {"completed", "closed", "cancelled"}


@pytest.mark.parametrize("status", ["draft", "released", "in_progress", "on_hold"])
def test_allocate_change_and_release_in_every_open_state(env, status):
    first, second = env.demand(spec(10)), env.demand(spec(10))
    po = env.order((items(first)[0], "600"))
    set_status(env, po["id"], status)
    r = add(env, po["id"], items(second)[0], "200")
    assert r.status_code == 200, r.text
    order = r.json()
    # Planned quantity follows the allocations: 600 + 200 = 800.
    assert Decimal(order["planned_quantity"]) == 800 and Decimal(order["active_allocated_quantity"]) == 800
    added = next(a for a in order["allocations"] if a["production_demand_item_id"] == items(second)[0])
    assert added["order_status_at_allocation"] == status
    assert added["added_after_start"] is (status in ("in_progress", "on_hold"))
    assert order["allocation_open"] is True
    changed = env.client.patch(f"{ROOT}/allocations/{added['id']}", json={"allocated_quantity": "150"})
    assert changed.status_code == 200, changed.text
    assert Decimal(changed.json()["planned_quantity"]) == 750
    released = env.client.post(f"{ROOT}/allocations/{added['id']}/release", json={"reason": "customer reduced"})
    assert released.status_code == 200, released.text
    assert Decimal(env.client.get(f"{ROOT}/orders/{po['id']}").json()["planned_quantity"]) == 600


@pytest.mark.parametrize("status", ["completed", "closed", "cancelled"])
def test_allocate_change_and_release_are_refused_once_locked(env, status):
    first, second = env.demand(spec(10)), env.demand(spec(10))
    po = env.order((items(first)[0], "300"), (items(second)[0], "300"))
    set_status(env, po["id"], status)
    third = env.demand(spec(10))
    allocation = po["allocations"][0]["id"]
    responses = [add(env, po["id"], items(third)[0], "10"),
                 env.client.patch(f"{ROOT}/allocations/{allocation}", json={"allocated_quantity": "50"}),
                 env.client.post(f"{ROOT}/allocations/{allocation}/release", json={"reason": "late"})]
    for r in responses:
        assert r.status_code == 409 and r.json()["detail"]["code"] == "ORDER_ALLOCATION_LOCKED", r.text
        assert r.json()["detail"]["order_status"] == status
    assert env.client.get(f"{ROOT}/orders/{po['id']}").json()["allocation_open"] is False


def test_release_after_execution_started_is_allowed(env):
    # Recorded execution no longer freezes allocations; only the order's state decides.
    first, second = env.demand(spec(10)), env.demand(spec(12))
    po = env.order((items(first)[0], "100"), (items(second)[0], "100"))
    set_status(env, po["id"], "in_progress")
    order = env.db.get(ProductionOrder, UUID(po["id"]))
    env.db.add(ProductionRun(organization_id=env.org.id, production_order_id=order.id, work_center_id=order.work_center_id,
                             run_date=date.today(), status="in_progress", created_by_user_id=env.ctx.tenant.user_id))
    env.db.commit()
    target = next(a for a in po["allocations"] if a["production_demand_item_id"] == items(second)[0])
    r = env.client.post(f"{ROOT}/allocations/{target['id']}/release", json={"reason": "moved"})
    assert r.status_code == 200, r.text
    assert env.client.get(f"{ROOT}/demands/{second['id']}").json()["status"] == "ready_for_planning"


def test_started_order_keeps_its_lines_and_numbers(env):
    first, same, other = env.demand(spec(10)), env.demand(spec(10)), env.demand(spec(5))
    po = env.order((items(first)[0], "600"))
    line = po["lines"][0]
    set_status(env, po["id"], "in_progress")
    # Waste already points at line 1: the line must survive every allocation change.
    order = env.db.get(ProductionOrder, UUID(po["id"]))
    env.db.add(WasteRecord(organization_id=env.org.id, production_order_id=order.id, production_order_item_id=UUID(line["id"]),
                           work_center_id=order.work_center_id, waste_date=date.today(), quantity_wasted=Decimal("5"), unit="kg",
                           waste_category="process", created_by_user_id=env.ctx.tenant.user_id))
    env.db.commit()
    joined = add(env, po["id"], items(same)[0], "200").json()
    assert [(l["id"], l["line_no"], Decimal(l["planned_quantity"])) for l in joined["lines"]] == [(line["id"], 1, Decimal(800))]
    # A narrower width would sort first in a draft; on the floor it is appended as line 2 instead.
    grown = add(env, po["id"], items(other)[0], "50").json()
    assert [(l["line_no"], l["target_spec_json"], Decimal(l["planned_quantity"])) for l in grown["lines"]] == [
        (1, spec(10), Decimal(800)), (2, spec(5), Decimal(50))]
    new = next(a for a in active(grown) if a["production_demand_item_id"] == items(other)[0])
    assert new["order_line_no"] == 2
    released = env.client.post(f"{ROOT}/allocations/{new['id']}/release", json={"reason": "cancelled by customer"})
    assert released.status_code == 200, released.text
    after = env.client.get(f"{ROOT}/orders/{po['id']}").json()
    # The emptied line stays (never deleted, never below zero); the order total is 800 again.
    assert [(l["line_no"], Decimal(l["planned_quantity"])) for l in after["lines"]] == [(1, Decimal(800)), (2, Decimal(0))]
    assert Decimal(after["planned_quantity"]) == 800
    assert env.db.scalar(select(ProductionOrderItem.id).where(ProductionOrderItem.id == UUID(line["id"]))) is not None


def test_draft_orders_still_rearrange(env):
    wide, narrow = env.demand(spec(20)), env.demand(spec(10))
    po = env.order((items(wide)[0], "100"))
    order = add(env, po["id"], items(narrow)[0], "50").json()
    assert [l["target_spec_json"] for l in order["lines"]] == [spec(10), spec(20)]


def test_no_over_allocation_and_compatibility_still_apply(env):
    first, second = env.demand(spec(10), quantity="500"), env.demand(spec(10), quantity="500")
    po = env.order((items(first)[0], "400"))
    set_status(env, po["id"], "in_progress")
    r = add(env, po["id"], items(second)[0], "501")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "ALLOCATION_QUANTITY_CONFLICT"
    over = env.client.patch(f"{ROOT}/allocations/{po['allocations'][0]['id']}", json={"allocated_quantity": "501"})
    assert over.status_code == 409 and over.json()["detail"]["code"] == "ALLOCATION_QUANTITY_CONFLICT"
    other_unit = env.demand(spec(10), unit="m")
    r = add(env, po["id"], items(other_unit)[0], "10")
    assert r.status_code == 400 and r.json()["detail"]["code"] == "INCOMPATIBLE_DEMAND_ITEMS"
    again = add(env, po["id"], items(first)[0], "10")
    assert again.status_code == 409 and again.json()["detail"]["code"] == "ALLOCATION_ALREADY_IN_ORDER"


def test_cross_tenant_allocation_is_rejected(env):
    other = other_org_demand(env.db)
    mine = env.demand(spec(10))
    po = env.order((items(mine)[0], "100"))
    set_status(env, po["id"], "in_progress")
    assert add(env, po["id"], str(other.demand.items[0].id), "10").status_code == 404
    assert add(env, str(other.order.id), items(mine)[0], "10").status_code == 404
    assert env.client.post(f"{ROOT}/allocations/{other.allocation.id}/release", json={"reason": "x"}).status_code == 404
    assert env.client.get(f"{ROOT}/planning/eligible-orders", params={"demand_item_id": str(other.demand.items[0].id)}).status_code == 404


def test_eligible_orders_lists_open_compatible_orders_only(env):
    source = env.demand(spec(10))
    candidate = env.demand(spec(10))
    orders = {}
    for status in ("draft", "in_progress", "on_hold", "completed", "cancelled"):
        d = env.demand(spec(10))
        orders[status] = env.order((items(d)[0], "10"))
        set_status(env, orders[status]["id"], status)
    meters = env.demand(spec(10), unit="m")
    env.order((items(meters)[0], "10"))
    containing = env.order((items(source)[0], "10"))
    r = env.client.get(f"{ROOT}/planning/eligible-orders", params={"demand_item_id": items(candidate)[0]})
    assert r.status_code == 200, r.text
    listed = {o["id"]: o["status"] for o in r.json()}
    assert listed == {orders["draft"]["id"]: "draft", orders["in_progress"]["id"]: "in_progress", orders["on_hold"]["id"]: "on_hold",
                      containing["id"]: "draft"}
    # An order that already has this demand item is not offered again.
    mine = env.client.get(f"{ROOT}/planning/eligible-orders", params={"demand_item_id": items(source)[0]}).json()
    assert containing["id"] not in {o["id"] for o in mine}


def test_every_allocation_change_is_audited_with_the_order_status(env, monkeypatch):
    from app.production.application import planning_order_service, allocation_service
    logged = []
    class Logger:
        def log_activity(self, db, org, action, entity_type, entity_id, name, actor_id=None, details=None):
            logged.append((action, details or {}))
    for module in (planning_order_service, allocation_service):
        monkeypatch.setattr(module, "get_registered_activity_logger", lambda: Logger())
    first, second = env.demand(spec(10)), env.demand(spec(10))
    po = env.order((items(first)[0], "100"))
    set_status(env, po["id"], "on_hold")
    order = add(env, po["id"], items(second)[0], "20").json()
    new = next(a for a in active(order) if a["production_demand_item_id"] == items(second)[0])
    env.client.patch(f"{ROOT}/allocations/{new['id']}", json={"allocated_quantity": "30"})
    env.client.post(f"{ROOT}/allocations/{new['id']}/release", json={"reason": "r"})
    actions = {action: details for action, details in logged}
    assert set(actions) >= {"production_order.allocation_added", "production_order.allocation_changed", "production_allocation.released"}
    assert all(details["order_status"] == "on_hold" for details in actions.values())


def test_the_order_status_is_stored_on_the_allocation(env):
    first, second = env.demand(spec(10)), env.demand(spec(10))
    po = env.order((items(first)[0], "100"))
    set_status(env, po["id"], "in_progress")
    add(env, po["id"], items(second)[0], "20")
    rows = {a.production_demand_item_id: a.order_status_at_allocation for a in env.db.scalars(select(ProductionAllocation))}
    assert rows[UUID(items(first)[0])] == "draft" and rows[UUID(items(second)[0])] == "in_progress"
