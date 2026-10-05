"""SHIP-001: shipments and delivery notes — customers (registered or named), methods, lines, lifecycle, permissions, document."""
import ast
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import select

from app.commercial.infrastructure.models import Customer
from app.core.tenancy import TenantContext
from app.dependencies import get_current_user
from app.foundation.domain.permission_catalog import PERMISSION_BY_CODE
from app.main import app
from app.shipping.domain import permissions as S
from app.shipping.domain.rules import normalize_phone, ShippingError
from app.shipping.infrastructure.models import ShipmentEvent

ROOT = "/api/v1/shipping/shipments"


@pytest.fixture
def ship(client, db, test_org, test_user):
    customer = Customer(organization_id=test_org.id, customer_code="C-SHIP", name="UCIC Company", phone="0551234567",
                        email="orders@ucic.example", city="Riyadh")
    db.add(customer); db.commit()
    ctx = SimpleNamespace(user=SimpleNamespace(is_organization_root=False, id=test_user.id, full_name=test_user.full_name),
                          auth_user=SimpleNamespace(permissions=set(S.ALL)),
                          tenant=TenantContext(test_user.id, test_org.id, permissions=frozenset(S.ALL)))
    app.dependency_overrides[get_current_user] = lambda: ctx

    def body(**over):
        data = dict(delivery_method="factory_delivery", shipment_date="2026-10-04", customer_id=str(customer.id),
                    lines=[dict(description="PP Strap", width_mm="5", thickness_mm="0.35", quantity="120", unit="roll", weight="1200")])
        data.update(over)
        return data

    def create(**over):
        r = client.post(ROOT, json=body(**over))
        assert r.status_code == 201, r.text
        return r.json()

    yield SimpleNamespace(client=client, db=db, org=test_org, user=test_user, ctx=ctx, customer=customer, body=body, create=create)
    app.dependency_overrides.pop(get_current_user, None)


def code(r):
    return r.json()["detail"]["code"]


def go(env, shipment, step, **payload):
    return env.client.post(f"{ROOT}/{shipment['id']}/{step}", json=payload or None)


# ── customer and recipient ──────────────────────────────────────────────────────────────────────

def test_a_registered_customer_fills_the_recipient_contacts(ship):
    s = ship.create()
    assert s["shipment_no"].startswith("DN-2026-") and s["status"] == "draft"
    assert s["customer_name"] == "UCIC Company" and s["customer_id"] == str(ship.customer.id)
    assert s["consignee_phone"] == "+966551234567" and s["consignee_email"] == "orders@ucic.example" and s["delivery_city"] == "Riyadh"
    assert s["quantities"] == [{"unit": "roll", "quantity": "120.000"}] and s["weight_total_kg"] == "1200.000"
    assert s["missing_details"] == ["driver_name", "vehicle_plate"] and set(s["actions"]) == {"edit", "ready", "cancel"}


def test_an_unregistered_customer_is_named_and_the_name_is_required(ship):
    s = ship.create(customer_id=None, customer_name="Walk-in buyer", consignee_phone="٠٥٠٠٠٠٠٠٠١")
    assert s["customer_id"] is None and s["customer_name"] == "Walk-in buyer" and s["consignee_phone"] == "+966500000001"
    r = ship.client.post(ROOT, json=ship.body(customer_id=None, customer_name="  "))
    assert r.status_code == 400 and code(r) == "CUSTOMER_REQUIRED"
    r = ship.client.post(ROOT, json=ship.body(customer_id=str(uuid4())))
    assert r.status_code == 404 and code(r) == "CUSTOMER_NOT_FOUND"
    r = ship.client.post(ROOT, json=ship.body(consignee_phone="12ab"))
    assert r.status_code == 400 and code(r) == "PHONE_INVALID"
    assert ship.client.post(ROOT, json=ship.body(consignee_email="not-an-email")).status_code == 422
    assert ship.client.post(ROOT, json=ship.body(location_url="javascript:alert(1)")).status_code == 422
    assert ship.client.post(ROOT, json=ship.body(organization_id=str(uuid4()))).status_code == 422


