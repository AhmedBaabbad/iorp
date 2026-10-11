"""The demand items an open production order may take, searched on the server (PROD-QUALITY-FIX-001, item 2 follow-up).

The order page's "Add a demand" picker used to read the first 100 demands of the planning queue and filter them in the
browser, so a matching demand past the hundredth never showed. The server now answers the eligible items directly.
"""
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from app.commercial.infrastructure.models import Customer
from app.production.infrastructure.models import ProductionDemand, ProductionDemandItem, ProductionOrder
from tests.test_production_allocation_lifecycle import other_org_demand
from tests.test_production_order_lines import ROOT, env, items, spec  # noqa: F401  (env is a fixture)


def eligible(env, order_id, **params):
    r = env.client.get(f"{ROOT}/orders/{order_id}/eligible-demand-items", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def many_demands(env, count, start=1, product="film", unit="kg"):
    """Demands straight in the database (quick), ready for planning, one item each."""
    customer = env.db.scalar(select(Customer).where(Customer.organization_id == env.org.id))
    rows = []
    for n in range(start, start + count):
        demand = ProductionDemand(organization_id=env.org.id, customer_id=customer.id, demand_number=f"PD-BULK-{n:04d}", status="ready_for_planning",
                                  planning_sequence=n)
        demand.items = [ProductionDemandItem(line_no=1, product_type=product, unit=unit, required_quantity=Decimal(100), target_spec_json=spec(10))]
        rows.append(demand)
    env.db.add_all(rows); env.db.commit()
    return rows


def test_a_matching_demand_past_the_hundredth_is_found_by_search(env):
    first = env.demand(spec(10))
    po = env.order((items(first)[0], "100"))
    bulk = many_demands(env, 105)
    shown = eligible(env, po["id"])
    assert len(shown) == 20  # a picker answer, not a page of demands
    late = bulk[102]  # the 103rd demand of the queue
    found = eligible(env, po["id"], search=late.demand_number)
    assert [r["demand_number"] for r in found] == [late.demand_number]
    assert Decimal(found[0]["remaining_quantity"]) == 100 and found[0]["customer_name"] == "Lines Customer"


def test_only_items_the_order_can_take(env):
    base = env.demand(spec(10))
    po = env.order((items(base)[0], "100"))
    ok = env.demand(spec(12))
    other_unit = env.demand(spec(10), unit="m")
    other_product = env.demand(spec(10), product="tape")
    full = env.demand(spec(10), quantity="50")
    env.order((items(full)[0], "50"))  # fully allocated elsewhere
    partly = env.demand(spec(10), quantity="80")
    env.order((items(partly)[0], "30"))  # 50 left
    draft = env.client.post(f"{ROOT}/demands", json={"customer_id": str(env.db.scalar(select(Customer.id).where(Customer.organization_id == env.org.id))),
                                                     "items": [dict(product_type="film", unit="kg", required_quantity="10", target_spec_json=spec(10))]}).json()
    other_org_demand(env.db)
    shown = {r["demand_number"]: r for r in eligible(env, po["id"])}
    assert ok["demand_number"] in shown and partly["demand_number"] in shown
    assert Decimal(shown[partly["demand_number"]]["remaining_quantity"]) == 50
    for absent in (base, other_unit, other_product, full):  # already in the order, other unit, other product, nothing left
        assert absent["demand_number"] not in shown
    assert draft["demand_number"] not in shown and "PD-OTHER" not in shown  # not plannable; another organization


def test_search_by_customer_name_and_limits(env):
    base = env.demand(spec(10))
    po = env.order((items(base)[0], "100"))
    many_demands(env, 3)
    assert len(eligible(env, po["id"], search="Lines Cust")) == 3
    assert eligible(env, po["id"], search="nobody-matches") == []
    assert len(eligible(env, po["id"], limit=2)) == 2
    # The planning routes answer an invalid request with 400 INVALID_ALLOCATION_REQUEST (their convention).
    r = env.client.get(f"{ROOT}/orders/{po['id']}/eligible-demand-items", params={"limit": 51})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "INVALID_ALLOCATION_REQUEST"


def test_open_orders_only_and_tenant_scoped(env):
    base = env.demand(spec(10))
    po = env.order((items(base)[0], "100"))
    row = env.db.get(ProductionOrder, UUID(po["id"]))
    row.status = "in_progress"; env.db.commit()
    assert env.client.get(f"{ROOT}/orders/{po['id']}/eligible-demand-items").status_code == 200
    row.status = "completed"; env.db.commit()
    r = env.client.get(f"{ROOT}/orders/{po['id']}/eligible-demand-items")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "ORDER_ALLOCATION_LOCKED"
    foreign = other_org_demand(env.db)
    r = env.client.get(f"{ROOT}/orders/{foreign.order.id}/eligible-demand-items")
    assert r.status_code == 404 and r.json()["detail"]["code"] == "PRODUCTION_ORDER_NOT_FOUND"
