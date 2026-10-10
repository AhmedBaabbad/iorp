"""Planning orders with differing specifications: ordered lines and draft editing."""
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID
import pytest
from sqlalchemy import func, select
from app.main import app
from app.dependencies import get_current_user
from app.core.tenancy import TenantContext
from app.commercial.infrastructure.models import Customer
from app.production.domain.arrangement import arrange, sort_key
from app.production.infrastructure.models import ProductionAllocation, ProductionOrder, ProductionOrderItem, WorkCenter
from tests.test_production_allocation_lifecycle import other_org_demand

ROOT = "/api/v1/production"
PERMISSIONS = frozenset([
    "production:planning:read", "production:planning:allocate", "production:planning:release_allocation",
    "production:production_orders:create", "production:production_orders:cancel", "production:production_orders:read", "production:production_orders:update", "production:production_orders:manage_items",
] + [f"production:demands:{a}" for a in ("read", "create", "update", "release", "cancel")])


def spec(width=None, color=None, thickness=None, weight=None):
    values = dict(width_mm=width, color=color, thickness_mm=thickness, roll_weight_kg=weight)
    return {k: v for k, v in values.items() if v is not None}


@pytest.fixture
def env(client, db, test_org, test_user):
    customer = Customer(organization_id=test_org.id, customer_code="C-LINES", name="Lines Customer")
    center = WorkCenter(organization_id=test_org.id, code="WC-LINES", name="Line")
    db.add_all([customer, center]); db.commit()
    ctx = SimpleNamespace(user=SimpleNamespace(is_organization_root=False), auth_user=SimpleNamespace(permissions=PERMISSIONS),
                          tenant=TenantContext(test_user.id, test_org.id, permissions=PERMISSIONS))
    app.dependency_overrides[get_current_user] = lambda: ctx

    def demand(*specs, quantity="1000", product="film", unit="kg"):
        items = [dict(product_type=product, unit=unit, required_quantity=quantity, target_spec_json=s) for s in specs]
        r = client.post(f"{ROOT}/demands", json={"customer_id": str(customer.id), "items": items})
        assert r.status_code == 201, r.text
        assert client.post(f"{ROOT}/demands/{r.json()['id']}/status", json={"status": "ready_for_planning"}).status_code == 200
        return client.get(f"{ROOT}/demands/{r.json()['id']}").json()

    def pairs(*entries):
        return [{"production_demand_item_id": i, "allocated_quantity": q} for i, q in entries]

    def create(*entries):
        return client.post(f"{ROOT}/planning/create-production-order", json=dict(allocations=pairs(*entries), work_center_id=str(center.id),
                           planned_start_date="2026-10-01", planned_end_date="2026-10-02"))

    def order(*entries):
        r = create(*entries)
        assert r.status_code == 201, r.text
        return r.json()

    return SimpleNamespace(db=db, client=client, org=test_org, ctx=ctx, demand=demand, pairs=pairs, create=create, order=order)


def items(d):
    return [i["id"] for i in d["items"]]


def line_specs(order):
    return [line["target_spec_json"] for line in order["lines"]]


# ---- Arrangement rule -------------------------------------------------------------------

def test_sort_width_then_color_then_thickness_then_weight():
    specs = [spec(20, "red", 30, 5), spec(10, "red", 30, 5), spec(10, "blue", 40, 5), spec(10, "blue", 30, 9), spec(10, "blue", 30, 5)]
    ordered = [line.target_spec_json for line in arrange([SimpleNamespace(s=s, q=Decimal(1), u="kg") for s in specs], spec=lambda e: e.s, quantity=lambda e: e.q, unit=lambda e: e.u)]
    assert ordered == [spec(10, "blue", 30, 5), spec(10, "blue", 30, 9), spec(10, "blue", 40, 5), spec(10, "red", 30, 5), spec(20, "red", 30, 5)]


