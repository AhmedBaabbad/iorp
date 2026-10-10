"""PROD-OUTPUT-001: the final order result. Numbered comments refer to the task's required tests."""
from datetime import date, time
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.commercial.infrastructure.models import Customer
from app.core.tenancy import TenantContext
from app.dependencies import get_current_user
from app.main import app
from app.production.infrastructure.models import (
    ProductionOrder, ProductionOrderItem, ProductionOrderStatusHistory, ProductionResultEntry, WorkCenter,
)
from tests.test_production_allocation_lifecycle import other_org_demand

ROOT = "/api/v1/production"
PERMISSIONS = frozenset(
    ["production:production_orders:read", "production:production_orders:update", "production:production_orders:manage_items", "production:planning:read", "production:planning:allocate",
     "production:production_orders:create"]
    + [f"production:production_orders:{a}" for a in ("release", "start", "hold", "complete", "close", "cancel")]
    + [f"production:results:{a}" for a in ("read", "create", "update", "delete", "correct")] + [f"production:demands:{a}" for a in ("read", "create", "update", "release", "cancel")])


@pytest.fixture
def env(client, db, test_org, test_user):
    customer = Customer(organization_id=test_org.id, customer_code="C-RES", name="Result Customer")
    center = WorkCenter(organization_id=test_org.id, code="WC-RES", name="Line 1")
    db.add_all([customer, center]); db.commit()
    ctx = SimpleNamespace(user=SimpleNamespace(is_organization_root=False), auth_user=SimpleNamespace(permissions=set(PERMISSIONS)),
                          tenant=TenantContext(test_user.id, test_org.id, permissions=PERMISSIONS))
    app.dependency_overrides[get_current_user] = lambda: ctx

    def transition(order_id, action, reason="because", **extra):
        return client.post(f"{ROOT}/production-orders/{order_id}/transitions", json={"action": action, "reason": reason, **extra})

    def planned(*specs, quantity="400", to="completed"):
        """A planning order with customer allocations per item (one item per spec), moved to `to`."""
        items = [dict(product_type="film", unit="kg", required_quantity="1000", target_spec_json=s) for s in (specs or ({"width_mm": 10},))]
        demand_id = client.post(f"{ROOT}/demands", json={"customer_id": str(customer.id), "items": items}).json()["id"]
        client.post(f"{ROOT}/demands/{demand_id}/status", json={"status": "ready_for_planning"})
        demand = client.get(f"{ROOT}/demands/{demand_id}").json()
        r = client.post(f"{ROOT}/planning/create-production-order", json=dict(
            allocations=[{"production_demand_item_id": i["id"], "allocated_quantity": quantity} for i in demand["items"]],
            work_center_id=str(center.id), planned_start_date="2026-10-01", planned_end_date="2026-10-03"))
        assert r.status_code == 201, r.text
        po = r.json()
        path = {"draft": [], "released": ["release"], "in_progress": ["release", "start"], "completed": ["release", "start", "complete"],
                "cancelled": ["cancel"], "on_hold": ["release", "start", "hold"]}[to]
        for action in path:
            assert transition(po["id"], action).status_code == 200
        return client.get(f"{ROOT}/production-orders/{po['id']}").json()

    def bare(*units, status="completed", planned_quantity="100"):
        """An order without customer allocations, one item per unit (no items when `units` is empty)."""
        order = ProductionOrder(organization_id=test_org.id, production_order_number=f"PO-{uuid4().hex[:8]}", work_center_id=center.id,
                                product_type="film", planned_quantity=Decimal(planned_quantity) * max(len(units), 1), unit=units[0] if units else "kg",
                                status=status, planned_start_date=date(2026, 10, 1), planned_end_date=date(2026, 10, 3), created_by_user_id=test_user.id)
        order.items = [ProductionOrderItem(line_no=n + 1, planned_quantity=Decimal(planned_quantity), unit=u) for n, u in enumerate(units)]
        db.add(order); db.commit()
        return dict(id=str(order.id), lines=[dict(id=str(i.id), unit=i.unit) for i in order.items])

    def add(po, disposition="stock_good", quantity="10", line=0, **extra):
        body = dict(disposition=disposition, quantity=quantity, **extra)
        if po.get("lines") and line is not None and len(po["lines"]) > 1:
            body.setdefault("production_order_item_id", po["lines"][line]["id"])
        return client.post(f"{ROOT}/production-orders/{po['id']}/result/entries", json=body)

    def added(po, *args, **kwargs):
        r = add(po, *args, **kwargs)
        assert r.status_code == 201, r.text
        return r.json()

    def result(po):
        r = client.get(f"{ROOT}/production-orders/{po['id']}/result")
        assert r.status_code == 200, r.text
        return r.json()

    def rows(po):
        db.expire_all()
        return list(db.scalars(select(ProductionResultEntry).where(ProductionResultEntry.production_order_id == UUID(po["id"]))
                               .order_by(ProductionResultEntry.created_at)))

    def close(po, **extra):
        r = transition(po["id"], "close", **extra)
        assert r.status_code == 200, r.text

    return SimpleNamespace(db=db, client=client, org=test_org, user=test_user, ctx=ctx, center=center, planned=planned, bare=bare,
                           add=add, added=added, result=result, rows=rows, transition=transition, close=close)