def test_phone_forms():
    assert normalize_phone("055 123 4567") == "+966551234567"
    assert normalize_phone("0112345678") == "+966112345678"
    assert normalize_phone("00971501234567") == "+971501234567"
    with pytest.raises(ShippingError):
        normalize_phone("123")


def test_lines_are_description_width_thickness_quantity_and_one_weight(ship):
    assert ship.client.post(ROOT, json=ship.body(lines=[dict(description="x", quantity="5", unit="rolls")])).status_code == 422
    assert ship.client.post(ROOT, json=ship.body(lines=[dict(description="x", quantity="5", unit="roll", weight_unit="stone")])).status_code == 422
    assert ship.client.post(ROOT, json=ship.body(lines=[dict(description="x", quantity="5", unit="roll", net_weight="1")])).status_code == 422  # gone
    assert ship.client.post(ROOT, json=ship.body(lines=[dict(description="x", quantity="5", unit="roll", width_mm="-1")])).status_code == 422
    s = ship.create(lines=[
        dict(description="Strap 5 mm", width_mm="5", thickness_mm="0.35", quantity="100", unit="roll", weight="2", weight_unit="ton"),
        dict(description="Strap 15 mm", width_mm="15", thickness_mm="0.85", quantity="500", unit="kg", weight="500"),
        dict(description="Sample", quantity="1", unit="piece", weight="10", weight_unit="lb")])
    first = s["lines"][0]
    assert (first["width_mm"], first["thickness_mm"], first["weight"], first["weight_unit"]) == ("5.000", "0.350", "2.000", "ton")
    assert {q["unit"]: q["quantity"] for q in s["quantities"]} == {"roll": "100.000", "kg": "500.000", "piece": "1.000"}
    assert s["weight_total_kg"] == "2504.536"  # 2 t + 500 kg + 10 lb


# ── lifecycle ───────────────────────────────────────────────────────────────────────────────────

def test_factory_delivery_ready_dispatch_deliver(ship):
    s = ship.create()
    r = go(ship, s, "ready")
    assert r.status_code == 400 and code(r) == "METHOD_DETAILS_REQUIRED" and r.json()["detail"]["fields"] == "driver_name,vehicle_plate"
    ship.client.patch(f"{ROOT}/{s['id']}", json=dict(driver_name="Saleh", driver_phone="0559876543", vehicle_plate="أ ب ج 1234", vehicle_type="Truck"))
    ready = go(ship, s, "ready").json()
    assert ready["status"] == "ready" and set(ready["actions"]) == {"reopen", "dispatch", "cancel"}
    r = ship.client.patch(f"{ROOT}/{s['id']}", json=dict(notes="late change"))
    assert r.status_code == 409 and code(r) == "SHIPMENT_NOT_DRAFT"
    dispatched = go(ship, s, "dispatch").json()
    assert dispatched["status"] == "dispatched" and dispatched["dispatched_at"] and dispatched["actions"] == ["deliver", "fail"]
    r = go(ship, s, "cancel", reason="no")
    assert r.status_code == 409 and code(r) == "SHIPMENT_ALREADY_LEFT"
    assert go(ship, s, "deliver", received_by_name=" ").status_code == 422  # a receiver is required
    delivered = go(ship, s, "deliver", received_by_name="Khalid", delivery_notes="All pallets intact").json()
    assert delivered["status"] == "delivered" and delivered["received_by_name"] == "Khalid" and delivered["actions"] == ["return"]
    assert [h["action"] for h in delivered["history"]] == ["created", "ready", "dispatched", "delivered"]


def test_pickup_is_delivered_at_the_factory_and_carrier_needs_its_name(ship):
    pickup = ship.create(delivery_method="pickup", driver_name="Customer driver", driver_id_no="2345678901", vehicle_plate="ر س ص 9876")
    go(ship, pickup, "ready")
    r = go(ship, pickup, "dispatch")
    assert r.status_code == 409 and code(r) == "PICKUP_IS_DELIVERED_AT_FACTORY"
    done = go(ship, pickup, "deliver", received_by_name="Customer driver").json()
    assert done["status"] == "delivered" and done["dispatched_at"] == done["delivered_at"]
    carrier = ship.create(delivery_method="carrier", driver_name="ignored")
    assert carrier["driver_name"] is None and code(go(ship, carrier, "ready")) == "METHOD_DETAILS_REQUIRED"
    ship.client.patch(f"{ROOT}/{carrier['id']}", json=dict(carrier_name="SMSA", tracking_no="290012345"))
    assert go(ship, carrier, "ready").json()["status"] == "ready"


