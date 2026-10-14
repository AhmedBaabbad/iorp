"""SHIP-004: delivery outcomes and returns — partial delivery, failed delivery and rescheduling under the same number,
closing as not delivered, customer returns against a delivery note, weights, batches, proof of delivery, documents."""
from datetime import date
from uuid import uuid4

import pytest

from app.core.config import settings as app_settings
from app.core.db import Base
from app.shipping.domain import permissions as S
from tests.shipping.test_shipments import ROOT, code, go, ship  # noqa: F401 - the shared fixture

RETURNS = "/api/v1/shipping/returns"
from tests.file_samples import pdf, png

PNG = png()


def two_lines(env, **over):
    return env.create(lines=[dict(description="PP Strap 5 mm", width_mm="5", thickness_mm="0.35", quantity="100", unit="roll", weight="1000"),
                             dict(description="PP Strap 15 mm", width_mm="15", thickness_mm="0.85", quantity="40", unit="roll", weight="0.4",
                                  weight_unit="ton")], driver_affiliation="external", driver_name="Saleh", vehicle_plate="ABC 1234", **over)


def on_the_road(env, **over):
    s = two_lines(env, **over)
    assert go(env, s, "ready").status_code == 200
    assert go(env, s, "dispatch").status_code == 200
    return s


def returns_of(env, s):
    return env.client.get(RETURNS, params=dict(shipment_id=s["id"])).json()


def receive(env, ret, **payload):
    return env.client.post(f"{RETURNS}/{ret['id']}/receive", json=payload or {})


# ── case 1: not received at the door ────────────────────────────────────────────────────────────

def test_a_partial_delivery_sends_the_refused_part_back_under_a_return(ship):
    s = on_the_road(ship)
    first, second = s["lines"]
    r = go(ship, s, "deliver", received_by_name="Khalid", lines=[dict(line_id=first["id"], delivered_quantity="70")])
    assert r.status_code == 400 and code(r) == "REFUSAL_REASON_REQUIRED"
    r = go(ship, s, "deliver", received_by_name="Khalid", lines=[dict(line_id=first["id"], delivered_quantity="101")], refusal_reason="quality_issue")
    assert r.status_code == 400 and code(r) == "DELIVERED_QUANTITY_INVALID"
    r = go(ship, s, "deliver", received_by_name="Khalid", refusal_reason="customer_refused",
           lines=[dict(line_id=first["id"], delivered_quantity="0"), dict(line_id=second["id"], delivered_quantity="0")])
    assert r.status_code == 400 and code(r) == "NOTHING_DELIVERED"
    done = go(ship, s, "deliver", received_by_name="Khalid", lines=[dict(line_id=first["id"], delivered_quantity="70")],
              refusal_reason="quality_issue", refusal_details="30 rolls with crushed cores").json()
    assert done["status"] == "partially_delivered"
    assert [line["delivered_quantity"] for line in done["lines"]] == ["70.000", "40.000"]
    [ret] = returns_of(ship, s)
    assert ret["return_no"].startswith("RT-2026-") and ret["kind"] == "delivery" and ret["status"] == "approved"
    assert ret["reason"] == "quality_issue" and ret["responsibility"] == "factory" and ret["shipment_no"] == s["shipment_no"]
    assert ret["quantities"] == [{"unit": "roll", "quantity": "30.000"}] and ret["weight_kg"] == "300.000"  # in proportion
    assert ret["actions"] == ["receive"]
    assert ship.client.post(f"{RETURNS}/{ret['id']}/cancel", json=dict(reason="x")).json()["detail"]["code"] == "DELIVERY_RETURN_NOT_CANCELLABLE"
    got = receive(ship, ret, notes="Back on pallet 4").json()
    assert got["status"] == "received" and got["lines"][0]["received_quantity"] == "30.000" and got["received_by_name"] == "Test User"
    detail = ship.client.get(f"{ROOT}/{s['id']}").json()
    assert {"return_opened", "return_received", "partially_delivered"} <= {h["action"] for h in detail["history"]}