def code(r):
    return r.json()["detail"]["code"]


def entry_url(po, entry_id, suffix=""):
    return f"{ROOT}/production-orders/{po['id']}/result/entries/{entry_id}{suffix}"


# ---- 1-4: lifecycle and locking ----------------------------------------------------------------

@pytest.mark.parametrize("status", ["draft", "released", "in_progress", "on_hold", "cancelled"])
def test_01_writes_rejected_before_completion_and_after_cancel(env, status):
    po = env.planned(to=status)
    r = env.add(po, "stock_good")
    assert r.status_code == 409 and code(r) == "RESULT_NOT_AVAILABLE" and r.json()["detail"]["order_status"] == status
    assert env.rows(po) == []
    view = env.result(po)
    assert view["available"] is False and view["actions"] == []


def test_02_completed_order_allows_create_edit_delete(env):
    po = env.planned()
    view = env.added(po, "scrap", "12.5", reason_code="EDGE_TRIM", notes="trim")
    entry = view["entries"][0]
    assert entry["actions"] == ["edit", "delete"] and view["actions"] == ["create"]
    r = env.client.patch(entry_url(po, entry["id"]), json={"quantity": "20", "notes": "re-weighed"})
    assert r.status_code == 200, r.text
    (row,) = env.rows(po)
    assert (row.quantity, row.notes, row.disposition, row.counts_as_loss, row.updated_by_user_id) == (Decimal("20"), "re-weighed", "scrap", True, env.user.id)
    assert env.client.delete(entry_url(po, entry["id"])).status_code == 204
    assert env.rows(po) == []


def test_03_closed_order_rejects_direct_create_edit_delete(env):
    po = env.planned()
    entry = env.added(po, "stock_good", "30")["entries"][0]
    env.close(po)
    for r in (env.client.patch(entry_url(po, entry["id"]), json={"quantity": "5"}), env.client.delete(entry_url(po, entry["id"])), env.add(po)):
        assert r.status_code == 409 and code(r) == "RESULT_LOCKED"
    (row,) = env.rows(po)
    assert row.quantity == Decimal("30")
    assert env.result(po)["entries"][0]["actions"] == ["correct"]


def test_04_correction_only_when_closed_needs_reason_and_keeps_original(env):
    po = env.planned()
    entry = env.added(po, "stock_good", "30", secondary_quantity="3", secondary_unit="kg")["entries"][0]
    r = env.client.post(entry_url(po, entry["id"], "/corrections"), json={"quantity": "-5", "correction_reason": "scale"})
    assert r.status_code == 409 and code(r) == "CORRECTION_REQUIRES_CLOSED_ORDER"
    env.close(po)
    assert env.client.post(entry_url(po, entry["id"], "/corrections"), json={"quantity": "-5"}).status_code == 422
    assert env.client.post(entry_url(po, entry["id"], "/corrections"), json={"quantity": "-5", "correction_reason": ""}).status_code == 422
    r = env.client.post(entry_url(po, entry["id"], "/corrections"), json={"quantity": "-5", "secondary_quantity": "-0.5", "correction_reason": "scale drift"})
    assert r.status_code == 201, r.text
    original, correction = env.rows(po)
    assert (original.quantity, original.entry_type, original.secondary_quantity) == (Decimal("30"), "original", Decimal("3"))
    assert (correction.entry_type, correction.corrects_entry_id, correction.quantity, correction.correction_reason) == ("correction", original.id, Decimal("-5"), "scale drift")
    assert (correction.disposition, correction.unit, correction.production_order_item_id, correction.created_by_user_id) == (
        original.disposition, original.unit, original.production_order_item_id, env.user.id)
    shown = r.json()["entries"][0]
    assert Decimal(shown["effective_quantity"]) == 25 and [c["id"] for c in shown["corrections"]] == [str(correction.id)]
    # A correction cannot itself be corrected.
    again = env.client.post(entry_url(po, correction.id, "/corrections"), json={"quantity": "1", "correction_reason": "x"})
    assert again.status_code == 422 and code(again) == "CORRECT_THE_ORIGINAL"


