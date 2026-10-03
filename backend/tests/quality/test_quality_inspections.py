"""QUAL-001: quality checks and rejections aligned with production orders, permissions and the close gate."""
import re
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import select

from app.main import app
from app.quality.domain import permissions as Q
from app.quality.infrastructure.models import QualityStatusHistory
from tests.production.test_order_results import PERMISSIONS as PRODUCTION, env as result_env  # noqa: F401

CHECKS = "/api/v1/quality/quality-checks"
REJECTIONS = "/api/v1/quality/quality-rejections"
NOW = "2026-10-03T08:00:00+00:00"


@pytest.fixture
def q(result_env):
    e = result_env
    e.ctx.auth_user.permissions = set(PRODUCTION) | set(Q.ALL)

    def check(po=None, line=0, check_type="in_process_inspection", **extra):
        body = dict(check_type=check_type, check_datetime=NOW, **extra)
        if po:
            body["production_order_id"] = po["id"]
            if po.get("lines"):
                body["production_order_item_id"] = po["lines"][line]["id"]
        return e.client.post(CHECKS, json=body)

    def opened(*args, **kwargs):
        r = check(*args, **kwargs)
        assert r.status_code == 201, r.text
        return r.json()

    def close(c, inspected="10", accepted="10", rejected="0", result="accepted", **extra):
        return e.client.post(f"{CHECKS}/{c['id']}/close", json=dict(result=result, qty_inspected=inspected, qty_accepted=accepted,
                                                                     qty_rejected=rejected, **extra))

    def rejections(po):
        return e.client.get(REJECTIONS, params=dict(production_order_id=po["id"])).json()

    e.check, e.opened, e.close_check, e.rejections = check, opened, close, rejections
    return e


def code(r):
    return r.json()["detail"]["code"]


# ── creation on a production order ────────────────────────────────────────────────────────────

def test_check_needs_a_running_held_or_completed_order(q):
    assert code(q.check(check_type="in_process_inspection")) == "PRODUCTION_ORDER_REQUIRED"
    for status in ("draft", "released", "closed", "cancelled"):
        r = q.check(q.bare("kg", status=status))
        assert r.status_code == 409 and code(r) == "ORDER_NOT_INSPECTABLE", status
    for status in ("in_progress", "on_hold", "completed"):
        assert q.check(q.bare("kg", status=status)).status_code == 201, status
    assert q.check(dict(id=str(uuid4()))).status_code == 404
    assert q.check(check_type="general").status_code == 201  # a general inspection needs no order


def test_check_takes_the_line_unit_and_is_numbered(q):
    po = q.bare("kg", "roll", status="in_progress")
    first, second = q.opened(po, line=1), q.opened(po)
    assert first["unit"] == "roll" and second["unit"] == "kg" and first["item_line_no"] == 2
    assert first["order_number"].startswith("PO-") and first["status"] == "open" and first["result"] is None
    year = first["inspection_code"][3:7]
    assert first["inspection_code"] == f"QI-{year}-0001" and second["inspection_code"] == f"QI-{year}-0002"
    other = q.bare("kg", status="in_progress")
    assert code(q.check(dict(id=other["id"], lines=[dict(id=po["lines"][0]["id"])]))) == "ORDER_ITEM_NOT_FOUND"


# ── lifecycle ─────────────────────────────────────────────────────────────────────────────────

def test_lifecycle_start_close_and_finality(q):
    c = q.opened(q.bare("kg", status="in_progress"))
    assert c["actions"] == ["edit", "start", "close", "cancel"]
    started = q.client.post(f"{CHECKS}/{c['id']}/start").json()
    assert started["status"] == "under_inspection" and started["started_at"] and started["actions"] == ["edit", "close", "cancel"]
    assert code(q.client.post(f"{CHECKS}/{c['id']}/start")) == "CHECK_NOT_OPEN"
    closed = q.close_check(c, inspected="12.5", accepted="12.5").json()
    assert closed["status"] == "closed" and closed["result"] == "accepted" and Decimal(closed["qty_inspected"]) == Decimal("12.5")
    assert closed["actions"] == [] and closed["closed_by_name"] == q.user.full_name
    assert code(q.client.patch(f"{CHECKS}/{c['id']}", json=dict(notes="late"))) == "CHECK_IS_FINAL"
    assert code(q.close_check(c)) == "CHECK_IS_FINAL"
    assert [h["action"] for h in closed["history"]] == ["create", "start", "close"]


def test_cancel_needs_a_reason_and_is_final(q):
    c = q.opened(q.bare("kg", status="in_progress"))
    assert q.client.post(f"{CHECKS}/{c['id']}/cancel", json=dict(reason="")).status_code == 422
    cancelled = q.client.post(f"{CHECKS}/{c['id']}/cancel", json=dict(reason="Lot moved to another line")).json()
    assert cancelled["status"] == "cancelled" and cancelled["cancel_reason"] == "Lot moved to another line" and cancelled["result"] is None
    assert code(q.client.post(f"{CHECKS}/{c['id']}/start")) == "CHECK_NOT_OPEN"