def test_a_failed_delivery_comes_back_and_sets_out_again_under_the_same_number(ship):
    s = on_the_road(ship)
    r = go(ship, s, "fail", reason="other")
    assert r.status_code == 400 and code(r) == "RETURN_NOTE_REQUIRED"
    back = go(ship, s, "fail", reason="site_closed", details="Gate closed, nobody answered").json()
    assert back["status"] == "returned" and back["actions"] == [] and back["failed_at"]  # the goods are not back yet
    [ret] = back["returns"]
    assert ret["kind"] == "delivery" and ret["status"] == "approved" and ret["attempt"] == 1
    r = go(ship, s, "reschedule")
    assert r.status_code == 409 and code(r) == "RETURN_NOT_RECEIVED"
    assert receive(ship, ret).status_code == 200
    assert set(ship.client.get(f"{ROOT}/{s['id']}").json()["actions"]) == {"reschedule", "close"}
    again = go(ship, s, "reschedule", driver_affiliation="external", driver_name="Fahad", vehicle_plate="XYZ 9", shipment_date="2026-10-06").json()
    assert again["status"] == "ready" and again["attempt"] == 2 and again["shipment_no"] == s["shipment_no"]
    assert again["driver_name"] == "Fahad" and again["dispatched_at"] is None and set(again["actions"]) == {"dispatch", "close"}
    assert code(go(ship, s, "reopen")) == "SHIPMENT_LEFT_BEFORE"  # its lines stay as dispatched
    assert code(go(ship, s, "cancel", reason="x")) == "SHIPMENT_LEFT_BEFORE"
    go(ship, s, "dispatch")
    assert go(ship, s, "deliver", received_by_name="Khalid").json()["status"] == "delivered"


def test_a_returned_note_is_closed_as_not_delivered(ship):
    s = on_the_road(ship)
    go(ship, s, "fail", reason="customer_refused")
    receive(ship, returns_of(ship, s)[0])
    assert go(ship, s, "close").status_code == 422  # a reason is required
    closed = go(ship, s, "close", reason="Order cancelled by the customer").json()
    assert closed["status"] == "not_delivered" and closed["close_reason"] == "Order cancelled by the customer" and closed["actions"] == []
    assert ship.client.get(ROOT, params=dict(status="not_delivered")).json()[0]["id"] == s["id"]


def test_a_pickup_is_not_delivered_in_part(ship):
    s = ship.create(delivery_method="pickup", driver_affiliation="external", driver_name="Customer driver", vehicle_plate="P 1")
    go(ship, s, "ready")
    r = go(ship, s, "deliver", received_by_name="Ali", refusal_reason="customer_refused",
           lines=[dict(line_id=s["lines"][0]["id"], delivered_quantity="10")])
    assert r.status_code == 400 and code(r) == "PARTIAL_NOT_FOR_PICKUP"


# ── case 2: returned by the customer after receiving ────────────────────────────────────────────

def delivered(env, **over):
    s = on_the_road(env, **over)
    return go(env, s, "deliver", received_by_name="Khalid").json()


def test_a_customer_returns_part_of_a_delivered_note(ship):
    s = delivered(ship, delivery_method="carrier", carrier_name="SMSA", tracking_no="T-1")
    first, second = s["lines"]
    new = lambda **over: ship.client.post(RETURNS, json=dict(shipment_id=s["id"], reason="quality_defect", customer_reference="UCIC-RMA-9",  # noqa: E731
                                                              lines=[dict(shipment_line_id=first["id"], quantity="20")], **over))
    r = ship.client.post(RETURNS, json=dict(shipment_id=s["id"], reason="quality_defect", lines=[dict(shipment_line_id=first["id"], quantity="101")]))
    assert r.status_code == 400 and code(r) == "RETURN_QUANTITY_INVALID" and r.json()["detail"]["available"] == "100.000"
    assert ship.client.post(RETURNS, json=dict(shipment_id=s["id"], reason="broken", lines=[dict(shipment_line_id=first["id"], quantity="1")])).status_code == 422
    ret = new().json()
    assert ret["kind"] == "customer" and ret["status"] == "requested" and ret["responsibility"] == "factory" and not ret["is_late"]
    assert set(ret["actions"]) == {"approve", "reject", "cancel"} and ret["customer_reference"] == "UCIC-RMA-9"
    assert ship.client.get(f"{ROOT}/{s['id']}").json()["line_returns"][first["id"]] == {"returned": "20.000", "returnable": "80.000"}
    approved = ship.client.post(f"{RETURNS}/{ret['id']}/approve", json={}).json()
    assert approved["status"] == "approved" and approved["decided_by_name"] == "Test User" and set(approved["actions"]) == {"receive", "cancel"}
    got = receive(ship, approved, lines=[dict(return_line_id=approved["lines"][0]["id"], received_quantity="18", received_weight="180")]).json()
    assert got["status"] == "received" and got["received_weight_kg"] == "180.000"
    detail = ship.client.get(f"{ROOT}/{s['id']}").json()
    assert detail["line_returns"][first["id"]] == {"returned": "18.000", "returnable": "82.000"} and detail["status"] == "delivered"
    damaged = ship.client.post(RETURNS, json=dict(shipment_id=s["id"], reason="transit_damage", carrier_claim_ref="SMSA-CLM-3",
                                                  lines=[dict(shipment_line_id=second["id"], quantity="40")])).json()
    assert damaged["responsibility"] == "carrier" and damaged["carrier_claim_ref"] == "SMSA-CLM-3"
    rejected = ship.client.post(f"{RETURNS}/{damaged['id']}/reject", json=dict(reason="Signed as received intact")).json()
    assert rejected["status"] == "rejected" and rejected["decision_note"] == "Signed as received intact"
    # a rejected return takes nothing back
    assert ship.client.get(f"{ROOT}/{s['id']}").json()["line_returns"][second["id"]]["returnable"] == "40.000"