def test_05_correction_cannot_make_effective_total_negative(env):
    po = env.planned()
    entry = env.added(po, "scrap", "10")["entries"][0]
    env.close(po)
    assert env.client.post(entry_url(po, entry["id"], "/corrections"), json={"quantity": "-6", "correction_reason": "a"}).status_code == 201
    r = env.client.post(entry_url(po, entry["id"], "/corrections"), json={"quantity": "-4.001", "correction_reason": "b"})
    assert r.status_code == 422 and code(r) == "CORRECTION_MAKES_TOTAL_NEGATIVE"
    assert env.client.post(entry_url(po, entry["id"], "/corrections"), json={"quantity": "-4", "correction_reason": "c"}).status_code == 201
    assert Decimal(env.result(po)["entries"][0]["effective_quantity"]) == 0


# ---- 6-8: dispositions and loss --------------------------------------------------------------------

@pytest.mark.parametrize("disposition,extra,loss", [("customer_good", {}, False), ("stock_good", {}, False), ("sample", {"counts_as_loss": False}, False),
                                                    ("sample", {"counts_as_loss": True}, True), ("scrap", {}, True), ("rework", {}, False)])
def test_06_each_disposition_can_be_recorded(env, disposition, extra, loss):
    po = env.planned()
    env.added(po, disposition, "7", **extra)
    (row,) = env.rows(po)
    assert (row.disposition, row.quantity, row.unit, row.counts_as_loss) == (disposition, Decimal("7"), "kg", loss)


def test_07_customer_good_capped_by_allocation_and_needs_one(env):
    po = env.planned(quantity="400")
    env.added(po, "customer_good", "300")
    r = env.add(po, "customer_good", "100.001")
    assert r.status_code == 422 and code(r) == "CUSTOMER_GOOD_EXCEEDS_ALLOCATION"
    assert r.json()["detail"]["allocated_quantity"] == "400.000" and r.json()["detail"]["excess_quantity"] == "0.001"
    env.added(po, "customer_good", "100")
    env.added(po, "stock_good", "25")  # the surplus goes to stock
    # Editing an entry counts its own quantity only once.
    first = env.result(po)["entries"][0]
    assert env.client.patch(entry_url(po, first["id"]), json={"quantity": "300"}).status_code == 200
    assert code(env.client.patch(entry_url(po, first["id"]), json={"quantity": "301"})) == "CUSTOMER_GOOD_EXCEEDS_ALLOCATION"
    # Turning stock into customer good is checked too.
    stock = env.result(po)["entries"][2]
    assert code(env.client.patch(entry_url(po, stock["id"]), json={"disposition": "customer_good"})) == "CUSTOMER_GOOD_EXCEEDS_ALLOCATION"
    unallocated = env.bare("kg")
    r = env.add(unallocated, "customer_good", "1")
    assert r.status_code == 422 and code(r) == "NO_CUSTOMER_ALLOCATION"
    assert env.rows(unallocated) == []


def test_07b_positive_correction_of_customer_good_respects_the_cap(env):
    po = env.planned(quantity="100")
    entry = env.added(po, "customer_good", "100")["entries"][0]
    env.close(po)
    r = env.client.post(entry_url(po, entry["id"], "/corrections"), json={"quantity": "1", "correction_reason": "recount"})
    assert r.status_code == 422 and code(r) == "CUSTOMER_GOOD_EXCEEDS_ALLOCATION"