def test_numbers_sort_numerically_text_alphabetically_and_missing_last():
    assert sort_key(spec(9)) < sort_key(spec(10)) < sort_key(spec("100.5")) < sort_key({})
    assert sort_key(spec(10, "Blue")) < sort_key(spec(10, "green")) < sort_key(spec(10))
    assert sort_key({"width": 5}) < sort_key({"width_mm": 7})  # alternative key names count too


def test_identical_specifications_share_one_line():
    entries = [SimpleNamespace(s=spec(10, "red"), q=Decimal("1.5")), SimpleNamespace(s={"color": "red", "width_mm": 10}, q=Decimal("2.25"))]
    (line,) = arrange(entries, spec=lambda e: e.s, quantity=lambda e: e.q, unit=lambda e: "kg")
    assert line.quantity == Decimal("3.75") and line.line_no == 1 and len(line.allocations) == 2


# ---- Creation --------------------------------------------------------------------------

def test_order_accepts_differing_specs_as_ordered_lines(env):
    a = env.demand(spec(20, "white", 25, 50), spec(10, "blue", 30, 40))
    b = env.demand(spec(10, "blue", 30, 40), spec(10, "black", 30, 40))
    po = env.order((items(a)[0], "300"), (items(a)[1], "200"), (items(b)[0], "150"), (items(b)[1], "100.5"))
    assert line_specs(po) == [spec(10, "black", 30, 40), spec(10, "blue", 30, 40), spec(20, "white", 25, 50)]
    assert [Decimal(line["planned_quantity"]) for line in po["lines"]] == [Decimal("100.5"), 350, 300]
    assert Decimal(po["planned_quantity"]) == Decimal("750.5")
    blue = po["lines"][1]
    assert len(blue["allocation_ids"]) == 2  # two customers' demands merged into one production line
    assert {a["order_line_no"] for a in po["allocations"] if a["id"] in blue["allocation_ids"]} == {2}
    # Header shows only what every line agrees on.
    assert po["target_spec_json"] is None
    assert po["editable"] is True


def test_header_keeps_the_shared_part_of_the_specification(env):
    d = env.demand(spec(10, "blue", 30), spec(12, "blue", 30))
    po = env.order((items(d)[0], "10"), (items(d)[1], "10"))
    assert po["target_spec_json"] == {"color": "blue", "thickness_mm": 30}


def test_product_type_and_unit_must_still_match(env):
    d = env.demand(spec(10))
    other_unit = env.demand(spec(10), unit="m")
    other_product = env.demand(spec(10), product="bag")
    for other in (other_unit, other_product):
        r = env.create((items(d)[0], "10"), (items(other)[0], "10"))
        assert r.status_code == 400 and r.json()["detail"]["code"] == "INCOMPATIBLE_DEMAND_ITEMS"
    assert env.db.scalar(select(func.count()).select_from(ProductionOrder)) == 0


def test_preview_arranges_without_writing(env):
    a, b = env.demand(spec(20, "red")), env.demand(spec(10, "red"))
    r = env.client.post(f"{ROOT}/planning/preview-production-order", json={"allocations": env.pairs((items(a)[0], "400"), (items(b)[0], "250"))})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [line["target_spec_json"] for line in body["lines"]] == [spec(10, "red"), spec(20, "red")]
    assert body["lines"][0]["allocations"][0]["customer_name"] == "Lines Customer"
    assert Decimal(body["total_quantity"]) == 650
    assert env.db.scalar(select(func.count()).select_from(ProductionOrder)) == 0
    assert env.db.scalar(select(func.count()).select_from(ProductionAllocation)) == 0
    over = env.client.post(f"{ROOT}/planning/preview-production-order", json={"allocations": env.pairs((items(a)[0], "1000.001"))})
    assert over.status_code == 409 and over.json()["detail"]["code"] == "ALLOCATION_QUANTITY_CONFLICT"


# ---- Editing a draft order -------------------------------------------------------------