def test_reopen_and_cancel_with_reason(ship):
    s = ship.create(driver_name="Saleh", vehicle_plate="1234")
    go(ship, s, "ready")
    assert go(ship, s, "reopen").json()["status"] == "draft"
    assert go(ship, s, "cancel", reason="Customer postponed").json()["status"] == "cancelled"
    assert code(go(ship, s, "cancel", reason="again")) == "SHIPMENT_IS_FINAL"
    empty = ship.create(lines=[])
    assert code(go(ship, empty, "ready")) == "LINES_REQUIRED"


def test_events_form_the_outbox_for_notifications(ship):
    s = ship.create(notify_consignee=True, driver_name="Saleh", vehicle_plate="1234")
    go(ship, s, "ready"); go(ship, s, "dispatch")
    events = ship.db.scalars(select(ShipmentEvent).where(ShipmentEvent.shipment_id == UUID(s["id"])).order_by(ShipmentEvent.occurred_at)).all()
    assert [e.event_type for e in events] == ["shipment.created", "shipment.ready", "shipment.dispatched"]
    assert events[-1].payload["consignee_phone"] == "+966551234567" and events[-1].payload["notify"] is True
    assert all(e.processed_at is None for e in events)  # nothing is sent by this module


# ── permissions, tenancy, list and document ────────────────────────────────────────────────────

def test_permissions_per_action(ship):
    s = ship.create(driver_name="Saleh", vehicle_plate="1234")
    go(ship, s, "ready")
    ship.ctx.auth_user.permissions.discard(S.SHIPMENTS_DISPATCH)
    assert go(ship, s, "dispatch").status_code == 403
    assert "dispatch" not in ship.client.get(f"{ROOT}/{s['id']}").json()["actions"]
    ship.ctx.auth_user.permissions.discard(S.SHIPMENTS_READ)
    assert ship.client.get(ROOT).status_code == 403


def test_list_filters_search_and_tenancy(ship):
    a = ship.create(customer_reference="UCIC-PO-77")
    ship.create(customer_id=None, customer_name="Other buyer", delivery_method="pickup")
    rows = ship.client.get(ROOT, params=dict(search="UCIC-PO")).json()
    assert [r["id"] for r in rows] == [a["id"]]
    assert {r["delivery_method"] for r in ship.client.get(ROOT, params=dict(method="pickup")).json()} == {"pickup"}
    assert ship.client.get(f"{ROOT}/{uuid4()}").status_code == 404
    customers = ship.client.get(f"{ROOT}/lookups/customers", params=dict(q="UCIC")).json()
    assert [c["name"] for c in customers] == ["UCIC Company"] and customers[0]["phone"] == "0551234567"


def test_numbering_prefix_and_settings(ship):
    assert ship.client.patch("/api/v1/shipping/settings", json=dict(note_prefix="ROF-DN-")).json()["note_prefix"] == "ROF-DN-"
    first, second = ship.create(), ship.create()
    assert first["shipment_no"].startswith("ROF-DN-2026-") and int(second["shipment_no"][-4:]) == int(first["shipment_no"][-4:]) + 1
    ship.ctx.auth_user.permissions.discard(S.SETTINGS_UPDATE)
    assert ship.client.patch("/api/v1/shipping/settings", json=dict(note_prefix="X-")).status_code == 403


