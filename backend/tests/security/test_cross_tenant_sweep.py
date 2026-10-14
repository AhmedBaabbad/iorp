from tests.route_inventory import discover_routes
"""SEC-ISO-002: every identifier route of procurement, shipping, master data, delegations, approvals, notifications,
announcements and workforce, swept with another organization's records (complements tests/test_batch1_isolation.py).

Organization B creates its records through the real API. A user of organization A, holding every permission, then calls
EVERY route of those modules that takes an identifier, with B's identifiers: the answer must be exactly the one a
non-existent identifier gets (no 5xx, no 2xx except an empty list, nothing that tells B's record exists), and B's records must read the same
afterwards. A also tries to use B's records inside its own new documents, to download B's files, and to find B's
records through lists, searches and an organization override. The guard test fails when a new identifier route is added
to these modules without being swept here. Synthetic data only; files go to a temporary folder.
"""
import re
import uuid
from datetime import date, timedelta

import pytest

from app.core.config import settings as app_settings
from app.foundation.domain.enums import UserStatus
from app.foundation.infrastructure.models import User
from app.core.security import hash_password
from app.main import app
from tests.file_samples import png
from tests.test_tenant_isolation import isolated_tenants  # noqa: F401 - the shared two-organization fixture

API = "/api/v1"
SWEPT = re.compile(r"^/api/v1/(procurement|shipping|masterdata|delegations|approvals|notifications|announcements|workforce-members)/")
# Path parameters that name a kind or a list, not a record: they are filled with a valid value, not an identifier.
NAMED = {"kind": None, "list_name": "sector", "resource_type": "purchase_order"}
# Probe bodies: enough for most actions to reach the record lookup (an action refusing its body before the lookup
# answers the same for a foreign and a missing record, which the comparison still checks).
BODY = {"reason": "isolation probe", "notes": "isolation probe", "received_by_name": "Probe", "name": "Probe",
        "status": "approved", "version": 1, "shipment_date": str(date.today() + timedelta(days=3))}


