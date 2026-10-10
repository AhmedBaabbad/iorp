"""PROC-003: purchase orders — amounts with or without VAT in riyals or dollars, the stages from draft to received, goods
receipts against the order's lines, permissions, settings and the document in Arabic and English."""
from decimal import Decimal
from pathlib import Path

import pytest

from app.procurement.domain import permissions as PR
from app.procurement.domain import purchase_orders as PO
from app.procurement.domain.rules import ProcurementError
from tests.procurement.test_procurement import ROOT, code, proc  # noqa: F401 - the shared fixture

ORDERS = f"{ROOT}/purchase-orders"


def order(proc, sup, mat, **over):
    data = dict(supplier_id=sup["id"], order_date="2026-10-05", required_date="2026-10-20", currency="SAR", tax_rate=15,
                supplier_quote_ref="Q-GP-118", subject="PP resin for October", payment_terms="net_30", delivery_place="Factory — Riyadh 2nd Industrial City",
                lines=[dict(material_id=mat["id"], quantity="20000", unit="kg", unit_price="5.425"),
                       dict(description="Delivery to the factory", quantity="1", unit="lot", unit_price="1500")])
    data.update(over)
    r = proc.client.post(ORDERS, json=data)
    assert r.status_code == 201, r.text
    return r.json()


def step(proc, o, name, **payload):
    return proc.client.post(f"{ORDERS}/{o['id']}/{name}", json=payload or None)


def test_amounts_are_computed_with_or_without_vat():
    t = PO.totals([(Decimal("20000"), Decimal("5.425")), (Decimal("1"), Decimal("1500"))], Decimal("500"), 15)
    assert (t["subtotal"], t["taxable"], t["tax_amount"], t["total"]) == (Decimal("110000.00"), Decimal("109500.00"), Decimal("16425.00"), Decimal("125925.00"))
    assert PO.totals([(Decimal("3"), Decimal("0.335"))], 0, 0)["total"] == Decimal("1.01")  # 1.005 rounds half up
    with pytest.raises(ProcurementError):
        PO.totals([(Decimal("1"), Decimal("10"))], Decimal("11"), 15)
    assert PO.received_status(PO.SENT, [(Decimal("10"), Decimal("4"))]) == PO.PARTIAL
    assert PO.received_status(PO.PARTIAL, [(Decimal("10"), Decimal("10")), (Decimal("5"), Decimal("6"))]) == PO.RECEIVED
    assert PO.received_status(PO.RECEIVED, [(Decimal("10"), Decimal("0"))]) == PO.SENT  # its receipt was cancelled
    assert PO.received_status(PO.CLOSED, [(Decimal("10"), Decimal("0"))]) == PO.CLOSED


def test_a_local_order_in_riyals_with_vat(proc):
    sup, mat = proc.supplier(), proc.material()
    o = order(proc, sup, mat, discount_amount="500")
    assert o["po_number"].startswith("PO-2026-") and o["status"] == "draft" and o["currency"] == "SAR"
    assert (o["subtotal_amount"], o["discount_amount"], o["tax_amount"], o["total_amount"]) == ("110000.00", "500.00", "16425.00", "125925.00")
    first, second = o["lines"]
    assert (first["description"], first["unit_price"], first["line_total"]) == ("PP homopolymer H030", "5.4250", "108500.00")
    assert second["unit"] == "lot" and o["attention"] is None and set(o["actions"]) == {"edit", "approve", "cancel"}
    # the browser cannot set the amounts
    assert proc.client.patch(f"{ORDERS}/{o['id']}", json=dict(total_amount="1")).status_code == 422
    o = proc.client.patch(f"{ORDERS}/{o['id']}", json=dict(tax_rate=0)).json()
    assert (o["tax_amount"], o["total_amount"]) == ("0.00", "109500.00")
    assert code(proc.client.patch(f"{ORDERS}/{o['id']}", json=dict(tax_rate=5))) == "TAX_RATE_UNKNOWN"
    assert code(proc.client.patch(f"{ORDERS}/{o['id']}", json=dict(discount_amount="200000"))) == "DISCOUNT_INVALID"


