"""Planning queue lifecycle and allocation release tests (PROD-PLAN-003)."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4
import pytest
from sqlalchemy import func, select
from app.main import app
from app.dependencies import get_current_user
from app.core.tenancy import TenantContext
from app.commercial.infrastructure.models import Customer
from app.foundation.infrastructure.models import Organization, User
from app.production.infrastructure.execution_models import ProductionRun
from app.production.infrastructure.models import ProductionAllocation, ProductionDemand, ProductionDemandItem, ProductionOrder, WorkCenter

ROOT = "/api/v1/production"
PERMISSIONS = frozenset([
    "production:planning:read", "production:planning:allocate", "production:planning:release_allocation",
    "production:production_orders:create", "production:production_orders:cancel", "production:production_orders:read", "production:production_orders:update", "production:production_orders:manage_items",
] + [f"production:demands:{a}" for a in ("read", "create", "update", "release", "cancel")])
ITEM = {"product_type": "film", "required_quantity": "1000", "unit": "kg", "target_spec_json": {"width": 12}}


@pytest.fixture
def env(client, db, test_org, test_user):
    customer = Customer(organization_id=test_org.id, customer_code="C-LIFE", name="Lifecycle Customer")
    center = WorkCenter(organization_id=test_org.id, code="WC-LIFE", name="Line")
    db.add_all([customer, center]); db.commit()
    ctx = SimpleNamespace(user=SimpleNamespace(is_organization_root=False), auth_user=SimpleNamespace(permissions=PERMISSIONS),
                          tenant=TenantContext(test_user.id, test_org.id, permissions=PERMISSIONS))
    app.dependency_overrides[get_current_user] = lambda: ctx

    def demand(*quantities):
        items = [{**deepcopy(ITEM), "required_quantity": q} for q in (quantities or ("1000",))]
        r = client.post(f"{ROOT}/demands", json={"customer_id": str(customer.id), "items": items})
        assert r.status_code == 201, r.text
        assert client.post(f"{ROOT}/demands/{r.json()['id']}/status", json={"status": "ready_for_planning"}).status_code == 200
        return get(r.json()["id"])

    def get(demand_id):
        r = client.get(f"{ROOT}/demands/{demand_id}")
        assert r.status_code == 200, r.text
        return r.json()

    def allocate(*pairs):
        """pairs: (demand_item_id, quantity); returns the response."""
        return client.post(f"{ROOT}/planning/create-production-order", json=dict(
            allocations=[{"production_demand_item_id": i, "allocated_quantity": q} for i, q in pairs],
            work_center_id=str(center.id), planned_start_date="2026-10-01", planned_end_date="2026-10-02"))

    def order(*pairs):
        r = allocate(*pairs)
        assert r.status_code == 201, r.text
        return r.json()

    def release(allocation_id, reason="Order cancelled before execution"):
        return client.post(f"{ROOT}/allocations/{allocation_id}/release", json={"reason": reason})

    def cancel(order_id, reason="Customer withdrew"):
        return client.post(f"{ROOT}/production-orders/{order_id}/cancel", json={"reason": reason})

    def queue(view=None):
        r = client.get(f"{ROOT}/planning/demands" + (f"?view={view}" if view else ""))
        assert r.status_code == 200, r.text
        return {d["id"] for d in r.json()["items"]}

    def set_order_status(order_id, status):
        row = db.get(ProductionOrder, UUID(order_id)); row.status = status; db.commit()

    return SimpleNamespace(db=db, client=client, org=test_org, user=test_user, center=center, customer=customer, ctx=ctx,
                           demand=demand, get=get, allocate=allocate, order=order, release=release, cancel=cancel,
                           queue=queue, set_order_status=set_order_status)


def item_id(demand, index=0):
    return demand["items"][index]["id"]


def item(demand, index=0):
    return demand["items"][index]


def other_org_demand(db):
    org = Organization(name="Other", code="life-other", timezone="UTC")
    db.add(org); db.flush()
    customer = Customer(organization_id=org.id, customer_code="OTHER", name="Other")
    center = WorkCenter(organization_id=org.id, code="WC-O", name="Other line")
    user = User(organization_id=org.id, full_name="Other", email=f"{uuid4().hex}@example.invalid", password_hash="unused")
    db.add_all([customer, center, user]); db.flush()
    demand = ProductionDemand(organization_id=org.id, customer_id=customer.id, demand_number="PD-OTHER", status="ready_for_planning")
    demand.items = [ProductionDemandItem(line_no=1, **deepcopy(ITEM))]
    db.add(demand); db.flush()
    order = ProductionOrder(organization_id=org.id, production_order_number="PO-OTHER", work_center_id=center.id, product_type="film",
                            planned_quantity=100, unit="kg", status="draft", planned_start_date=date.today(), planned_end_date=date.today(),
                            created_by_user_id=user.id)
    db.add(order); db.flush()
    allocation = ProductionAllocation(organization_id=org.id, production_order_id=order.id, production_demand_id=demand.id,
                                      production_demand_item_id=demand.items[0].id, allocated_quantity=100, unit="kg")
    db.add(allocation); db.commit()
    return SimpleNamespace(org=org, demand=demand, order=order, allocation=allocation)


def test_t01_t23_no_allocation_is_ready_for_planning(env):
    d = env.demand()
    assert d["status"] == "ready_for_planning"
    assert item(d)["planning_state"] == "ready_for_planning"
    assert Decimal(item(d)["active_allocated_quantity"]) == 0 and Decimal(item(d)["remaining_quantity"]) == 1000


def test_t02_t03_t04_t22_full_allocation_is_planned_and_kept(env):
    d = env.demand(); env.order((item_id(d), "1000"))
    full = env.get(d["id"])
    assert full["status"] == "planned" and item(full)["planning_state"] == "planned"
    assert Decimal(item(full)["active_allocated_quantity"]) == 1000 and Decimal(item(full)["remaining_quantity"]) == 0
    assert d["id"] not in env.queue()
    assert env.db.get(ProductionDemand, UUID(d["id"])) is not None
    assert len(item(full)["allocations"]) == 1


def test_t05_t06_t07_partial_then_remaining(env):
    d = env.demand(); env.order((item_id(d), "600"))
    partial = env.get(d["id"])
    assert partial["status"] == "partially_planned"
    assert Decimal(item(partial)["active_allocated_quantity"]) == 600 and Decimal(item(partial)["remaining_quantity"]) == 400
    assert d["id"] in env.queue()
    env.order((item_id(d), "400"))
    assert env.get(d["id"])["status"] == "planned"
    assert d["id"] not in env.queue()


def test_t08_one_demand_item_many_orders(env):
    d = env.demand()
    po1, po2 = env.order((item_id(d), "600")), env.order((item_id(d), "400"))
    allocations = item(env.get(d["id"]))["allocations"]
    assert {a["production_order_id"] for a in allocations} == {po1["id"], po2["id"]}
    assert sorted(Decimal(a["allocated_quantity"]) for a in allocations) == [400, 600]


def test_t09_one_order_many_demands(env):
    a, b, c = env.demand("300"), env.demand("200"), env.demand("150")
    po = env.order((item_id(a), "300"), (item_id(b), "200"), (item_id(c), "150"))
    assert Decimal(po["planned_quantity"]) == 650 == Decimal(po["active_allocated_quantity"])
    assert {x["demand_number"] for x in po["allocations"]} == {a["demand_number"], b["demand_number"], c["demand_number"]}
    assert all(env.get(x["id"])["status"] == "planned" for x in (a, b, c))


def test_t10_t11_t12_t13_released_not_counted_and_kept(env):
    d = env.demand()
    env.order((item_id(d), "300"))
    po = env.order((item_id(d), "500"))
    r = env.release(po["allocations"][0]["id"])
    # A single-source order cannot lose its only demand; the order has to be cancelled instead.
    assert r.status_code == 409 and r.json()["detail"]["code"] == "LAST_ACTIVE_ALLOCATION"
    assert env.cancel(po["id"]).status_code == 200
    after = item(env.get(d["id"]))
    assert Decimal(after["active_allocated_quantity"]) == 300
    assert Decimal(after["released_allocated_quantity"]) == 500
    assert Decimal(after["remaining_quantity"]) == 700
    assert {a["status"] for a in after["allocations"]} == {"active", "released"}
    assert env.db.scalar(select(func.count()).select_from(ProductionAllocation)) == 2


def test_t14_t15_release_endpoint_metadata_and_queue_return(env):
    a, b = env.demand("300"), env.demand("200")
    po = env.order((item_id(a), "300"), (item_id(b), "200"))
    assert a["id"] not in env.queue()
    target = next(x for x in po["allocations"] if x["production_demand_id"] == a["id"])
    r = env.release(target["id"], "  Wrong customer line  ")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["allocation"]["status"] == "released"
    assert body["allocation"]["released_by_user_id"] == str(env.user.id)
    assert body["allocation"]["release_reason"] == "Wrong customer line"
    assert body["allocation"]["released_at"] is not None
    assert body["demand"]["status"] == "ready_for_planning"
    assert Decimal(body["demand"]["total_remaining"]) == 300 and Decimal(body["demand"]["total_released_allocated"]) == 300
    assert a["id"] in env.queue() and b["id"] not in env.queue()
    # The order keeps its remaining active source; planned quantity follows ACTIVE allocations.
    order = env.client.get(f"{ROOT}/production-orders/{po['id']}").json()
    assert Decimal(order["planned_quantity"]) == 200 and len(order["allocations"]) == 2
    assert env.release(target["id"]).json()["detail"]["code"] == "ALLOCATION_ALREADY_RELEASED"


def test_t16_t17_cancel_pre_execution_releases_all(env):
    a, b = env.demand("300"), env.demand("200", "100")
    po = env.order((item_id(a), "300"), (item_id(b, 0), "200"), (item_id(b, 1), "50"))
    assert env.get(b["id"])["status"] == "partially_planned"
    r = env.cancel(po["id"])
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"
    assert {x["status"] for x in r.json()["allocations"]} == {"released"} and len(r.json()["allocations"]) == 3
    assert all(x["release_reason"] == "Customer withdrew" for x in r.json()["allocations"])
    for d in (a, b):
        fresh = env.get(d["id"])
        assert fresh["status"] == "ready_for_planning" and Decimal(fresh["total_active_allocated"]) == 0
        assert d["id"] in env.queue()
    assert env.cancel(po["id"]).json()["detail"]["code"] == "TRANSITION_NOT_ALLOWED"  # cancelled is terminal


def test_cancel_via_status_patch_is_rejected(env):
    d = env.demand(); po = env.order((item_id(d), "100"))
    assert env.client.patch(f"{ROOT}/production-orders/{po['id']}", json={"status": "cancelled"}).status_code == 422
    assert env.get(d["id"])["status"] == "partially_planned"


def test_released_order_without_execution_is_releasable(env):
    d = env.demand(); po = env.order((item_id(d), "100"))
    env.set_order_status(po["id"], "released")
    assert env.cancel(po["id"]).status_code == 200
    assert env.get(d["id"])["status"] == "ready_for_planning"


@pytest.mark.parametrize("status,code", [("in_progress", "ORDER_EXECUTION_STARTED"), ("completed", "ORDER_COMPLETED")])
def test_t18_t19_started_or_completed_orders_block_release(env, status, code):
    d = env.demand()
    env.order((item_id(d), "100"))
    po = env.order((item_id(d), "200"), )
    env.set_order_status(po["id"], status)
    r = env.release(po["allocations"][0]["id"])
    assert r.status_code == 409 and r.json()["detail"]["code"] == code
    # The lifecycle does not offer cancel once production has started or finished.
    r = env.cancel(po["id"])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "TRANSITION_NOT_ALLOWED"
    fresh = item(env.get(d["id"]))
    assert Decimal(fresh["active_allocated_quantity"]) == 300 and Decimal(fresh["released_allocated_quantity"]) == 0


def test_t20_execution_evidence_blocks_release(env):
    d = env.demand(); po = env.order((item_id(d), "100"))
    env.set_order_status(po["id"], "released")
    env.db.add(ProductionRun(organization_id=env.org.id, production_order_id=UUID(po["id"]), work_center_id=env.center.id,
                             run_date=date.today(), status="in_progress", created_by_user_id=env.user.id))
    env.db.commit()
    r = env.cancel(po["id"])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "ORDER_EXECUTION_STARTED"
    assert "production_runs" in r.json()["detail"]["execution_records"]
    assert env.db.get(ProductionOrder, UUID(po["id"])).status == "released"
    assert env.get(d["id"])["status"] == "partially_planned"


def test_planned_run_is_not_execution_evidence(env):
    d = env.demand(); po = env.order((item_id(d), "100"))
    env.db.add(ProductionRun(organization_id=env.org.id, production_order_id=UUID(po["id"]), work_center_id=env.center.id,
                             run_date=date.today(), status="planned", created_by_user_id=env.user.id))
    env.db.commit()
    assert env.cancel(po["id"]).status_code == 200


def test_t21_second_allocation_of_same_remaining_conflicts(env):
    # Sequential proof of the invariant; the real parallel race runs in test_production_allocation_postgres.py.
    d = env.demand(); env.order((item_id(d), "600"))
    assert env.allocate((item_id(d), "400")).status_code == 201
    r = env.allocate((item_id(d), "400"))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "ALLOCATION_QUANTITY_CONFLICT"
    assert env.db.scalar(select(func.sum(ProductionAllocation.allocated_quantity))) == 1000


def test_decimal_precision_is_exact(env):
    d = env.demand("1.003"); env.order((item_id(d), "0.001")); env.order((item_id(d), "1.002"))
    assert env.get(d["id"])["status"] == "planned"
    assert env.allocate((item_id(d), "0.001")).status_code == 409


def test_t24_t25_header_aggregates_mixed_item_states(env):
    d = env.demand("100", "100")
    env.order((item_id(d, 0), "100"))
    mixed = env.get(d["id"])
    assert [i["planning_state"] for i in mixed["items"]] == ["planned", "ready_for_planning"]
    assert mixed["status"] == "partially_planned" and d["id"] in env.queue()
    env.order((item_id(d, 1), "100"))
    assert env.get(d["id"])["status"] == "planned"


def test_t26_cancelled_demand_is_not_overwritten(env):
    a, b = env.demand("100"), env.demand("100")
    po = env.order((item_id(a), "50"), (item_id(b), "50"))
    row = env.db.get(ProductionDemand, UUID(a["id"])); row.status = "cancelled"; env.db.commit()
    assert env.cancel(po["id"]).status_code == 200
    assert env.get(a["id"])["status"] == "cancelled"
    assert env.get(b["id"])["status"] == "ready_for_planning"


def test_derived_statuses_cannot_be_forced(env):
    d = env.demand()
    for status in ("partially_planned", "planned"):
        r = env.client.post(f"{ROOT}/demands/{d['id']}/status", json={"status": status})
        assert r.status_code == 409 and r.json()["detail"]["code"] == "status_derived_from_allocations"


def test_t27_cross_tenant_release_and_cancel_rejected(env):
    other = other_org_demand(env.db)
    assert env.release(other.allocation.id).status_code == 404
    assert env.cancel(other.order.id).status_code == 404
    env.db.expire_all()
    assert env.db.get(ProductionAllocation, other.allocation.id).status == "active"


def test_t28_cross_tenant_allocation_rejected(env):
    other = other_org_demand(env.db)
    mine = env.demand()
    r = env.allocate((item_id(mine), "10"), (str(other.demand.items[0].id), "10"))
    assert r.status_code == 404
    assert env.db.scalar(select(func.count()).select_from(ProductionAllocation).where(ProductionAllocation.organization_id == env.org.id)) == 0


def test_t29_active_planned_all_views(env):
    ready, partial, planned = env.demand(), env.demand(), env.demand()
    env.order((item_id(partial), "10")); env.order((item_id(planned), "1000"))
    draft = env.client.post(f"{ROOT}/demands", json={"customer_id": str(env.customer.id), "items": [ITEM]}).json()
    assert env.queue() == env.queue("active") == {ready["id"], partial["id"]}
    assert env.queue("planned") == {planned["id"]}
    assert env.queue("all") == {ready["id"], partial["id"], planned["id"], draft["id"]}
    r = env.client.get(f"{ROOT}/planning/demands?view=active&page_size=1")
    assert r.json()["total"] == 2 and len(r.json()["items"]) == 1
    assert env.client.get(f"{ROOT}/planning/demands?view=bogus").status_code == 400


def test_planning_statuses_narrow_the_view_and_count_the_hidden(env):
    ready, partial, planned = env.demand(), env.demand(), env.demand()
    env.order((item_id(partial), "10")); env.order((item_id(planned), "1000"))
    env.client.post(f"{ROOT}/demands", json={"customer_id": str(env.customer.id), "items": [ITEM]})  # a draft
    # The active queue with the matching statuses reports everything outside it as hidden.
    body = env.client.get(f"{ROOT}/planning/demands", params=[("view", "active"), ("statuses", "ready_for_planning"), ("statuses", "partially_planned")]).json()
    assert {d["id"] for d in body["items"]} == {ready["id"], partial["id"]} and body["hidden_by_status"] == 2
    body = env.client.get(f"{ROOT}/planning/demands", params=[("view", "all"), ("statuses", "planned"), ("statuses", "ready_for_planning")]).json()
    assert {d["id"] for d in body["items"]} == {ready["id"], planned["id"]} and body["hidden_by_status"] == 2
    assert env.client.get(f"{ROOT}/planning/demands").json()["hidden_by_status"] is None


def test_t30_demand_detail_includes_allocation_history(env):
    d = env.demand()
    keep, drop = env.order((item_id(d), "600")), env.order((item_id(d), "100"))
    env.cancel(drop["id"], "Machine unavailable")
    history = {a["production_order_id"]: a for a in item(env.get(d["id"]))["allocations"]}
    assert history[keep["id"]]["status"] == "active" and history[keep["id"]]["released_at"] is None
    assert history[drop["id"]]["status"] == "released" and history[drop["id"]]["release_reason"] == "Machine unavailable"
    assert history[drop["id"]]["production_order_number"] == drop["production_order_number"]
    assert history[drop["id"]]["production_order_status"] == "cancelled"
    assert history[keep["id"]]["created_at"] is not None


def test_order_detail_keeps_released_allocation_sources(env):
    d = env.demand(); po = env.order((item_id(d), "100")); env.cancel(po["id"])
    source = env.client.get(f"{ROOT}/production-orders/{po['id']}").json()["allocations"][0]
    assert source["status"] == "released" and source["customer_name"] == "Lifecycle Customer"
    assert source["demand_number"] == d["demand_number"] and source["demand_item_line_no"] == 1


def test_release_reason_required(env):
    d = env.demand(); po = env.order((item_id(d), "100"))
    assert env.client.post(f"{ROOT}/allocations/{po['allocations'][0]['id']}/release", json={"reason": "   "}).status_code == 400
    assert env.client.post(f"{ROOT}/production-orders/{po['id']}/cancel", json={}).status_code == 422


@pytest.mark.parametrize("missing,call", [
    ("production:planning:release_allocation", "release"),
    ("production:production_orders:cancel", "cancel"),
])
def test_release_and_cancel_permissions(env, missing, call):
    d = env.demand(); env.order((item_id(d), "100")); po = env.order((item_id(d), "100"))
    env.ctx.auth_user.permissions = PERMISSIONS - {missing}
    r = env.release(po["allocations"][0]["id"]) if call == "release" else env.cancel(po["id"])
    assert r.status_code == 403


def test_release_and_cancel_are_audited(env):
    from app.foundation.infrastructure.models import TenantActivityLog
    d = env.demand()
    keep = env.order((item_id(d), "100"), )
    po = env.order((item_id(d), "200"))
    env.cancel(po["id"], "Machine unavailable")
    two = env.demand("50", "50")
    multi = env.order((item_id(two, 0), "50"), (item_id(two, 1), "50"))
    env.release(multi["allocations"][0]["id"], "Wrong line")
    rows = {r.action: r for r in env.db.scalars(select(TenantActivityLog).where(TenantActivityLog.organization_id == env.org.id))}
    cancelled, released = rows["production_order.status_changed"], rows["production_allocation.released"]
    assert cancelled.actor_id == env.user.id and cancelled.details["reason"] == "Machine unavailable"
    assert cancelled.details["action"] == "cancel" and cancelled.details["released_allocations"] == "1"
    assert released.actor_id == env.user.id and released.details["reason"] == "Wrong line"
    assert keep["id"] not in str(cancelled.details)
