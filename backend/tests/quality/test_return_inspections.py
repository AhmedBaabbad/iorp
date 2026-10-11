"""QUAL-RET-001 / SHIP-005: returned goods — back to stock or to quality on receipt, an inspection per returned line,
the split decision (stock, second grade, rework, back to the process, scrap «هالك», hold), the NCR, containment by
production order, and the production close gate left alone."""
from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.core.db import Base
from app.core.tenancy import TenantContext
from app.quality.application.rejection_service import close_blockers
from app.quality.domain import permissions as Q
from app.quality.infrastructure.models import NonConformanceReport
from tests.shipping.test_shipments import ROOT, go, ship  # noqa: F401 - the shared fixture

RETURNS = "/api/v1/shipping/returns"
QUALITY = "/api/v1/quality"


@pytest.fixture
def env(ship):
    ship.ctx.auth_user.permissions.update(Q.ALL)
    ship.ctx.tenant = TenantContext(ship.user.id, ship.org.id, permissions=frozenset(ship.ctx.auth_user.permissions))
    order_id = uuid4()
    ship.db.execute(Base.metadata.tables["production_orders"].insert().values(
        id=order_id, organization_id=ship.org.id, production_order_number="PO-2026-000014", work_center_id=uuid4(), product_type="PP Strap",
        planned_quantity=500, unit="roll", priority="normal", status="completed", planned_start_date=date(2026, 10, 1),
        planned_end_date=date(2026, 10, 2), created_by_user_id=ship.user.id, status_version=1))
    ship.db.commit()
    ship.order_id = order_id
    return ship


def delivered(env, **over):
    s = env.create(lines=[dict(description="PP Strap 5 mm", width_mm="5", thickness_mm="0.35", quantity="100", unit="roll", weight="1000",
                               production_order_id=str(env.order_id))], driver_name="Saleh", vehicle_plate="ABC 1", **over)
    go(env, s, "ready"); go(env, s, "dispatch")
    return go(env, s, "deliver", received_by_name="Khalid").json()


def returned(env, reason="quality_defect", quantity="20", received="18", **receive):
    s = delivered(env)
    ret = env.client.post(RETURNS, json=dict(shipment_id=s["id"], reason=reason, details="Crushed cores on 20 rolls",
                                             lines=[dict(shipment_line_id=s["lines"][0]["id"], quantity=quantity)])).json()
    env.client.post(f"{RETURNS}/{ret['id']}/approve", json={})
    got = env.client.post(f"{RETURNS}/{ret['id']}/receive", json=dict(lines=[dict(return_line_id=ret["lines"][0]["id"], received_quantity=received)],
                                                                       **receive))
    assert got.status_code == 200, got.text
    return s, got.json()


def code(r):
    return r.json()["detail"]["code"]


def test_goods_not_in_question_go_back_to_stock_unless_the_warehouse_sends_them(env):
    _s, ret = returned(env, reason="excess_quantity")
    assert ret["quality_required"] is False and ret["quality_status"] == "not_required" and ret["quality"]["expected"] is False
    assert env.client.get(f"{QUALITY}/returns/awaiting").json() == []
    _s, sent = returned(env, reason="customer_cancelled", send_to_quality=True)
    assert sent["quality_required"] is True and sent["quality_status"] == "awaiting"
    assert [r["return_no"] for r in env.client.get(f"{QUALITY}/returns/awaiting").json()] == [sent["return_no"]]