def test_an_import_in_dollars_without_vat(proc):
    o = order(proc, proc.supplier(name="Sabic Asia Pacific", country="Singapore"), proc.material(), currency="USD", tax_rate=0, incoterm="CIF",
              payment_terms="letter_of_credit", lines=[dict(description="LLDPE film grade 218W", quantity="24", unit="ton", unit_price="1180")])
    assert (o["currency"], o["tax_rate"], o["tax_amount"], o["total_amount"], o["incoterm"]) == ("USD", "0.00", "0.00", "28320.00", "CIF")
    assert proc.client.post(ORDERS, json=dict(supplier_id=o["supplier_id"], order_date="2026-10-05", currency="EUR")).status_code == 422


def test_the_stages_and_receiving_against_the_order(proc):
    sup, mat = proc.supplier(), proc.material()
    o = order(proc, sup, mat)
    assert code(step(proc, o, "send")) == "ORDER_NOT_APPROVED"
    empty = order(proc, sup, mat, lines=[])
    assert code(step(proc, empty, "approve")) == "LINES_REQUIRED"
    o = step(proc, o, "approve").json()
    assert o["status"] == "approved" and o["approved_by_name"] == "Test User" and "receive" in o["actions"]
    assert code(proc.client.patch(f"{ORDERS}/{o['id']}", json=dict(subject="x"))) == "ORDER_NOT_DRAFT"
    o = step(proc, o, "send").json()
    assert o["status"] == "sent" and o["sent_by_name"] == "Test User"
    resin, delivery = o["lines"]
    [open_order] = proc.client.get(f"{ORDERS}/open-for-receipt", params=dict(supplier_id=sup["id"])).json()
    assert open_order["po_number"] == o["po_number"] and open_order["lines"][0]["remaining"] == "20000.000"

    # a first delivery of 12 tons, against the resin line
    r = proc.receipt(sup, mat, purchase_order_id=o["id"], purchase_reference=None,
                     lines=[dict(material_id=mat["id"], supplier_lot="SUP-7781", quantity="12000", unit="kg", po_line_id=resin["id"])])
    assert r["purchase_order_id"] == o["id"] and r["po_number"] == o["po_number"] and r["purchase_reference"] == o["po_number"]
    assert code(step(proc, o, "cancel", reason="x")) == "ORDER_HAS_RECEIPTS"  # a draft receipt waits on it
    proc.client.post(f"{ROOT}/receipts/{r['id']}/receive")
    o = proc.client.get(f"{ORDERS}/{o['id']}").json()
    assert o["status"] == "partially_received" and o["line_received"][resin["id"]] == {"received": "12000.000", "remaining": "8000.000"}
    assert o["receipts"][0]["receipt_no"] == r["receipt_no"] and "cancel" not in o["actions"]
    # the rest of the resin and the delivery service
    r2 = proc.receipt(sup, mat, purchase_order_id=o["id"], lines=[
        dict(material_id=mat["id"], supplier_lot="SUP-7790", quantity="8000", unit="kg", po_line_id=resin["id"]),
        dict(description="Delivery to the factory", quantity="1", unit="lot", po_line_id=delivery["id"])])
    proc.client.post(f"{ROOT}/receipts/{r2['id']}/receive")
    o = proc.client.get(f"{ORDERS}/{o['id']}").json()
    assert o["status"] == "received" and o["received_pct"] == "100.0" and o["actions"] == []
    # a receipt cancelled afterwards puts the order back to partially received
    proc.client.post(f"{ROOT}/receipts/{r2['id']}/cancel", json=dict(reason="Entered twice"))
    o = proc.client.get(f"{ORDERS}/{o['id']}").json()
    assert o["status"] == "partially_received"
    o = step(proc, o, "close", reason="The supplier cannot deliver the rest").json()
    assert o["status"] == "closed" and o["close_reason"] == "The supplier cannot deliver the rest"
    assert code(proc.client.post(f"{ROOT}/receipts", json=dict(supplier_id=sup["id"], receipt_date="2026-10-06", purchase_order_id=o["id"]))) == \
        "ORDER_NOT_OPEN_FOR_RECEIPT"
    assert [h["action"] for h in o["history"]] == ["create", "approve", "send", "receipt", "received", "receipt", "close"]