def _login(client, email):
    r = client.post(f"{API}/auth/login", json={"email": email, "password": "Test1234!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def world(client, db, isolated_tenants, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(app_settings, "uploads_dir", str(tmp_path))
    d = isolated_tenants
    hb = _login(client, d["user_b"].email)
    client.headers.pop("Authorization", None)

    def as_b(method, path, **kw):
        r = client.request(method, API + path, headers=hb, **kw)
        assert r.status_code in (200, 201), (path, r.status_code, r.text)
        return r.json()

    today = date.today()
    supplier = as_b("post", "/procurement/suppliers", json=dict(name="B Polymers", category="raw_material"))
    material = as_b("post", "/procurement/materials", json=dict(name="B resin", category="resin", unit="kg", inspection_required=False))
    contact = as_b("post", f"/procurement/suppliers/{supplier['id']}/contacts", json=dict(name="B buyer"))
    receipt = as_b("post", "/procurement/receipts", json=dict(supplier_id=supplier["id"], receipt_date=str(today),
                                                               lines=[dict(material_id=material["id"], quantity="10", unit="kg")]))
    order = as_b("post", "/procurement/purchase-orders", json=dict(
        supplier_id=supplier["id"], order_date=str(today), currency="SAR", tax_rate=15,
        lines=[dict(material_id=material["id"], quantity="10", unit="kg", unit_price="5")]))
    shipment = as_b("post", "/shipping/shipments", json=dict(
        delivery_method="factory_delivery", shipment_date=str(today), customer_id=str(d["customer_b"].id),
        driver_affiliation="external", driver_name="Saleh", vehicle_plate="ABC 1234",
        lines=[dict(description="PP Strap", width_mm="5", thickness_mm="0.35", quantity="100", unit="roll", weight="1000")]))
    for step, payload in (("ready", None), ("dispatch", None), ("deliver", {"received_by_name": "Khalid"})):
        as_b("post", f"/shipping/shipments/{shipment['id']}/{step}", json=payload)
    shipment_file = as_b("post", f"/shipping/shipments/{shipment['id']}/attachments", data=dict(kind="proof_of_delivery"),
                         files=dict(file=("pod.png", png())))[0]
    shipment = as_b("get", f"/shipping/shipments/{shipment['id']}")
    ret = as_b("post", "/shipping/returns", json=dict(shipment_id=shipment["id"], reason="quality_defect",
                                                     lines=[dict(shipment_line_id=shipment["lines"][0]["id"], quantity="1")]))
    return_file = as_b("post", f"/shipping/returns/{ret['id']}/attachments", data=dict(kind="photo"), files=dict(file=("r.png", png())))
    return_file = return_file[0] if isinstance(return_file, list) else return_file
    item = as_b("post", "/masterdata/lists/sector", json=dict(name_ar="قطاع ب", name_en="B sector"))
    deputy = User(organization_id=d["org_b"].id, full_name="B Deputy", email="deputy-b@example.com",
                  password_hash=hash_password("Test1234!"), status=UserStatus.ACTIVE)
    db.add(deputy); db.commit()
    delegation = as_b("post", "/delegations", json=dict(
        delegator_user_id=str(d["user_b"].id), delegate_user_id=str(deputy.id), permission_code="procurement:purchase_orders:approve",
        effective_from=str(today), effective_to=str(today + timedelta(days=7)), reason="Annual leave"))
    from app.masterdata.infrastructure.models import Product
    from app.notifications.infrastructure.models import Announcement, NotificationItem
    org_b, user_b = d["org_b"].id, d["user_b"].id
    product = Product(organization_id=org_b, code="B-PROD", key="b_prod", name_ar="منتج ب", name_en="B product", created_by_user_id=user_b)
    notice = NotificationItem(organization_id=org_b, recipient_user_id=user_b, event="test", category="work")
    announcement = Announcement(organization_id=org_b, author_user_id=user_b, author_name="B", title="B notice", body="B only", audience="everyone")
    db.add_all([product, notice, announcement]); db.commit()
    ids = {
        "product_id": str(product.id), "notification_item_id": str(notice.id), "announcement_id": str(announcement.id),
        "supplier_id": supplier["id"], "material_id": material["id"], "record_id": contact["id"], "receipt_id": receipt["id"],
        "order_id": order["id"], "shipment_id": shipment["id"], "return_id": ret["id"], "item_id": item["id"],
        "delegation_id": delegation["id"], "member_id": str(d["member_b"].id), "customer_id": str(d["customer_b"].id),
        "resource_id": order["id"],
    }
    files = {"shipment": (shipment["id"], shipment_file["id"]), "return": (ret["id"], return_file["id"])}
    reads = [f"/procurement/suppliers/{supplier['id']}", f"/procurement/receipts/{receipt['id']}",
             f"/procurement/purchase-orders/{order['id']}", f"/shipping/shipments/{shipment['id']}", f"/shipping/returns/{ret['id']}",
             f"/procurement/suppliers/{supplier['id']}/contacts"]
    return dict(client=client, db=db, a=d["headers"], b=hb, ids=ids, files=files, reads=reads, d=d, deputy=deputy,
                names=["B product", "B notice", "B Polymers", "B resin", "B buyer", "B sector", order.get("po_number"), receipt.get("receipt_no"),
                       shipment.get("shipment_no"), ret.get("return_no")])


def _routes():
    for route in discover_routes(app):
        if getattr(route, "methods", None) and SWEPT.match(route.path) and "{" in route.path:
            for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
                yield method, route.path


def _fill(path, ids, foreign, kind_for):
    def value(match):
        name = match.group(1)
        if name in NAMED:
            return kind_for(path) if name == "kind" else NAMED[name]
        if name == "attachment_id":
            return foreign["attachment"]
        known = ids.get("notification_item_id" if (name == "item_id" and "/notifications/" in path) else name)
        return str(known) if (foreign["real"] and known) else str(uuid.uuid4())
    return re.sub(r"\{(\w+)\}", value, path)


def _kind_for(path):
    if "/shipping/directory/customers/" in path:
        return "contacts"
    return "carriers"


def test_every_identifier_route_answers_a_foreign_record_as_a_missing_one(world):
    client, ids, a = world["client"], world["ids"], world["a"]
    before = {path: client.get(API + path, headers=world["b"]).json() for path in world["reads"]}
    checked = []
    for method, path in _routes():
        attachment = world["files"]["return" if "/returns/" in path else "shipment"][1]
        foreign_url = API[:-7] + _fill(path, ids, {"real": True, "attachment": attachment}, _kind_for)
        missing_url = API[:-7] + _fill(path, ids, {"real": False, "attachment": str(uuid.uuid4())}, _kind_for)
        if foreign_url == missing_url:
            continue  # nothing of B's in this URL (a kind/list route): covered by the list and reference tests below
        kw = {} if method in ("GET", "DELETE") else {"json": BODY}
        if path.endswith("/attachments") and method == "POST":
            kw = {"data": {"kind": "photo"}, "files": {"file": ("x.png", png())}}
        foreign = client.request(method, foreign_url, headers=a, **kw)
        missing = client.request(method, missing_url, headers=a, **kw)
        assert foreign.status_code < 500, (method, path, foreign.status_code, foreign.text[:300])
        if 200 <= foreign.status_code < 300:  # only a list under an unknown parent may answer, and it must be empty
            assert foreign.json() in ([], {"items": [], "total": 0}), (method, path, foreign.text[:300])
        assert (foreign.status_code, foreign.json()) == (missing.status_code, missing.json()), (method, path, foreign.text[:300], missing.text[:300])
        for name in world["names"]:
            assert not name or name not in foreign.text, (method, path, name)
        checked.append((method, path))
    after = {path: client.get(API + path, headers=world["b"]).json() for path in world["reads"]}
    assert after == before  # B's records unchanged
    assert len(checked) >= 60, len(checked)


def test_b_files_cannot_be_downloaded_or_removed_by_a(world):
    client, a = world["client"], world["a"]
    for kind, (owner, attachment) in world["files"].items():
        base = f"{API}/shipping/{'shipments' if kind == 'shipment' else 'returns'}/{owner}/attachments/{attachment}"
        assert client.get(base, headers=a).status_code == 404
        assert client.delete(base, headers=a).status_code == 404
        assert client.get(base, headers=world["b"]).status_code == 200  # still there for B


def test_a_cannot_use_b_records_inside_its_own_documents(world):
    client, a, ids, db = world["client"], world["a"], world["ids"], world["db"]
    today = str(date.today())
    attempts = [
        ("/procurement/purchase-orders", dict(supplier_id=ids["supplier_id"], order_date=today, currency="SAR", tax_rate=15,
                                              lines=[dict(description="x", quantity="1", unit="kg", unit_price="1")])),
        ("/procurement/receipts", dict(supplier_id=ids["supplier_id"], receipt_date=today, lines=[dict(description="x", quantity="1", unit="kg")])),
        ("/shipping/shipments", dict(delivery_method="factory_delivery", shipment_date=today, customer_id=ids["customer_id"],
                                     lines=[dict(description="x", width_mm="5", thickness_mm="0.35", quantity="1", unit="roll", weight="1")])),
        ("/shipping/returns", dict(shipment_id=ids["shipment_id"], reason="quality_defect", lines=[])),
        ("/delegations", dict(delegator_user_id=str(world["d"]["user_a"].id), delegate_user_id=str(world["deputy"].id),
                              permission_code="procurement:purchase_orders:approve", effective_from=today,
                              effective_to=str(date.today() + timedelta(days=3)), reason="probe")),
    ]
    own = _login(client, world["d"]["user_a"].email)
    supplier_a = client.post(f"{API}/procurement/suppliers", headers=own, json=dict(name="A Polymers", category="raw_material")).json()
    attempts.append(("/procurement/purchase-orders", dict(supplier_id=supplier_a["id"], order_date=today, currency="SAR", tax_rate=15,
                                                          lines=[dict(material_id=ids["material_id"], quantity="1", unit="kg", unit_price="1")])))
    for path, body in attempts:
        r = client.post(API + path, headers=a, json=body)
        assert 400 <= r.status_code < 500, (path, r.status_code, r.text[:300])
        assert ids["supplier_id"] not in r.text or "supplier_id" in r.text, (path, r.text[:300])
    org_a = world["d"]["org_a"].id
    from app.procurement.infrastructure.models import GoodsReceipt, PurchaseOrder
    from app.shipping.infrastructure.models import Shipment
    for model in (PurchaseOrder, GoodsReceipt, Shipment):
        assert db.query(model).filter(model.organization_id == org_a).count() == 0, model.__name__


@pytest.mark.parametrize("path", ["/procurement/suppliers", "/procurement/materials", "/procurement/receipts",
                                  "/procurement/purchase-orders", "/shipping/shipments", "/shipping/returns",
                                  "/masterdata/lists", "/delegations", "/workforce-members"])
def test_lists_and_searches_never_show_b_records(world, path):
    client, d = world["client"], world["d"]
    headers = {**world["a"], "X-Organization-ID": str(d["org_b"].id)}
    for params in ({}, {"organization_id": str(d["org_b"].id)}, {"search": "B"}, {"q": "B"}):
        r = client.get(API + path, headers=headers, params=params)
        assert r.status_code in (200, 422), (path, params, r.status_code)
        for value in [*world["ids"].values(), *world["names"]]:
            assert not value or str(value) not in r.text, (path, params, value)


def test_every_swept_module_identifier_route_is_covered():
    """The guard: a new identifier route in these modules must be reachable by the sweep (a known parameter)."""
    known = set(NAMED) | {"attachment_id", "supplier_id", "material_id", "record_id", "receipt_id", "order_id", "shipment_id",
                          "return_id", "item_id", "delegation_id", "member_id", "customer_id", "announcement_id", "resource_id",
                          "product_id"}
    unknown = sorted({(m, p) for m, p in _routes() for name in re.findall(r"\{(\w+)\}", p) if name not in known})
    assert not unknown, f"Add these routes to the cross-tenant sweep: {unknown}"