def test_add_allocation_places_it_on_the_right_line(env):
    d = env.demand(spec(20, "red"), spec(15, "red"), spec(20, "red"))
    po = env.order((items(d)[0], "100"))
    r = env.client.post(f"{ROOT}/orders/{po['id']}/allocations", json=env.pairs((items(d)[1], "50"))[0])
    assert r.status_code == 200, r.text
    assert line_specs(r.json()) == [spec(15, "red"), spec(20, "red")]
    same = env.demand(spec(20, "red"))
    r = env.client.post(f"{ROOT}/orders/{po['id']}/allocations", json=env.pairs((items(same)[0], "25"))[0])
    assert [Decimal(line["planned_quantity"]) for line in r.json()["lines"]] == [50, 125]
    assert Decimal(r.json()["planned_quantity"]) == 175
    assert env.client.get(f"{ROOT}/demands/{same['id']}").json()["status"] == "partially_planned"


def test_add_rejects_duplicates_other_products_and_over_allocation(env):
    d = env.demand(spec(10))
    po = env.order((items(d)[0], "100"))
    r = env.client.post(f"{ROOT}/orders/{po['id']}/allocations", json=env.pairs((items(d)[0], "10"))[0])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "ALLOCATION_ALREADY_IN_ORDER"
    bag = env.demand(spec(10), product="bag")
    r = env.client.post(f"{ROOT}/orders/{po['id']}/allocations", json=env.pairs((items(bag)[0], "10"))[0])
    assert r.status_code == 400 and r.json()["detail"]["reason"] == "DIFFERENT_PRODUCT_TYPE"
    fresh = env.demand(spec(10))
    r = env.client.post(f"{ROOT}/orders/{po['id']}/allocations", json=env.pairs((items(fresh)[0], "1000.001"))[0])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "ALLOCATION_QUANTITY_CONFLICT"