def test_a_receipt_must_match_its_order(proc):
    sup, mat = proc.supplier(), proc.material()
    o = step(proc, order(proc, sup, mat), "approve").json()
    other = proc.supplier(name="Another")
    bad = proc.client.post(f"{ROOT}/receipts", json=dict(supplier_id=other["id"], receipt_date="2026-10-06", purchase_order_id=o["id"]))
    assert code(bad) == "ORDER_OF_ANOTHER_SUPPLIER"
    unit = proc.client.post(f"{ROOT}/receipts", json=dict(supplier_id=sup["id"], receipt_date="2026-10-06", purchase_order_id=o["id"],
                                                          lines=[dict(material_id=mat["id"], quantity="20", unit="ton", po_line_id=o["lines"][0]["id"])]))
    assert code(unit) == "ORDER_LINE_UNIT_MISMATCH"
    loose = proc.client.post(f"{ROOT}/receipts", json=dict(supplier_id=sup["id"], receipt_date="2026-10-06",
                                                           lines=[dict(material_id=mat["id"], quantity="20", unit="kg", po_line_id=o["lines"][0]["id"])]))
    assert code(loose) == "ORDER_LINE_NOT_IN_ORDER"
    o = step(proc, o, "cancel", reason="Price changed").json()
    assert o["status"] == "cancelled" and o["cancel_reason"] == "Price changed"


def test_a_blocked_supplier_gets_no_order(proc):
    sup, mat = proc.supplier(), proc.material()
    o = order(proc, sup, mat)
    proc.client.post(f"{ROOT}/suppliers/{sup['id']}/status", json=dict(status="blocked", reason="Repeated contamination"))
    assert code(step(proc, o, "approve")) == "SUPPLIER_BLOCKED"
    assert code(proc.client.post(ORDERS, json=dict(supplier_id=sup["id"], order_date="2026-10-05"))) == "SUPPLIER_BLOCKED"


def test_each_step_needs_its_permission(proc):
    o = order(proc, proc.supplier(), proc.material())
    proc.grant(PR.PO_READ, PR.PO_CREATE, PR.PO_UPDATE)
    assert step(proc, o, "approve").status_code == 403
    assert set(proc.client.get(f"{ORDERS}/{o['id']}").json()["actions"]) == {"edit"}
    proc.grant(PR.SUPPLIERS_READ)
    assert proc.client.get(ORDERS).status_code == 403
    assert proc.client.get(f"{ORDERS}/{o['id']}/document.pdf").status_code == 403


