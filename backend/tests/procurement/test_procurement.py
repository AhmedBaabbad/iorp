"""PROC-001: procurement — suppliers on the approved list, materials, goods receipts, the document, NCRs naming a registered
supplier, permissions and module boundaries."""
import ast
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute

from app.core.tenancy import TenantContext
from app.dependencies import get_current_user
from app.foundation.domain.permission_catalog import PERMISSION_BY_CODE
from app.main import app
from app.procurement.domain import permissions as PR
from app.quality.domain import permissions as Q

ROOT = "/api/v1/procurement"


@pytest.fixture
def proc(client, db, test_org, test_user):
    granted = set(PR.ALL) | set(Q.ALL)
    ctx = SimpleNamespace(user=SimpleNamespace(is_organization_root=False, id=test_user.id, full_name=test_user.full_name),
                          auth_user=SimpleNamespace(permissions=set(granted)), tenant=TenantContext(test_user.id, test_org.id, permissions=frozenset(granted)))
    app.dependency_overrides[get_current_user] = lambda: ctx

    def grant(*codes):
        ctx.auth_user.permissions = set(codes)
        ctx.tenant = TenantContext(test_user.id, test_org.id, permissions=frozenset(codes))

    def supplier(**over):
        data = dict(name="Gulf Polymers", category="raw_material", supplies="PP homopolymer", phone="0551234567", email="sales@gulfpoly.example",
                    vat_number="300000000000003")
        data.update(over)
        r = client.post(f"{ROOT}/suppliers", json=data)
        assert r.status_code == 201, r.text
        return r.json()

    def material(**over):
        data = dict(name="PP homopolymer H030", category="resin", unit="kg", inspection_required=True, spec_product_type="pp_resin")
        data.update(over)
        r = client.post(f"{ROOT}/materials", json=data)
        assert r.status_code == 201, r.text
        return r.json()

    def receipt(sup, mat, **over):
        data = dict(supplier_id=sup["id"], receipt_date="2026-10-05", supplier_delivery_no="DN-GP-4471", supplier_invoice_no="INV-9912",
                    purchase_reference="PO-778", vehicle_plate="ABC 123", driver_name="Ali",
                    lines=[dict(material_id=mat["id"], supplier_lot="SUP-7781", quantity="20000", unit="kg", package_count=800, weight="20.2",
                                weight_unit="ton")])
        data.update(over)
        r = client.post(f"{ROOT}/receipts", json=data)
        assert r.status_code == 201, r.text
        return r.json()

    yield SimpleNamespace(client=client, db=db, org=test_org, user=test_user, grant=grant, supplier=supplier, material=material, receipt=receipt)
    app.dependency_overrides.pop(get_current_user, None)


def code(r):
    return r.json()["detail"]["code"]


def test_suppliers_are_numbered_and_carry_their_standing(proc):
    s = proc.supplier()
    assert s["supplier_code"] == "SUP-0001" and s["status"] == "pending" and s["phone"] == "+966551234567" and s["actions"] == ["edit", "set_status"]
    assert proc.supplier(name="Masterbatch Co")["supplier_code"] == "SUP-0002"
    assert code(proc.client.post(f"{ROOT}/suppliers", json=dict(name="x", phone="12ab"))) == "PHONE_INVALID"
    assert proc.client.post(f"{ROOT}/suppliers", json=dict(name="x", organization_id=str(uuid4()))).status_code == 422
    set_status = lambda **b: proc.client.post(f"{ROOT}/suppliers/{s['id']}/status", json=b)  # noqa: E731
    assert code(set_status(status="blocked")) == "REASON_REQUIRED"
    ok = set_status(status="approved").json()
    assert ok["status"] == "approved" and ok["status_changed_by_name"] == "Test User"
    assert code(set_status(status="approved")) == "SUPPLIER_STATUS_UNCHANGED"
    cond = set_status(status="conditional", reason="Two wet lots this quarter").json()
    assert cond["status"] == "conditional" and cond["status_reason"] == "Two wet lots this quarter"
    assert {h["action"] for h in cond["history"]} == {"create", "status"}
    assert [x["name"] for x in proc.client.get(f"{ROOT}/suppliers", params=dict(status="conditional")).json()] == ["Gulf Polymers"]
    edited = proc.client.patch(f"{ROOT}/suppliers/{s['id']}", json=dict(contact_name="Omar", city="Jubail")).json()
    assert edited["contact_name"] == "Omar" and edited["city"] == "Jubail" and edited["name"] == "Gulf Polymers"