def test_returns_only_against_delivered_notes_and_late_ones_need_a_note(ship):
    s = on_the_road(ship)
    r = ship.client.post(RETURNS, json=dict(shipment_id=s["id"], reason="quality_defect", lines=[dict(shipment_line_id=s["lines"][0]["id"], quantity="1")]))
    assert r.status_code == 409 and code(r) == "SHIPMENT_NOT_DELIVERED"
    go(ship, s, "deliver", received_by_name="Khalid")
    ship.client.patch("/api/v1/shipping/settings", json=dict(return_window_days=0))
    ret = ship.client.post(RETURNS, json=dict(shipment_id=s["id"], reason="excess_quantity", lines=[dict(shipment_line_id=s["lines"][0]["id"], quantity="5")])).json()
    assert ret["is_late"] and ret["responsibility"] == "customer"
    r = ship.client.post(f"{RETURNS}/{ret['id']}/approve", json={})
    assert r.status_code == 400 and code(r) == "LATE_RETURN_NEEDS_NOTE"
    ok = ship.client.post(f"{RETURNS}/{ret['id']}/approve", json=dict(note="Accepted as goodwill")).json()
    assert ok["status"] == "approved" and ok["decision_note"] == "Accepted as goodwill"
    cancelled = ship.client.post(f"{RETURNS}/{ret['id']}/cancel", json=dict(reason="Customer kept them")).json()
    assert cancelled["status"] == "cancelled" and cancelled["actions"] == []


def test_each_return_step_needs_its_permission(ship):
    s = delivered(ship)
    ret = ship.client.post(RETURNS, json=dict(shipment_id=s["id"], reason="quality_defect", lines=[dict(shipment_line_id=s["lines"][0]["id"], quantity="5")])).json()
    for permission in (S.RETURNS_APPROVE, S.RETURNS_REJECT, S.RETURNS_RECEIVE, S.RETURNS_CANCEL):
        ship.ctx.auth_user.permissions.discard(permission)
    ship.ctx.tenant = type(ship.ctx.tenant)(ship.user.id, ship.org.id, permissions=frozenset(ship.ctx.auth_user.permissions))
    assert ship.client.get(f"{RETURNS}/{ret['id']}").json()["actions"] == []
    assert ship.client.post(f"{RETURNS}/{ret['id']}/approve", json={}).status_code == 403
    assert ship.client.post(f"{RETURNS}/{ret['id']}/cancel", json=dict(reason="x")).status_code == 403
    ship.ctx.auth_user.permissions.discard(S.RETURNS_CREATE)
    r = ship.client.post(RETURNS, json=dict(shipment_id=s["id"], reason="quality_defect", lines=[dict(shipment_line_id=s["lines"][0]["id"], quantity="1")]))
    assert r.status_code == 403


