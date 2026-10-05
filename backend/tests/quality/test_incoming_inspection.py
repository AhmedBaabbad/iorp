"""QUAL-INC-001 / PROC-002: incoming inspection — received lots awaiting quality, an inspection per lot against its
material's specification, the lot decision (released or not, with an NCR about the supplier), the lot's status on the
goods receipt, and the supplier's evaluation."""
from decimal import Decimal

from app.procurement.domain import rules as PRR
from tests.procurement.test_procurement import ROOT, proc  # noqa: F401 - the shared fixture

QUALITY = "/api/v1/quality"


def received(proc, quantity="20000", **material):
    s, m = proc.supplier(), proc.material(**material)
    proc.client.post(f"{ROOT}/suppliers/{s['id']}/status", json=dict(status="approved"))
    r = proc.receipt(s, m, lines=[dict(material_id=m["id"], supplier_lot="SUP-7781", quantity=quantity, unit="kg"),
                                  dict(description="Pallets (returnable)", quantity="20", unit="pallet")])
    proc.client.post(f"{ROOT}/receipts/{r['id']}/receive")
    return s, m, proc.client.get(f"{ROOT}/receipts/{r['id']}").json()


def code(r):
    return r.json()["detail"]["code"]


def test_received_lots_wait_for_quality_and_show_their_status_on_the_receipt(proc):
    _s, _m, r = received(proc)
    first, pallets = r["lines"]
    assert r["line_quality"][first["id"]]["status"] == "awaiting" and r["line_quality"][pallets["id"]]["status"] == "not_required"
    assert r["lots_pending"] == 1
    [waiting] = proc.client.get(f"{QUALITY}/incoming/awaiting").json()
    assert waiting["receipt_no"] == r["receipt_no"] and [line["line_id"] for line in waiting["lines"]] == [first["id"]]
    check = proc.client.post(f"{QUALITY}/incoming/lines/{first['id']}/inspection").json()
    assert check["check_type"] == "incoming_inspection" and check["qty_inspected"] == "20000.000" and check["unit"] == "kg"
    assert check["incoming_source"]["receipt_no"] == r["receipt_no"] and check["incoming_source"]["supplier_lot"] == "SUP-7781"
    assert "lot_decision" in check["actions"] and "close" not in check["actions"]
    assert code(proc.client.post(f"{QUALITY}/incoming/lines/{first['id']}/inspection")) == "LOT_ALREADY_INSPECTED"
    assert code(proc.client.post(f"{QUALITY}/incoming/lines/{pallets['id']}/inspection")) == "LOT_NOT_AWAITING_INSPECTION"
    closing = proc.client.post(f"{QUALITY}/quality-checks/{check['id']}/close", json=dict(result="accepted", qty_inspected="20000", qty_accepted="20000", qty_rejected="0"))
    assert code(closing) == "INCOMING_INSPECTION_NEEDS_DECISION"
    assert proc.client.get(f"{ROOT}/receipts/{r['id']}").json()["line_quality"][first["id"]]["status"] == "inspecting"
    released = proc.client.post(f"{QUALITY}/quality-checks/{check['id']}/lot-decision", json=dict(released="20000")).json()
    assert released["status"] == "closed" and released["result"] == "accepted"
    after = proc.client.get(f"{ROOT}/receipts/{r['id']}").json()
    assert after["line_quality"][first["id"]]["status"] == "released" and after["lots_pending"] == 0
    assert proc.client.get(f"{QUALITY}/incoming/awaiting").json() == []
    assert proc.client.get("/api/v1/quality/non-conformance-reports").json() == []  # nothing to report