def test_materials_say_what_is_inspected(proc):
    m = proc.material()
    assert m["material_code"] == "MAT-0001" and m["inspection_required"] is True and m["unit"] == "kg"
    assert proc.client.post(f"{ROOT}/materials", json=dict(name="x", unit="kilos")).status_code == 422
    core = proc.material(name="Paper core 200 mm", category="core", unit="piece", inspection_required=False)
    assert proc.client.patch(f"{ROOT}/materials/{core['id']}", json=dict(active=False)).json()["active"] is False
    assert [x["name"] for x in proc.client.get(f"{ROOT}/materials", params=dict(active_only=True)).json()] == ["PP homopolymer H030"]


def test_a_goods_receipt_from_draft_to_received(proc):
    s, m = proc.supplier(), proc.material()
    r = proc.receipt(s, m)
    assert r["receipt_no"] == f"GRN-{date.today().year}-0001" and r["status"] == "draft" and r["supplier_name"] == "Gulf Polymers"
    [line] = r["lines"]
    assert line["description"] == "PP homopolymer H030" and line["inspection_required"] is True and line["supplier_lot"] == "SUP-7781"
    assert r["quantities"] == [{"unit": "kg", "quantity": "20000.000"}] and r["weight_kg"] == "20200.000" and r["inspection_lines"] == 1
    assert set(r["actions"]) == {"edit", "receive", "cancel"}
    bad = proc.client.post(f"{ROOT}/receipts", json=dict(supplier_id=s["id"], receipt_date="2026-10-05", lines=[dict(quantity="1", unit="kg")]))
    assert bad.status_code == 400 and code(bad) == "DESCRIPTION_REQUIRED"
    edited = proc.client.patch(f"{ROOT}/receipts/{r['id']}", json=dict(lines=[dict(material_id=m["id"], quantity="10000", unit="kg"),
                                                                           dict(description="Pallets (returnable)", quantity="20", unit="pallet")])).json()
    assert len(edited["lines"]) == 2 and edited["lines"][1]["inspection_required"] is False
    got = proc.client.post(f"{ROOT}/receipts/{r['id']}/receive").json()
    assert got["status"] == "received" and got["received_by_name"] == "Test User" and got["actions"] == ["cancel"]
    assert code(proc.client.patch(f"{ROOT}/receipts/{r['id']}", json=dict(notes="x"))) == "RECEIPT_NOT_DRAFT"
    assert proc.client.get(f"{ROOT}/receipts", params=dict(search="SUP-7781")).json() == []  # the lot left with the edit
    assert [x["receipt_no"] for x in proc.client.get(f"{ROOT}/receipts", params=dict(search="INV-9912")).json()] == [r["receipt_no"]]
    cancelled = proc.client.post(f"{ROOT}/receipts/{r['id']}/cancel", json=dict(reason="Entered twice")).json()
    assert cancelled["status"] == "cancelled" and cancelled["cancel_reason"] == "Entered twice"
    supplier = proc.client.get(f"{ROOT}/suppliers/{s['id']}").json()
    assert supplier["recent_receipts"][0]["receipt_no"] == r["receipt_no"]


def test_a_blocked_supplier_delivers_nothing(proc):
    s, m = proc.supplier(), proc.material()
    draft = proc.receipt(s, m)
    proc.client.post(f"{ROOT}/suppliers/{s['id']}/status", json=dict(status="blocked", reason="Repeated contamination"))
    r = proc.client.post(f"{ROOT}/receipts", json=dict(supplier_id=s["id"], receipt_date="2026-10-05"))
    assert r.status_code == 409 and code(r) == "SUPPLIER_BLOCKED"
    assert code(proc.client.post(f"{ROOT}/receipts/{draft['id']}/receive")) == "SUPPLIER_BLOCKED"
    assert proc.client.get(f"{ROOT}/suppliers/lookup").json() == []
    empty = proc.receipt(proc.supplier(name="Other"), m, lines=[])
    assert code(proc.client.post(f"{ROOT}/receipts/{empty['id']}/receive")) == "LINES_REQUIRED"


def test_a_non_conformance_report_names_a_registered_supplier(proc):
    s = proc.supplier()
    options = proc.client.get("/api/v1/quality/non-conformance-reports/lookups/suppliers", params=dict(q="Gulf")).json()
    assert [o["name"] for o in options] == ["Gulf Polymers"]
    r = proc.client.post("/api/v1/quality/non-conformance-reports", json=dict(
        report_date="2026-10-05", source_type="incoming_material", report_type="material_non_conformance", title="Wet lot",
        description="Moisture", supplier_id=s["id"], supplier_name="typed by hand"))
    assert r.status_code == 201, r.text
    assert r.json()["supplier_id"] == s["id"] and r.json()["supplier_name"] == "Gulf Polymers"
    bad = proc.client.post("/api/v1/quality/non-conformance-reports", json=dict(
        report_date="2026-10-05", source_type="supplier", report_type="other", title="x", description="y", supplier_id=str(uuid4())))
    assert bad.status_code == 404 and code(bad) == "SUPPLIER_NOT_FOUND"
    supplier = proc.client.get(f"{ROOT}/suppliers/{s['id']}").json()
    assert supplier["ncr_count"] == 1 and supplier["open_ncr_count"] == 1 and supplier["non_conformances"][0]["title"] == "Wet lot"