def test_delivery_note_document_in_arabic_and_english(ship):
    s = ship.create(customer_reference="UCIC-PO-77", driver_name="Saleh", driver_phone="0559876543", vehicle_plate="أ ب ج 1234", notes="Handle with care")
    preview = lambda lang: ship.client.post("/api/v1/reports/shipping.delivery_note/preview", json=dict(shipment_id=s["id"], lang=lang))  # noqa: E731
    r = preview("ar")
    assert r.status_code == 200, r.text
    for text in ("إشعار تسليم", s["shipment_no"], "UCIC Company", "UCIC-PO-77", "توصيل بسيارة المصنع", "أ ب ج 1234", "العرض (مم)",
                 "السماكة (مم)", "0.35", "1200 كيلوجرام", "رول", "مسودة", "استلمتُ البضاعة"):
        assert text in r.text, text
    english = preview("en").text
    assert "DELIVERY NOTE" in english and "Factory delivery" in english and "Received the goods" in english
    assert "1200 Kilogram" in english and "Width (mm)" in english and ">Roll<" in english


# ── architecture ────────────────────────────────────────────────────────────────────────────────

def test_every_shipping_route_declares_a_known_permission():
    def policies(dependant):
        for dep in dependant.dependencies:
            policy = getattr(dep.call, "permission_policy", None)
            if policy:
                yield policy
            yield from policies(dep)
    routes = [r for r in app.routes if isinstance(r, APIRoute) and r.path.startswith("/api/v1/shipping")]
    assert len(routes) >= 12
    assert [r.path for r in routes if not list(policies(r.dependant))] == []
    for route in routes:
        for _kind, codes in policies(route.dependant):
            assert all(c in PERMISSION_BY_CODE for c in codes), (route.path, codes)


def test_shipping_imports_no_other_business_module_and_owns_prefixed_tables():
    root = Path(__file__).resolve().parents[2] / "app" / "shipping"
    imported = set()
    for path in root.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
    forbidden = ("app.commercial", "app.production", "app.quality", "app.foundation", "app.workforce", "app.platform")
    assert sorted(m for m in imported if m.startswith(forbidden)) == []
    from app.shipping.infrastructure import models
    tables = [c.__tablename__ for c in vars(models).values() if isinstance(c, type) and hasattr(c, "__tablename__") and c.__module__ == models.__name__]
    assert tables and all(t.startswith("shipping_") for t in tables)


@pytest.mark.skipif(not __import__("os").environ.get("REPORT_SAMPLES_DIR"), reason="Writes review samples: REPORT_SAMPLES_DIR=<folder> with the renderer running")
def test_write_delivery_note_samples(ship):
    """The delivery note in Arabic and English through the real renderer. Written outside the project."""
    import os
    from app.foundation.api.branding_schemas import BrandingUpdate
    from app.foundation.application.branding_service import BrandingService
    out = Path(os.environ["REPORT_SAMPLES_DIR"]); out.mkdir(parents=True, exist_ok=True)
    BrandingService(ship.db).update(ship.org.id, BrandingUpdate(legal_name_ar="مصنع ريحانة الأفق للصناعة", legal_name_en="REHANAH AL-OFUQ FACTORY FOR INDUSTRY",
                                                               commercial_registration_no="1010000000", vat_number="300000000000003"), ship.user.id)
    s = ship.create(customer_reference="UCIC-PO-4471", consignee_name="UCIC Warehouse — Sulay", delivery_address="Sulay industrial area, street 12",
                    driver_name="صالح العتيبي", driver_phone="0559876543", vehicle_plate="أ ب ج 1234", vehicle_type="Truck 7 t",
                    notes="Deliver before 2 pm. Pallets are shrink-wrapped.",
                    lines=[dict(description="PP Strap — black, full automatic", width_mm="5", thickness_mm="0.35", quantity="120", unit="roll", weight="1260"),
                           dict(description="PP Strap — white", width_mm="15", thickness_mm="0.85", quantity="60", unit="roll", weight="0.366", weight_unit="ton")])
    go(ship, s, "ready"); go(ship, s, "dispatch")
    for lang in ("ar", "en"):
        r = ship.client.get(f"{ROOT}/{s['id']}/document.pdf", params=dict(lang=lang))
        assert r.status_code == 200, r.text
        (out / f"DN-{lang}.pdf").write_bytes(r.content)