def test_a_returned_line_is_inspected_and_decided_in_parts(env):
    s, ret = returned(env)
    assert ret["quality_required"] and ret["quality_status"] == "awaiting"
    [waiting] = env.client.get(f"{QUALITY}/returns/awaiting").json()
    line = waiting["lines"][0]
    assert waiting["shipment_no"] == s["shipment_no"] and line["received_quantity"] == "18.000" and line["production_order_no"] == "PO-2026-000014"
    check = env.client.post(f"{QUALITY}/returns/lines/{line['line_id']}/inspection").json()
    assert check["check_type"] == "issue_triggered" and check["qty_inspected"] == "18.000" and check["unit"] == "roll"
    assert check["production_order_id"] == str(env.order_id) and check["lot_values"] == {"width_mm": "5", "thickness_mm": "0.35"}
    assert check["return_source"]["return_no"] == ret["return_no"] and check["return_source"]["shipment_no"] == s["shipment_no"]
    assert "return_decision" in check["actions"] and "close" not in check["actions"]
    r = env.client.post(f"{QUALITY}/returns/lines/{line['line_id']}/inspection")
    assert r.status_code == 409 and code(r) == "RETURN_LINE_ALREADY_INSPECTED"
    r = env.client.post(f"{QUALITY}/quality-checks/{check['id']}/close", json=dict(result="accepted", qty_inspected="18", qty_accepted="18", qty_rejected="0"))
    assert r.status_code == 409 and code(r) == "RETURN_INSPECTION_NEEDS_DECISION"
    assert env.client.get(f"{RETURNS}/{ret['id']}").json()["quality_status"] == "inspecting"
    decide = lambda **parts: env.client.post(f"{QUALITY}/quality-checks/{check['id']}/return-decision", json=parts)  # noqa: E731
    r = decide(to_stock="8", scrap="5")
    assert r.status_code == 400 and code(r) == "RETURN_SPLIT_MISMATCH" and r.json()["detail"]["total"] == "13"
    r = decide(to_stock="8", use_as_is="10")
    assert r.status_code == 400 and code(r) == "CONCESSION_DETAILS_REQUIRED"
    done = decide(to_stock="8", rework="5", scrap="5", notes="Cores crushed in loading", open_ncr=True).json()
    assert done["status"] == "closed" and done["result"] == "rejected" and done["qty_accepted"] == "8.000" and done["qty_rejected"] == "10.000"
    assert sorted((x["disposition"], x["quantity_rejected"], x["disposition_status"]) for x in done["rejections"]) == [
        ("rework", "5.000", "decided"), ("scrap", "5.000", "decided")]
    ncr = env.db.scalar(select(NonConformanceReport).where(NonConformanceReport.quality_check_id == UUID(done["id"])))
    assert ncr.source_type.value == "customer_return" and ncr.reference_code == ret["return_no"] and ncr.status == "open"
    assert env.client.get(f"{QUALITY}/returns/awaiting").json() == []  # every line is decided
    back = env.client.get(f"{RETURNS}/{ret['id']}").json()
    assert back["quality_status"] == "decided" and back["quality"]["inspections"][0]["inspection_code"] == done["inspection_code"]
    assert {d["disposition"] for d in back["quality"]["decisions"]} == {"rework", "scrap"}
    rejections = env.client.get(f"{QUALITY}/quality-rejections", params=dict(quality_check_id=done["id"])).json()["items"]
    assert {x["return_no"] for x in rejections} == {ret["return_no"]}
    for x in rejections:
        assert env.client.post(f"{QUALITY}/quality-rejections/{x['id']}/execute", json={}).status_code == 200
    assert env.client.get(f"{RETURNS}/{ret['id']}").json()["quality_status"] == "done"


def test_second_grade_needs_the_concession_and_returned_goods_never_block_the_production_order(env):
    _s, ret = returned(env, reason="spec_mismatch", quantity="10", received="10")
    line = env.client.get(f"{QUALITY}/returns/awaiting").json()[0]["lines"][0]
    check = env.client.post(f"{QUALITY}/returns/lines/{line['line_id']}/inspection").json()
    assert close_blockers(env.db, env.org.id, env.order_id) == []  # an open return inspection
    ok = env.client.post(f"{QUALITY}/quality-checks/{check['id']}/return-decision",
                         json=dict(use_as_is="6", hold="4", notes="Thickness 0.33 mm: sold as second grade", concession_approved_by="Sales manager")).json()
    assert ok["result"] == "rejected" and {x["disposition"] for x in ok["rejections"]} == {"use_as_is", "hold"}
    assert close_blockers(env.db, env.org.id, env.order_id) == []  # a held part of returned goods


def test_containment_lists_every_note_that_carried_the_production_order(env):
    first, ret = returned(env)
    other = delivered(env)
    ready = env.create(lines=[dict(description="PP Strap 5 mm", quantity="30", unit="roll", production_order_id=str(env.order_id))],
                       driver_name="Saleh", vehicle_plate="ABC 1")
    go(env, ready, "ready")
    env.create(lines=[dict(description="draft", quantity="1", unit="roll", production_order_id=str(env.order_id))])  # a draft has not left
    line = env.client.get(f"{QUALITY}/returns/awaiting").json()[0]["lines"][0]
    check = env.client.post(f"{QUALITY}/returns/lines/{line['line_id']}/inspection").json()
    batch = env.client.get(f"{QUALITY}/quality-checks/{check['id']}/batch-shipments").json()
    assert {b["shipment_no"]: b["status"] for b in batch} == {first["shipment_no"]: "delivered", other["shipment_no"]: "delivered",
                                                              ready["shipment_no"]: "ready"}


def test_return_decisions_need_close_and_decide(env):
    _s, _ret = returned(env)
    line = env.client.get(f"{QUALITY}/returns/awaiting").json()[0]["lines"][0]
    check = env.client.post(f"{QUALITY}/returns/lines/{line['line_id']}/inspection").json()
    env.ctx.auth_user.permissions.discard(Q.REJECTIONS_DECIDE)
    env.ctx.tenant = TenantContext(env.user.id, env.org.id, permissions=frozenset(env.ctx.auth_user.permissions))
    assert "return_decision" not in env.client.get(f"{QUALITY}/quality-checks/{check['id']}").json()["actions"]
    assert env.client.post(f"{QUALITY}/quality-checks/{check['id']}/return-decision", json=dict(to_stock="18")).status_code == 403
    env.ctx.auth_user.permissions.discard(Q.CHECKS_CREATE)
    assert env.client.post(f"{QUALITY}/returns/lines/{uuid4()}/inspection").status_code == 403