@pytest.mark.parametrize("inspected,accepted,rejected,result,expected", [
    ("10", "8", "1", "rejected", "QUANTITY_BALANCE"),
    ("10", "9", "1", "accepted", "ACCEPTED_WITH_REJECTED_QUANTITY"),
    ("10", "10", "0", "rejected", "REJECTED_WITHOUT_QUANTITY"),
])
def test_close_quantities_and_result_must_agree(q, inspected, accepted, rejected, result, expected):
    c = q.opened(q.bare("kg", status="in_progress"))
    r = q.close_check(c, inspected=inspected, accepted=accepted, rejected=rejected, result=result)
    assert r.status_code == 400 and code(r) == expected


# ── rejections ────────────────────────────────────────────────────────────────────────────────

def test_closing_with_rejected_quantity_opens_a_pending_rejection(q):
    po = q.bare("roll", status="in_progress")
    c = q.opened(po)
    closed = q.close_check(c, inspected="100", accepted="90", rejected="10", result="rejected", notes="Edges torn", rejection_reason="surface_failure").json()
    [summary] = closed["rejections"]
    assert summary["disposition_status"] == "pending" and Decimal(summary["quantity_rejected"]) == 10 and summary["unit"] == "roll"
    [rejection] = q.rejections(po)
    assert rejection["rejection_code"].startswith("QR-") and rejection["inspection_code"] == c["inspection_code"]
    assert rejection["rejection_reason"] == "surface_failure" and rejection["unresolved"] and rejection["actions"] == ["edit", "decide"]
    detail = q.client.get(f"{REJECTIONS}/{rejection['id']}").json()
    assert detail["rejection_notes"] == "Edges torn" and detail["production_order_item_id"] == po["lines"][0]["id"]


def test_decision_hold_concession_and_execution(q):
    po = q.bare("kg", status="in_progress")
    q.close_check(q.opened(po), inspected="50", accepted="45", rejected="5", result="rejected")
    rid = q.rejections(po)[0]["id"]
    held = q.client.post(f"{REJECTIONS}/{rid}/decide", json=dict(disposition="hold", decision_notes="Await lab")).json()
    assert held["disposition_status"] == "decided" and held["unresolved"] and held["actions"] == ["decide"]
    assert code(q.client.post(f"{REJECTIONS}/{rid}/execute", json={})) == "HOLD_IS_NOT_FINAL"
    r = q.client.post(f"{REJECTIONS}/{rid}/decide", json=dict(disposition="use_as_is"))
    assert r.status_code == 400 and code(r) == "CONCESSION_DETAILS_REQUIRED"
    accepted = q.client.post(f"{REJECTIONS}/{rid}/decide", json=dict(disposition="use_as_is", concession_approved_by="Customer QA",
                                                                     decision_notes="Colour slightly light, accepted by the customer")).json()
    assert not accepted["unresolved"] and accepted["concession_approved_by"] == "Customer QA" and accepted["actions"] == ["decide", "execute"]
    done = q.client.post(f"{REJECTIONS}/{rid}/execute", json=dict(execution_notes="Released")).json()
    assert done["disposition_status"] == "executed" and done["executed_by_name"] == q.user.full_name and done["actions"] == []
    assert code(q.client.post(f"{REJECTIONS}/{rid}/decide", json=dict(disposition="scrap"))) == "REJECTION_IS_FINAL"
    assert code(q.client.patch(f"{REJECTIONS}/{rid}", json=dict(rejection_notes="x"))) == "REJECTION_ALREADY_DECIDED"
    assert [h["action"] for h in done["history"]] == ["create", "decide", "decide", "execute"]


def test_manual_rejections_stay_within_the_check_and_need_an_order(q):
    po = q.bare("kg", status="in_progress")
    c = q.close_check(q.opened(po), inspected="20", accepted="12", rejected="8", result="rejected").json()
    body = dict(rejection_date="2026-10-03", rejection_reason="out_of_spec", rejection_notes="Second batch of the same lot")
    r = q.client.post(REJECTIONS, json=dict(body, quality_check_id=c["id"], quantity_rejected="1"))
    assert code(r) == "QUANTITY_EXCEEDS_CHECK" and r.json()["detail"]["available"] == "0.000"  # 8 already opened
    assert code(q.client.post(REJECTIONS, json=dict(body, quantity_rejected="3"))) == "PRODUCTION_ORDER_REQUIRED"
    manual = q.client.post(REJECTIONS, json=dict(body, production_order_id=po["id"], quantity_rejected="3"))
    assert manual.status_code == 201 and manual.json()["unit"] == "kg" and manual.json()["quality_check_id"] is None