def test_prefix_terms_and_the_document(proc):
    s = proc.client.patch(f"{ROOT}/settings", json=dict(po_prefix="ROF-PO-", po_terms_ar="تُسلَّم المواد مع شهادة تحليل.\nيُذكر رقم أمر الشراء على الفاتورة.",
                                                       po_terms_en="Goods are delivered with a certificate of analysis.")).json()
    assert s["po_prefix"] == "ROF-PO-" and s["receipt_prefix"] == "GRN-"
    sup, mat = proc.supplier(), proc.material()
    o = order(proc, sup, mat, discount_amount="500", incoterm="DAP")
    assert o["po_number"].startswith("ROF-PO-2026-")
    preview = lambda lang, oid=o["id"]: proc.client.post("/api/v1/reports/procurement.purchase_order/preview", json=dict(order_id=oid, lang=lang))  # noqa: E731
    ar = preview("ar")
    assert ar.status_code == 200, ar.text
    for text in ("أمر شراء", o["po_number"], "Gulf Polymers", "300000000000003", "Q-GP-118", "آجل 30 يومًا", "DAP — Delivered At Place",
                 "ضريبة القيمة المضافة (15%)", "125,925.00", "5.425", "108,500.00", "كجم", "تُسلَّم المواد مع شهادة تحليل.", "مسودة — غير معتمد",
                 "قبول المورد", 'class="po-sar"', "ريال سعودي"):
        assert text in ar.text, text
    en = preview("en").text
    for text in ("PURCHASE ORDER", "Items and prices", "Total including VAT", "Net 30 days", "Saudi Riyal", "Goods are delivered with a certificate"):
        assert text in en, text
    usd = order(proc, sup, mat, currency="USD", tax_rate=0, lines=[dict(description="LLDPE 218W", quantity="24", unit="ton", unit_price="1180")])
    en = preview("en", usd["id"]).text
    assert "US Dollar" in en and "Prices exclude VAT" in en and "VAT (15%)" not in en and 'class="po-usd"' in en and "28,320.00" in en


@pytest.mark.skipif(not __import__("os").environ.get("REPORT_SAMPLES_DIR"), reason="Writes review samples: REPORT_SAMPLES_DIR=<folder> with the renderer running")
def test_write_purchase_order_samples(proc):
    import os
    out = Path(os.environ["REPORT_SAMPLES_DIR"]); out.mkdir(parents=True, exist_ok=True)
    proc.client.patch(f"{ROOT}/settings", json=dict(
        po_terms_ar="تُسلَّم المواد مع شهادة تحليل لكل دفعة.\nتخضع كل دفعة لفحص الجودة عند الاستلام، والمرفوض يُعاد على حساب المورد.\nيُذكر رقم أمر الشراء على إشعار التسليم والفاتورة.",
        po_terms_en="Each lot is delivered with its certificate of analysis.\nEvery lot is inspected on arrival; rejected material is returned at the supplier's cost.\n"
                    "Quote the purchase order number on the delivery note and the invoice."))
    sup = proc.supplier(address="Jubail Industrial City", city="Jubail", country="Saudi Arabia", cr_number="2055001234", contact_name="Omar Saleh")
    mb = proc.material(name="Black masterbatch MB-40", category="masterbatch")
    core = proc.material(name="Paper core 76 mm × 3 mm", category="core", unit="piece", inspection_required=False)
    o = order(proc, sup, proc.material(), discount_amount="500", incoterm="DAP", payment_terms_note="from the invoice date", lines=[
        dict(material_id=None, description="PP homopolymer H030 — raffia grade", notes="MFI 3 g/10 min; moisture ≤ 0.05 %", quantity="20000", unit="kg", unit_price="5.425"),
        dict(material_id=mb["id"], quantity="500", unit="kg", unit_price="12.75"),
        dict(material_id=core["id"], quantity="2000", unit="piece", unit_price="1.10"),
        dict(description="Delivery to the factory", quantity="1", unit="lot", unit_price="1500")])
    step(proc, o, "approve")
    imp = order(proc, proc.supplier(name="Sabic Asia Pacific Pte", country="Singapore"), proc.material(), currency="USD", tax_rate=0, incoterm="CIF",
                payment_terms="letter_of_credit", delivery_place="Dammam port", lines=[dict(description="LLDPE film grade 218W", quantity="24", unit="ton", unit_price="1180")])
    for name, oid in (("PO-SAR", o["id"]), ("PO-USD", imp["id"])):
        for lang in ("ar", "en"):
            doc = proc.client.get(f"{ORDERS}/{oid}/document.pdf", params=dict(lang=lang))
            assert doc.status_code == 200, doc.text
            (out / f"{name}-{lang}.pdf").write_bytes(doc.content)