def test_08_counts_as_loss_forced_except_samples_which_must_choose(env):
    po = env.planned()
    for disposition, sent, stored in (("scrap", False, True), ("stock_good", True, False), ("rework", True, False), ("customer_good", True, False)):
        env.added(po, disposition, "1", counts_as_loss=sent)
        assert env.rows(po)[-1].counts_as_loss is stored
    r = env.add(po, "sample", "1")
    assert r.status_code == 422 and code(r) == "SAMPLE_LOSS_FLAG_REQUIRED"
    sample = env.added(po, "sample", "2", counts_as_loss=False)["entries"][-1]
    # Changing a sample to scrap re-derives the flag; a sample never silently becomes scrap.
    assert env.rows(po)[-1].disposition == "sample"
    env.client.patch(entry_url(po, sample["id"]), json={"disposition": "scrap"})
    assert (env.rows(po)[-1].disposition, env.rows(po)[-1].counts_as_loss) == ("scrap", True)
    r = env.client.patch(entry_url(po, sample["id"]), json={"disposition": "sample"})
    assert code(r) == "SAMPLE_LOSS_FLAG_REQUIRED"


# ---- 9-10: summary -------------------------------------------------------------------------------

def test_09_summary_formulas_with_sample_loss_and_corrections(env):
    po = env.planned(quantity="400")
    customer = env.added(po, "customer_good", "300")["entries"][0]
    env.added(po, "stock_good", "50")
    env.added(po, "sample", "10", counts_as_loss=True)
    env.added(po, "sample", "5", counts_as_loss=False)
    scrap = env.added(po, "scrap", "20")["entries"][-1]
    env.added(po, "rework", "15")
    env.close(po)
    env.client.post(entry_url(po, scrap["id"], "/corrections"), json={"quantity": "-5", "correction_reason": "wet"})
    env.client.post(entry_url(po, customer["id"], "/corrections"), json={"quantity": "-10", "correction_reason": "returned"})
    view = env.result(po)
    (total,) = view["totals"]
    item = view["items"][0]["summary"]
    expected = dict(customer_good=290, stock_good=50, good_total=340, samples_total=15, samples_loss=10, scrap_total=15, loss_total=25,
                    rework_total=15, total_output=385, planned_qty=400, allocated_qty=400, fulfillment_pct=Decimal("72.50"),
                    yield_pct=Decimal("88.31"), loss_pct=Decimal("6.49"), variance_qty=-60)
    for summary in (total, item):
        assert {k: Decimal(summary[k]) for k in expected} == {k: Decimal(v) for k, v in expected.items()}
    assert total["unit"] == "kg"


def test_09b_percentages_are_null_without_a_denominator(env):
    po = env.bare("kg")
    (total,) = env.result(po)["totals"]
    assert total["yield_pct"] is None and total["loss_pct"] is None and total["fulfillment_pct"] is None
    assert Decimal(total["variance_qty"]) == -100


def test_10_different_units_are_never_summed(env):
    po = env.bare("kg", "m")
    env.added(po, "stock_good", "10", line=0)
    env.added(po, "stock_good", "5", line=1, secondary_quantity="3", secondary_unit="kg")
    view = env.result(po)
    groups = {t["unit"]: t for t in view["totals"]}
    assert set(groups) == {"kg", "m"}
    assert Decimal(groups["kg"]["good_total"]) == 10 and Decimal(groups["m"]["good_total"]) == 5
    # The secondary measure is totalled by its own unit, apart from the primary one.
    assert [(s["unit"], Decimal(s["quantity"])) for s in groups["m"]["secondary_totals"]] == [("kg", 3)]
    assert Decimal(groups["kg"]["good_total"]) != 13
    r = env.add(po, "stock_good", "1", line=1, unit="kg")
    assert r.status_code == 422 and code(r) == "UNIT_MISMATCH" and r.json()["detail"]["expected_unit"] == "m"
    assert env.add(po, "stock_good", "1", line=0, secondary_quantity="2").status_code == 422


# ---- 11: item assignment ---------------------------------------------------------------------------

def test_11_item_auto_assigned_required_or_rejected(env):
    single = env.planned()
    env.added(single, "stock_good", "1")
    assert str(env.rows(single)[0].production_order_item_id) == single["lines"][0]["id"]
    multi = env.planned({"width_mm": 10}, {"width_mm": 20})
    r = env.client.post(f"{ROOT}/production-orders/{multi['id']}/result/entries", json={"disposition": "stock_good", "quantity": "1"})
    assert r.status_code == 422 and code(r) == "ORDER_ITEM_REQUIRED"
    r = env.add(multi, "stock_good", "1", production_order_item_id=single["lines"][0]["id"])
    assert r.status_code == 422 and code(r) == "ORDER_ITEM_NOT_IN_ORDER"
    assert env.rows(multi) == []