def test_returns_list_filters_and_numbering_prefix(ship):
    assert ship.client.patch("/api/v1/shipping/settings", json=dict(return_prefix="ROF-RT-")).json()["return_prefix"] == "ROF-RT-"
    s = on_the_road(ship)
    go(ship, s, "fail", reason="no_receiver")
    s2 = delivered(ship)
    ship.client.post(RETURNS, json=dict(shipment_id=s2["id"], reason="wrong_item", lines=[dict(shipment_line_id=s2["lines"][1]["id"], quantity="10")]))
    rows = ship.client.get(RETURNS).json()
    assert len(rows) == 2 and all(r["return_no"].startswith("ROF-RT-2026-") for r in rows)
    assert [r["kind"] for r in ship.client.get(RETURNS, params=dict(kind="customer")).json()] == ["customer"]
    assert [r["shipment_no"] for r in ship.client.get(RETURNS, params=dict(search=s["shipment_no"])).json()] == [s["shipment_no"]]
    assert ship.client.get(RETURNS, params=dict(status="requested")).json()[0]["reason"] == "wrong_item"
    assert ship.client.get(ROOT).json()[0]["open_returns"] == 1


# ── weights, batches, proof of delivery ─────────────────────────────────────────────────────────

def test_the_received_weight_is_checked_against_the_gate_weight(ship):
    s = two_lines(ship)  # lines weigh 1400 kg
    go(ship, s, "ready")
    go(ship, s, "dispatch", gate_weight="1.42", gate_weight_unit="ton")
    got = go(ship, s, "deliver", received_by_name="Khalid", received_weight="1395").json()
    check = got["weight_check"]
    assert check["reference_kg"] == "1420.000" and check["received_kg"] == "1395.000"
    assert check["difference_kg"] == "-25.000" and check["difference_pct"] == "-1.76" and check["within_tolerance"] is False
    ship.client.patch("/api/v1/shipping/settings", json=dict(weight_tolerance_pct="2"))
    assert ship.client.get(f"{ROOT}/{s['id']}").json()["weight_check"]["within_tolerance"] is True


def test_a_line_names_the_production_order_it_comes_from(ship):
    orders = Base.metadata.tables["production_orders"]
    order_id = uuid4()
    ship.db.execute(orders.insert().values(id=order_id, organization_id=ship.org.id, production_order_number="PO-2026-000014", work_center_id=uuid4(),
                                           product_type="PP Strap", planned_quantity=500, unit="roll", priority="normal", status="completed",
                                           planned_start_date=date(2026, 10, 1), planned_end_date=date(2026, 10, 2), created_by_user_id=ship.user.id,
                                           status_version=1))
    ship.db.commit()
    options = ship.client.get(f"{ROOT}/lookups/production-orders", params=dict(q="000014")).json()
    assert [o["number"] for o in options] == ["PO-2026-000014"]
    s = ship.create(lines=[dict(description="PP Strap", quantity="10", unit="roll", production_order_id=str(order_id))])
    assert s["lines"][0]["production_order_no"] == "PO-2026-000014"
    r = ship.client.post(ROOT, json=ship.body(lines=[dict(description="x", quantity="1", unit="roll", production_order_id=str(uuid4()))]))
    assert r.status_code == 404 and code(r) == "PRODUCTION_ORDER_NOT_FOUND"


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(app_settings, "uploads_dir", str(tmp_path))
    return tmp_path


def test_the_signed_note_is_kept_as_proof_of_delivery(ship, uploads):
    s = two_lines(ship)
    upload = lambda content, name="pod.png": ship.client.post(f"{ROOT}/{s['id']}/attachments", data=dict(kind="proof_of_delivery"),  # noqa: E731
                                                              files=dict(file=(name, content)))
    r = upload(PNG)
    assert r.status_code == 409 and code(r) == "SHIPMENT_NOT_DISPATCHED"
    go(ship, s, "ready"); go(ship, s, "dispatch"); go(ship, s, "deliver", received_by_name="Khalid")
    r = upload(b"MZ executable", "virus.png")
    assert r.status_code == 400 and code(r) == "FILE_UNSUPPORTED_TYPE"
    [item] = upload(PNG).json()
    assert item["kind"] == "proof_of_delivery" and item["content_type"] == "image/webp" and item["uploaded_by_name"] == "Test User"
    upload(pdf(), "signed.pdf")
    files = ship.client.get(f"{ROOT}/{s['id']}").json()["attachments"]
    assert [f["content_type"] for f in files] == ["image/webp", "application/pdf"]  # photos are stored small (WebP)
    got = ship.client.get(f"{ROOT}/{s['id']}/attachments/{item['id']}")
    assert got.status_code == 200 and got.content.startswith(b"RIFF")  # stored small, as WebP
    # The shipment is delivered: its proof is part of the record, so "remove" archives it and the file stays.
    kept = ship.client.delete(f"{ROOT}/{s['id']}/attachments/{item['id']}").json()
    assert len(kept) == 2 and next(f for f in kept if f["id"] == item["id"])["archived_at"]
    assert ship.client.get(f"{ROOT}/{s['id']}/attachments/{item['id']}").status_code == 200
    assert not list(uploads.rglob("*.png"))  # nothing is stored under the user's file name or type
    ship.ctx.auth_user.permissions.discard(S.SHIPMENTS_DELIVER)
    assert upload(PNG).status_code == 403