def test_change_quantity_updates_lines_and_respects_remaining(env):
    d = env.demand(spec(10), spec(12))
    other = env.order((items(d)[0], "600"))  # another order already holds 600 of line 1
    po = env.order((items(d)[0], "300"), (items(d)[1], "100"))
    target = next(a for a in po["allocations"] if a["production_demand_item_id"] == items(d)[0])
    r = env.client.patch(f"{ROOT}/allocations/{target['id']}", json={"allocated_quantity": "400"})
    assert r.status_code == 200, r.text
    assert [Decimal(line["planned_quantity"]) for line in r.json()["lines"]] == [400, 100]
    assert Decimal(r.json()["planned_quantity"]) == 500
    r = env.client.patch(f"{ROOT}/allocations/{target['id']}", json={"allocated_quantity": "400.001"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "ALLOCATION_QUANTITY_CONFLICT"
    assert other["id"] != po["id"]
    r = env.client.patch(f"{ROOT}/allocations/{target['id']}", json={"allocated_quantity": "50"})
    assert Decimal(r.json()["lines"][0]["planned_quantity"]) == 50
    assert env.client.get(f"{ROOT}/demands/{d['id']}").json()["status"] == "partially_planned"


def test_release_removes_the_line_and_item_can_be_added_back(env):
    d = env.demand(spec(10, "red"), spec(20, "red"))
    po = env.order((items(d)[0], "100"), (items(d)[1], "200"))
    wide = next(a for a in po["allocations"] if a["production_demand_item_id"] == items(d)[1])
    assert env.client.post(f"{ROOT}/allocations/{wide['id']}/release", json={"reason": "Not this week"}).status_code == 200
    after = env.client.get(f"{ROOT}/production-orders/{po['id']}").json()
    assert line_specs(after) == [spec(10, "red")] and Decimal(after["planned_quantity"]) == 100
    assert next(a for a in after["allocations"] if a["id"] == wide["id"])["status"] == "released"
    # Released history does not block putting the same demand item back into the order.
    r = env.client.post(f"{ROOT}/orders/{po['id']}/allocations", json=env.pairs((items(d)[1], "150"))[0])
    assert r.status_code == 200, r.text
    assert line_specs(r.json()) == [spec(10, "red"), spec(20, "red")]


# PROD-QUALITY-FIX-001: open orders (draft, released, in progress, on hold) take allocation changes; locked ones refuse.
@pytest.mark.parametrize("status", ["completed", "closed", "cancelled"])
def test_locked_orders_refuse_allocation_changes(env, status):
    d = env.demand(spec(10), spec(12))
    po = env.order((items(d)[0], "100"))
    row = env.db.get(ProductionOrder, UUID(po["id"])); row.status = status; env.db.commit()
    add = env.client.post(f"{ROOT}/orders/{po['id']}/allocations", json=env.pairs((items(d)[1], "10"))[0])
    change = env.client.patch(f"{ROOT}/allocations/{po['allocations'][0]['id']}", json={"allocated_quantity": "50"})
    for r in (add, change):
        assert r.status_code == 409 and r.json()["detail"]["code"] == "ORDER_ALLOCATION_LOCKED"
    detail = env.client.get(f"{ROOT}/orders/{po['id']}").json()
    assert detail["editable"] is False and detail["allocation_open"] is False


def test_cancel_keeps_lines_as_history(env):
    d = env.demand(spec(10), spec(20))
    po = env.order((items(d)[0], "100"), (items(d)[1], "200"))
    assert env.client.post(f"{ROOT}/production-orders/{po['id']}/cancel", json={"reason": "Customer withdrew"}).status_code == 200
    after = env.client.get(f"{ROOT}/production-orders/{po['id']}").json()
    assert line_specs(after) == [spec(10), spec(20)]


def test_manual_line_edits_are_blocked_on_planning_orders(env):
    d = env.demand(spec(10))
    po = env.order((items(d)[0], "100"))
    line_id = po["lines"][0]["id"]
    assert env.client.post(f"{ROOT}/production-orders/{po['id']}/items", json={"planned_quantity": "5", "unit": "kg"}).status_code == 400
    assert env.client.patch(f"{ROOT}/production-orders/{po['id']}/items/{line_id}", json={"planned_quantity": "5"}).status_code == 400
    assert env.db.scalar(select(func.count()).select_from(ProductionOrderItem)) == 1


@pytest.mark.parametrize("call", ["add", "change", "preview"])
def test_editing_requires_allocate_permission(env, call):
    d = env.demand(spec(10), spec(12))
    po = env.order((items(d)[0], "100"))
    env.ctx.auth_user.permissions = PERMISSIONS - {"production:planning:allocate"}
    if call == "add":
        r = env.client.post(f"{ROOT}/orders/{po['id']}/allocations", json=env.pairs((items(d)[1], "10"))[0])
    elif call == "change":
        r = env.client.patch(f"{ROOT}/allocations/{po['allocations'][0]['id']}", json={"allocated_quantity": "50"})
    else:
        r = env.client.post(f"{ROOT}/planning/preview-production-order", json={"allocations": env.pairs((items(d)[1], "10"))})
    assert r.status_code == 403


def test_editing_is_tenant_safe(env):
    other = other_org_demand(env.db)
    mine = env.demand(spec(10))
    assert env.client.patch(f"{ROOT}/allocations/{other.allocation.id}", json={"allocated_quantity": "50"}).status_code == 404
    assert env.client.post(f"{ROOT}/orders/{other.order.id}/allocations", json=env.pairs((items(mine)[0], "10"))[0]).status_code == 404
    po = env.order((items(mine)[0], "10"))
    r = env.client.post(f"{ROOT}/orders/{po['id']}/allocations", json=env.pairs((str(other.demand.items[0].id), "10"))[0])
    assert r.status_code == 404
    env.db.expire_all()
    assert env.db.get(ProductionAllocation, other.allocation.id).allocated_quantity == 100