# ---- 12: close guard ---------------------------------------------------------------------------------

def test_12_close_guard_requires_result_or_zero_output_with_reason(env):
    po = env.planned({"width_mm": 10}, {"width_mm": 20})
    assert code(env.transition(po["id"], "close")) == "RESULT_REQUIRED_TO_CLOSE"
    env.added(po, "stock_good", "5", line=0)
    r = env.transition(po["id"], "close")
    assert r.status_code == 409 and code(r) == "RESULT_MISSING_FOR_ITEMS" and r.json()["detail"]["missing_item_ids"] == [po["lines"][1]["id"]]
    assert code(env.transition(po["id"], "close", zero_output=True, reason="nothing")) == "ZERO_OUTPUT_WITH_ENTRIES"
    assert env.result(po)["close_check"]["ready"] is False
    env.added(po, "scrap", "1", line=1)
    assert env.result(po)["close_check"]["ready"] is True
    env.close(po)

    empty = env.planned()
    assert code(env.transition(empty["id"], "close", zero_output=True, reason="")) == "REASON_REQUIRED"
    assert code(env.transition(empty["id"], "close", zero_output=True, reason=None)) == "REASON_REQUIRED"
    env.close(empty, zero_output=True, reason="Material never arrived")
    history = env.db.scalars(select(ProductionOrderStatusHistory).where(ProductionOrderStatusHistory.production_order_id == UUID(empty["id"]))
                             .order_by(ProductionOrderStatusHistory.created_at)).all()
    assert (history[-1].to_status, history[-1].reason, history[-1].actor_user_id) == ("closed", "Material never arrived", env.user.id)
    assert code(env.transition(env.planned(to="in_progress")["id"], "hold", zero_output=True, reason="x")) == "ZERO_OUTPUT_ONLY_ON_CLOSE"


# ---- 13-14: security -------------------------------------------------------------------------------

def test_13_other_organizations_orders_are_invisible_and_body_org_is_refused(env):
    foreign = other_org_demand(env.db)
    foreign.order.status = "completed"; env.db.commit()
    other = dict(id=str(foreign.order.id), lines=[])
    assert env.client.get(f"{ROOT}/production-orders/{other['id']}/result").status_code == 404
    assert env.add(other, "stock_good", "1").status_code == 404
    po = env.planned()
    r = env.add(po, "stock_good", "1", organization_id=str(foreign.org.id))
    assert r.status_code == 422  # never accepted from the body
    env.added(po, "stock_good", "1")
    assert {row.organization_id for row in env.rows(po)} == {env.org.id}
    entry = env.result(po)["entries"][0]
    # An entry id is only valid under its own order.
    assert env.client.patch(f"{ROOT}/production-orders/{other['id']}/result/entries/{entry['id']}", json={"quantity": "2"}).status_code == 404


@pytest.mark.parametrize("missing,call,expected", [
    ("production:results:read", lambda env, po, e: env.client.get(f"{ROOT}/production-orders/{po['id']}/result"), 403),
    ("production:results:create", lambda env, po, e: env.add(po), 403),
    ("production:results:update", lambda env, po, e: env.client.patch(entry_url(po, e["id"]), json={"quantity": "2"}), 403),
    ("production:results:delete", lambda env, po, e: env.client.delete(entry_url(po, e["id"])), 403),
])
def test_14_permissions_enforced_per_action(env, missing, call, expected):
    po = env.planned()
    entry = env.added(po, "stock_good", "1")["entries"][0]
    env.ctx.auth_user.permissions = set(PERMISSIONS) - {missing}
    assert call(env, po, entry).status_code == expected
    assert len(env.rows(po)) == 1 and env.rows(po)[0].quantity == Decimal("1")


def test_14b_correct_permission_and_allowed_actions(env):
    po = env.planned()
    entry = env.added(po, "stock_good", "5")["entries"][0]
    env.close(po)
    env.ctx.auth_user.permissions = set(PERMISSIONS) - {"production:results:correct"}
    assert env.client.post(entry_url(po, entry["id"], "/corrections"), json={"quantity": "-1", "correction_reason": "x"}).status_code == 403
    assert env.result(po)["entries"][0]["actions"] == []
    env.ctx.auth_user.permissions = set(PERMISSIONS) - {"production:results:create", "production:results:update", "production:results:delete"}
    assert env.result(po)["entries"][0]["actions"] == ["correct"]
    other = env.planned()
    view = env.result(other)
    assert view["actions"] == [] and view["editable"] is True  # editable status, but this user may not write