def test_photos_are_kept_with_a_return(ship, uploads):
    s = delivered(ship)
    ret = ship.client.post(RETURNS, json=dict(shipment_id=s["id"], reason="quality_defect", lines=[dict(shipment_line_id=s["lines"][0]["id"], quantity="5")])).json()
    r = ship.client.post(f"{RETURNS}/{ret['id']}/attachments", files=dict(file=("crushed.png", PNG)))
    assert r.status_code == 201 and r.json()[0]["kind"] == "photo"
    assert ship.client.get(f"{RETURNS}/{ret['id']}").json()["attachments"][0]["file_name"] == "crushed.png"
    assert ship.client.get(f"{ROOT}/{s['id']}").json()["attachments"] == []  # the note keeps its own files


# ── documents ───────────────────────────────────────────────────────────────────────────────────

def test_return_note_document_in_arabic_and_english(ship):
    s = on_the_road(ship)
    go(ship, s, "fail", reason="transit_damage", details="Pallet fell in the truck")
    ret = returns_of(ship, s)[0]
    receive(ship, ret, lines=[dict(return_line_id=ship.client.get(f"{RETURNS}/{ret['id']}").json()["lines"][0]["id"], received_quantity="98")])
    preview = lambda lang: ship.client.post("/api/v1/reports/shipping.return_note/preview", json=dict(return_id=ret["id"], lang=lang))  # noqa: E731
    r = preview("ar")
    assert r.status_code == 200, r.text
    for text in ("إشعار مرتجع", ret["return_no"], s["shipment_no"], "مرتجع قبل الاستلام", "تلف أثناء النقل", "المصنع", "مُستلم في المصنع",
                 "المستلم فعلياً", "98", "Pallet fell in the truck"):
        assert text in r.text, text
    english = preview("en").text
    assert "RETURN NOTE" in english and "Damaged in transit" in english and "Received at the factory" in english
    note = ship.client.post("/api/v1/reports/shipping.delivery_note/preview", json=dict(shipment_id=s["id"], lang="ar")).text
    assert ret["return_no"] in note


@pytest.mark.skipif(not __import__("os").environ.get("REPORT_SAMPLES_DIR"), reason="Writes review samples: REPORT_SAMPLES_DIR=<folder> with the renderer running")
def test_write_return_note_samples(ship):
    """A partial delivery's return note and a customer return, in Arabic and English, through the real renderer."""
    import os
    from pathlib import Path
    out = Path(os.environ["REPORT_SAMPLES_DIR"]); out.mkdir(parents=True, exist_ok=True)
    s = on_the_road(ship, customer_reference="UCIC-PO-4471")
    first = s["lines"][0]
    go(ship, s, "deliver", received_by_name="Khalid", lines=[dict(line_id=first["id"], delivered_quantity="70")], refusal_reason="quality_issue",
       refusal_details="30 rolls with crushed cores")
    door = returns_of(ship, s)[0]
    receive(ship, door, notes="Back on pallet 4")
    later = ship.client.post(RETURNS, json=dict(shipment_id=s["id"], reason="spec_mismatch", customer_reference="UCIC-RMA-9",
                                                details="Thickness measured 0.31 mm against 0.35 mm", lines=[dict(shipment_line_id=s["lines"][1]["id"], quantity="10")])).json()
    for lang in ("ar", "en"):
        for name, path in ((f"RT-door-{lang}", f"{RETURNS}/{door['id']}"), (f"RT-customer-{lang}", f"{RETURNS}/{later['id']}"), (f"DN-partial-{lang}", f"{ROOT}/{s['id']}")):
            r = ship.client.get(f"{path}/document.pdf", params=dict(lang=lang))
            assert r.status_code == 200, r.text
            (out / f"{name}.pdf").write_bytes(r.content)