def test_each_step_needs_its_permission(proc):
    s, m = proc.supplier(), proc.material()
    r = proc.receipt(s, m)
    proc.grant(*PR.READ, PR.RECEIPTS_CREATE, PR.RECEIPTS_UPDATE)  # e.g. a clerk who prepares receipts
    assert proc.client.get(f"{ROOT}/receipts/{r['id']}").json()["actions"] == ["edit"]
    assert proc.client.post(f"{ROOT}/receipts/{r['id']}/receive").status_code == 403
    assert proc.client.post(f"{ROOT}/suppliers/{s['id']}/status", json=dict(status="approved")).status_code == 403
    assert proc.client.get(f"{ROOT}/suppliers/{s['id']}").json()["actions"] == []
    assert proc.client.patch(f"{ROOT}/settings", json=dict(receipt_prefix="R-")).status_code == 403


def test_receipt_prefix_and_the_document(proc):
    assert proc.client.patch(f"{ROOT}/settings", json=dict(receipt_prefix="ROF-GRN-")).json()["receipt_prefix"] == "ROF-GRN-"
    r = proc.receipt(proc.supplier(), proc.material())
    assert r["receipt_no"].startswith("ROF-GRN-")
    preview = lambda lang: proc.client.post("/api/v1/reports/procurement.goods_receipt/preview", json=dict(receipt_id=r["id"], lang=lang))  # noqa: E731
    ar = preview("ar")
    assert ar.status_code == 200, ar.text
    for text in ("إشعار استلام مواد", r["receipt_no"], "Gulf Polymers", "DN-GP-4471", "INV-9912", "PO-778", "SUP-7781", "كيلوجرام", "مسودة",
                 "لا تُصرف للإنتاج قبل اعتماد الجودة"):
        assert text in ar.text, text
    en = preview("en").text
    assert "GOODS RECEIPT NOTE" in en and "Materials received" in en and "20.2 Ton" in en


def test_every_route_declares_a_permission_and_the_module_imports_no_other():
    def policies(dependant):
        for dep in dependant.dependencies:
            policy = getattr(dep.call, "permission_policy", None)
            if policy:
                yield policy
            yield from policies(dep)
    routes = [r for r in app.routes if isinstance(r, APIRoute) and r.path.startswith("/api/v1/procurement")]
    assert len(routes) >= 14 and [r.path for r in routes if not list(policies(r.dependant))] == []
    for route in routes:
        for _kind, codes in policies(route.dependant):
            assert all(c in PERMISSION_BY_CODE for c in codes), (route.path, codes)
    root = Path(__file__).resolve().parents[2] / "app" / "procurement"
    imported = set()
    for path in root.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
    forbidden = ("app.commercial", "app.production", "app.quality", "app.shipping", "app.foundation", "app.workforce", "app.platform")
    assert sorted(m for m in imported if m.startswith(forbidden)) == []
    from app.procurement.infrastructure import models
    tables = [c.__tablename__ for c in vars(models).values() if isinstance(c, type) and hasattr(c, "__tablename__") and c.__module__ == models.__name__]
    assert tables and all(t.startswith("procurement_") for t in tables)


@pytest.mark.skipif(not __import__("os").environ.get("REPORT_SAMPLES_DIR"), reason="Writes review samples: REPORT_SAMPLES_DIR=<folder> with the renderer running")
def test_write_goods_receipt_samples(proc):
    import os
    out = Path(os.environ["REPORT_SAMPLES_DIR"]); out.mkdir(parents=True, exist_ok=True)
    m2 = proc.material(name="Black masterbatch MB-40", category="masterbatch")
    core = proc.material(name="Paper core 200 mm", category="core", unit="piece", inspection_required=False)
    r = proc.receipt(proc.supplier(), proc.material(), lines=[
        dict(material_id=None, description="PP homopolymer H030", supplier_lot="SUP-7781", quantity="20000", unit="kg", package_count=800, weight="20.2", weight_unit="ton"),
        dict(material_id=m2["id"], supplier_lot="MB-2210", quantity="500", unit="kg", package_count=20, weight="505"),
        dict(material_id=core["id"], quantity="2000", unit="piece", package_count=10)])
    proc.client.post(f"{ROOT}/receipts/{r['id']}/receive")
    for lang in ("ar", "en"):
        doc = proc.client.get(f"{ROOT}/receipts/{r['id']}/document.pdf", params=dict(lang=lang))
        assert doc.status_code == 200, doc.text
        (out / f"GRN-{lang}.pdf").write_bytes(doc.content)