def test_a_lot_not_released_opens_a_non_conformance_report_about_the_supplier(proc):
    s, _m, r = received(proc)
    line = r["lines"][0]
    check = proc.client.post(f"{QUALITY}/incoming/lines/{line['id']}/inspection").json()
    decide = lambda **parts: proc.client.post(f"{QUALITY}/quality-checks/{check['id']}/lot-decision", json=parts)  # noqa: E731
    r2 = decide(released="15000", scrap="1000")
    assert r2.status_code == 400 and code(r2) == "LOT_SPLIT_MISMATCH" and r2.json()["detail"]["total"] == "16000"
    assert code(decide(released="15000", use_as_is="5000")) == "CONCESSION_DETAILS_REQUIRED"
    done = decide(released="15000", return_to_supplier="4000", scrap="1000", notes="Moisture 0.12 % on 5 t").json()
    assert done["result"] == "rejected" and done["qty_accepted"] == "15000.000" and done["qty_rejected"] == "5000.000"
    [ncr] = proc.client.get("/api/v1/quality/non-conformance-reports").json()
    full = proc.client.get(f"/api/v1/quality/non-conformance-reports/{ncr['id']}").json()
    assert full["source_type"] == "incoming_material" and full["supplier_id"] == s["id"] and full["supplier_name"] == "Gulf Polymers"
    assert full["quality_check_id"] == check["id"] and full["reference_code"] == f"{r['receipt_no']} / SUP-7781"
    assert [(i["disposition"], i["quantity_affected"]) for i in full["items"]] == [("return_to_supplier", "4000.000"), ("scrap", "1000.000")]
    assert proc.client.get(f"{ROOT}/receipts/{r['id']}").json()["line_quality"][line["id"]]["status"] == "partly_released"
    supplier = proc.client.get(f"{ROOT}/suppliers/{s['id']}").json()
    assert supplier["ncr_count"] == 1 and supplier["evaluation"]["lots_inspected"] == 1 and supplier["evaluation"]["lots_rejected"] == 1


def test_the_material_specification_becomes_the_plan(proc):
    params = {p["code"]: p["id"] for p in proc.client.post(f"{QUALITY}/quality-test-parameters/standard").json()}
    _s, _m, r = received(proc, spec_product_type="pp_resin")
    spec = proc.client.post(f"{QUALITY}/quality-specifications", json=dict(code="ROF-RM-PP-001", title="PP resin H030", product_type="pp_resin",
                                                                          lines=[dict(parameter_id=params["COLOR"], requirement="Natural, no black specks")]))
    assert spec.status_code == 201, spec.text
    assert proc.client.post(f"{QUALITY}/quality-specifications/{spec.json()['id']}/activate").status_code == 200
    check = proc.client.post(f"{QUALITY}/incoming/lines/{r['lines'][0]['id']}/inspection").json()
    assert check["specification_code"] == "ROF-RM-PP-001" and [m["parameter_code"] for m in check["measurements"]] == ["COLOR"]
    r2 = proc.client.post(f"{QUALITY}/quality-checks/{check['id']}/lot-decision", json=dict(released="20000"))
    assert r2.status_code == 409  # the plan must be measured before the decision


def test_supplier_evaluation_from_lots_ncrs_and_their_cost():
    good = PRR.evaluate(10, 10, [], Decimal("0"))
    assert (good["score"], good["grade"], good["suggested_status"]) == (Decimal("100.0"), "A", "approved")
    mixed = PRR.evaluate(10, 8, ["major"], Decimal("3500"))  # 80 − 5 − 3
    assert (mixed["score"], mixed["grade"], mixed["suggested_status"], mixed["cost_penalty"]) == (Decimal("72.0"), "C", "conditional", 3)
    bad = PRR.evaluate(4, 1, ["critical", "critical", "critical", "critical"], Decimal("90000"))  # 25 − 30 (cap) − 20 (cap)
    assert (bad["score"], bad["grade"], bad["suggested_status"], bad["ncr_penalty"]) == (Decimal("0"), "D", "blocked", 30)
    none = PRR.evaluate(0, 0, ["minor"], Decimal("0"))
    assert none["score"] is None and none["grade"] is None and none["ncr_count"] == 1


def test_the_evaluation_endpoint(proc):
    s, _m, r = received(proc)
    check = proc.client.post(f"{QUALITY}/incoming/lines/{r['lines'][0]['id']}/inspection").json()
    proc.client.post(f"{QUALITY}/quality-checks/{check['id']}/lot-decision", json=dict(released="20000"))
    ev = proc.client.get(f"{ROOT}/suppliers/{s['id']}/evaluation", params=dict(months=6)).json()
    assert ev["months"] == 6 and ev["lots_inspected"] == 1 and ev["score"] == "100.0" and ev["grade"] == "A"
    listed = proc.client.get(f"{ROOT}/suppliers").json()[0]
    assert listed["evaluation"]["grade"] == "A"