# ── production close gate ─────────────────────────────────────────────────────────────────────

def test_order_cannot_close_while_quality_is_open(q):
    po = q.bare("kg", status="completed")
    q.added(po, "stock_good", "10")
    c = q.opened(po, check_type="finished_product_inspection")
    r = q.transition(po["id"], "close")
    assert r.status_code == 409 and code(r) == "CLOSE_BLOCKED"
    assert r.json()["detail"]["blockers"] == [dict(code="QUALITY_CHECKS_OPEN", count=1)]
    q.close_check(c, inspected="10", accepted="9", rejected="1", result="rejected")
    assert r.json() and q.transition(po["id"], "close").json()["detail"]["blockers"] == [dict(code="QUALITY_REJECTIONS_UNRESOLVED", count=1)]
    rid = q.rejections(po)[0]["id"]
    q.client.post(f"{REJECTIONS}/{rid}/decide", json=dict(disposition="hold"))
    assert code(q.transition(po["id"], "close")) == "CLOSE_BLOCKED"  # on hold is not a decision
    q.client.post(f"{REJECTIONS}/{rid}/decide", json=dict(disposition="scrap"))
    assert q.transition(po["id"], "close").status_code == 200
    assert code(q.check(po)) == "ORDER_NOT_INSPECTABLE"  # closing the order locks its quality


# ── permissions and isolation ─────────────────────────────────────────────────────────────────

def test_each_action_needs_its_own_permission(q):
    po = q.bare("kg", status="in_progress")
    c = q.opened(po)
    q.ctx.auth_user.permissions = set(PRODUCTION) | {Q.CHECKS_READ, Q.CHECKS_START}
    assert q.client.get(f"{CHECKS}/{c['id']}").json()["actions"] == ["start"]
    assert q.close_check(c).status_code == 403 and q.check(po).status_code == 403
    assert q.client.post(f"{CHECKS}/{c['id']}/cancel", json=dict(reason="x")).status_code == 403
    assert q.client.get(REJECTIONS).status_code == 403
    q.ctx.auth_user.permissions = set(PRODUCTION)
    assert q.client.get(CHECKS).status_code == 403 and q.client.get("/api/v1/quality/non-conformance-reports").status_code == 403


def test_every_quality_route_declares_a_permission():
    def policies(dependant):
        for dep in dependant.dependencies:
            if getattr(dep.call, "permission_policy", None):
                yield dep.call.permission_policy
            yield from policies(dep)
    routes = [r for r in app.routes if isinstance(r, APIRoute) and r.path.startswith("/api/v1/quality")]
    assert len(routes) >= 25
    assert [r.path for r in routes if not list(policies(r.dependant))] == []


def test_quality_permission_catalog_is_explicit():
    from app.foundation.domain.permission_catalog import ALL_TENANT_PERMISSIONS
    from app.foundation.domain.system_roles import SYSTEM_ROLE_BY_CODE
    codes = {p.code for p in ALL_TENANT_PERMISSIONS if p.code.startswith("quality:")}
    assert codes == set(Q.ALL) and not [c for c in codes if c.endswith(":write")]
    assert set(Q.ALL) <= set(SYSTEM_ROLE_BY_CODE["quality_manager"]["permissions"])
    assert not [p for r in SYSTEM_ROLE_BY_CODE.values() for p in r["permissions"] if str(p).startswith("quality:") and "*" in str(p)]


def test_other_tenants_orders_and_checks_are_invisible(q):
    from tests.test_production_allocation_lifecycle import other_org_demand
    foreign = other_org_demand(q.db)
    from app.production.infrastructure.models import ProductionOrder
    order = q.db.scalar(select(ProductionOrder).where(ProductionOrder.organization_id == foreign.org.id))
    if order is not None:
        assert q.check(dict(id=str(order.id))).status_code == 404
    assert q.client.get(f"{CHECKS}/{uuid4()}").status_code == 404
    assert q.client.get(CHECKS, params=dict(production_order_id=str(uuid4()))).json() == []


def test_lookups_list_only_inspectable_orders_with_lines(q):
    running, draft = q.bare("kg", "roll", status="in_progress"), q.bare("kg", status="draft")
    orders = {o["id"]: o for o in q.client.get(f"{CHECKS}/lookups/orders").json()}
    assert running["id"] in orders and draft["id"] not in orders
    assert [line["unit"] for line in orders[running["id"]]["items"]] == ["kg", "roll"]


def test_history_rows_belong_to_the_organization(q):
    c = q.opened(q.bare("kg", status="in_progress"))
    rows = q.db.scalars(select(QualityStatusHistory)).all()
    assert rows and all(r.organization_id == q.org.id for r in rows)
    assert re.match(r"^QI-\d{4}-\d{4}$", c["inspection_code"])