# ---- 15-16: model shape and legacy data ------------------------------------------------------------

def test_15_result_model_has_no_work_center_shift_run_or_workforce_fields():
    columns = set(ProductionResultEntry.__table__.columns.keys())
    assert not {c for c in columns if any(word in c for word in ("work_center", "shift", "roster", "run", "workforce", "member", "status"))}
    assert {"production_order_id", "production_order_item_id", "disposition", "quantity", "unit", "secondary_quantity", "secondary_unit",
            "counts_as_loss", "reason_code", "notes", "entry_type", "corrects_entry_id", "correction_reason", "created_by_user_id"} <= columns


def test_16_the_legacy_output_design_is_gone(env):
    import app.production.infrastructure.models as models
    from app.core.db import Base
    from app.foundation.domain.permission_catalog import PRODUCTION_PERMISSIONS
    assert not hasattr(models, "ProductionOutput") and "production_outputs" not in Base.metadata.tables
    assert not any("production_output" in c for t in ("quality_checks", "quality_defects", "quality_rejections") for c in Base.metadata.tables[t].columns.keys())
    assert not [p for p in PRODUCTION_PERMISSIONS if "production_outputs" in str(p)]
    for method, path in (("get", ""), ("post", ""), ("get", f"/{uuid4()}")):
        assert getattr(env.client, method)(f"{ROOT}/production-outputs{path}").status_code in (404, 405)
    # Closing still needs the final result; nothing else counts.
    po = env.planned()
    assert env.result(po)["entries"] == [] and code(env.transition(po["id"], "close")) == "RESULT_REQUIRED_TO_CLOSE"


# ---- results list ------------------------------------------------------------------------------

def test_results_list_shows_completed_and_closed_orders_with_totals(env):
    completed = env.planned(quantity="400")
    env.added(completed, "customer_good", "300")
    env.added(completed, "scrap", "20")
    closed = env.planned()
    env.close(closed, zero_output=True, reason="nothing")
    env.planned(to="in_progress")  # not listed: the result is not recorded yet
    foreign = other_org_demand(env.db); foreign.order.status = "completed"; env.db.commit()
    rows = env.client.get(f"{ROOT}/production-results").json()
    assert {r["id"]: r["status"] for r in rows} == {completed["id"]: "completed", closed["id"]: "closed"}
    row = next(r for r in rows if r["id"] == completed["id"])
    (total,) = row["totals"]
    assert (row["entry_count"], row["ready_to_close"], total["unit"]) == (2, True, "kg")
    assert (Decimal(total["customer_good"]), Decimal(total["loss_total"]), Decimal(total["fulfillment_pct"])) == (300, 20, Decimal("75.00"))
    assert [r["id"] for r in env.client.get(f"{ROOT}/production-results?status=closed").json()] == [closed["id"]]
    assert env.client.get(f"{ROOT}/production-results?status=draft").status_code == 422
    env.ctx.auth_user.permissions = set(PERMISSIONS) - {"production:results:read"}
    assert env.client.get(f"{ROOT}/production-results").status_code == 403


# ---- review fixes: records survive a work-center delete ---------------------------------------

def test_work_center_delete_refused_when_orders_have_a_final_result(env):
    po = env.bare("kg")
    env.added(po, "stock_good", "5")
    env.ctx.auth_user.permissions = set(PERMISSIONS) | {"production:work_centers:delete"}
    r = env.client.delete(f"{ROOT}/work-centers/{env.center.id}")
    assert r.status_code == 409 and "final result" in r.json()["detail"]
    env.db.expire_all()
    assert env.db.get(ProductionOrder, UUID(po["id"])) is not None and len(env.rows(po)) == 1


def test_work_center_delete_summary_counts_results(env):
    po = env.bare("kg")
    env.added(po, "stock_good", "5")
    env.ctx.auth_user.permissions = set(PERMISSIONS) | {"production:work_centers:read"}
    summary = env.client.get(f"{ROOT}/work-centers/{env.center.id}/delete-summary").json()
    assert summary["production_results_count"] == 1 and "production_outputs_count" not in summary
