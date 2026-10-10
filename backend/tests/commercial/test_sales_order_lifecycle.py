"""SALES-001: quotation and sales order lifecycle, status history, and partial transfers to production demands."""
from uuid import uuid4

import pytest

from app.core.storage import LocalFileStorage
from app.foundation.infrastructure.models import UserRole
from app.foundation.infrastructure.organization_queries import FoundationOrganizationQueries

API = "/api/v1/commercial"
PROD = "/api/v1/production"


@pytest.fixture
def auth_headers(client, db, test_org, test_user):
    """A commercial manager who may also create production demands."""
    provider = FoundationOrganizationQueries(db, LocalFileStorage("uploads"))
    roles = provider._seed_roles(test_org, provider._get_or_create_permissions(test_org.id))
    db.add_all([UserRole(user_id=test_user.id, role_id=roles[code].id) for code in ("commercial_manager", "production_manager")])
    db.commit()
    resp = client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "Test1234!"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def s(client, auth_headers, test_user):
    class Session:
        def post(self, path, body=None):
            return client.post(path, json=body, headers=auth_headers)

        def patch(self, path, body):
            return client.patch(path, json=body, headers=auth_headers)

        def get(self, path):
            return client.get(path, headers=auth_headers)

        def delete(self, path):
            return client.delete(path, headers=auth_headers)

    session = Session()
    session.customer = session.post(f"{API}/customers", {"customer_code": "C-SO", "name": "Sales Order Co",
                                                        "sales_owner_user_id": str(test_user.id)}).json()["id"]
    return session


def quote(s, **extra):
    body = {"issue_date": "2026-06-09T10:00:00Z", "valid_until": "2026-07-09T10:00:00Z", "currency": "USD",
            "items": [{"line_no": 1, "product_type": "pp_strap", "requested_spec_json": {"width_mm": 19}, "quantity": "1000",
                       "unit": "kg", "unit_price": "2.50"},
                      {"line_no": 2, "product_type": "pp_strap", "requested_spec_json": {"width_mm": 12}, "quantity": "500",
                       "unit": "kg", "unit_price": "2.40"}], **extra}
    r = s.post(f"{API}/customers/{s.customer}/quotes", body)
    assert r.status_code == 201, r.text
    return r.json()


def accepted_quote(s):
    q = quote(s)
    assert s.post(f"{API}/quotes/{q['id']}/issue").status_code == 200
    return s.post(f"{API}/quotes/{q['id']}/accept").json()


def confirmed_order(s):
    q = accepted_quote(s)
    order = s.post(f"{API}/quotes/{q['id']}/sales-order").json()
    r = s.post(f"{API}/orders/{order['id']}/confirm")
    assert r.status_code == 200, r.text
    return r.json()


def test_quote_is_edited_only_as_a_draft_and_every_step_is_recorded(s):
    q = quote(s)
    assert q["status"] == "draft" and q["revision"] == 1 and q["allowed_actions"] == ["edit", "issue"]
    issued = s.post(f"{API}/quotes/{q['id']}/issue").json()
    assert issued["status"] == "issued" and set(issued["allowed_actions"]) == {"accept", "reject", "expire", "revise"}
    assert s.patch(f"{API}/quotes/{q['id']}", {"notes": "late change"}).json()["detail"] == "QUOTE_NOT_DRAFT"
    assert s.post(f"{API}/quotes/{q['id']}/revise", {"reason": " "}).status_code in (400, 422)
    revised = s.post(f"{API}/quotes/{q['id']}/revise", {"reason": "Customer asked for 15 mm"}).json()
    assert revised["status"] == "draft" and revised["revision"] == 2
    assert s.patch(f"{API}/quotes/{q['id']}", {"notes": "now allowed"}).status_code == 200
    s.post(f"{API}/quotes/{q['id']}/issue")
    done = s.post(f"{API}/quotes/{q['id']}/accept").json()
    assert done["status"] == "accepted" and done["allowed_actions"] == ["create_order"]
    assert [(h["action"], h["to_status"], h["revision"]) for h in done["history"]] == [
        ("create", "draft", 1), ("issue", "issued", 1), ("revise", "draft", 2), ("issue", "issued", 2), ("accept", "accepted", 2)]
    assert done["history"][2]["reason"] == "Customer asked for 15 mm" and done["history"][0]["actor_name"] == "Test User"
    assert s.post(f"{API}/quotes/{q['id']}/revise", {"reason": "too late"}).json()["detail"] == "QUOTE_INVALID_TRANSITION"
    assert s.patch(f"{API}/quotes/{q['id']}", {"notes": "x"}).json()["detail"] == "QUOTE_NOT_DRAFT"
    assert s.delete(f"{API}/quotes/{q['id']}").json()["detail"] == "QUOTE_ACCEPTED"


def test_rejecting_needs_a_reason(s):
    q = quote(s)
    s.post(f"{API}/quotes/{q['id']}/issue")
    assert s.post(f"{API}/quotes/{q['id']}/reject", {"reason": ""}).status_code in (400, 422)
    r = s.post(f"{API}/quotes/{q['id']}/reject", {"reason": "Price too high"}).json()
    assert r["status"] == "rejected" and r["allowed_actions"] == ["revise"]


def test_sales_order_is_copied_from_the_accepted_quote_only(s):
    q = quote(s)
    assert s.post(f"{API}/quotes/{q['id']}/sales-order").json()["detail"] == "ORDER_QUOTE_NOT_ACCEPTED"
    s.post(f"{API}/quotes/{q['id']}/issue")
    s.post(f"{API}/quotes/{q['id']}/accept")
    order = s.post(f"{API}/quotes/{q['id']}/sales-order")
    assert order.status_code == 201, order.text
    order = order.json()
    assert order["status"] == "draft" and order["quote_id"] == q["id"] and order["currency"] == "USD"
    assert [(i["line_no"], i["requested_spec_json"], i["quantity"], i["agreed_unit_price"]) for i in order["items"]] == [
        (1, {"width_mm": 19}, "1000.00", "2.50"), (2, {"width_mm": 12}, "500.00", "2.40")]
    assert s.post(f"{API}/quotes/{q['id']}/sales-order").json()["detail"].startswith("ORDER_EXISTS_FOR_QUOTE:")
    assert s.get(f"{API}/quotes/{q['id']}").json()["allowed_actions"] == []
    # The two documents are independent: editing the order's draft leaves the quotation as it was.
    items = [{**{k: i[k] for k in ("line_no", "product_type", "requested_spec_json", "unit", "agreed_unit_price")}, "quantity": "800"}
             for i in order["items"]]
    assert s.patch(f"{API}/orders/{order['id']}", {"items": items}).status_code == 200
    assert s.get(f"{API}/quotes/{q['id']}").json()["items"][0]["quantity"] == "1000.00"


def test_confirmed_order_is_locked(s):
    order = confirmed_order(s)
    assert order["confirmed_at"] and order["fulfilment"] == "none"
    assert set(order["allowed_actions"]) == {"transfer", "revise", "cancel"}
    r = s.patch(f"{API}/orders/{order['id']}", {"notes": "change"})
    assert r.status_code == 400 and r.json()["detail"] == "ORDER_LOCKED"
    assert s.post(f"{API}/orders/{order['id']}/confirm").json()["detail"] == "ORDER_INVALID_TRANSITION"
    assert s.post(f"{API}/orders/{order['id']}/revise", {"reason": "Quantity change"}).json()["revision"] == 2
    assert [h["action"] for h in s.get(f"{API}/orders/{order['id']}").json()["history"]] == ["create", "confirm", "revise"]


def test_direct_order_needs_the_customer_reference_and_a_currency_when_priced(s):
    body = {"order_date": "2026-06-09T10:00:00Z", "items": [{"line_no": 1, "product_type": "pp_strap", "quantity": "10", "unit": "kg"}]}
    order = s.post(f"{API}/customers/{s.customer}/orders", body).json()
    assert order["currency"] is None
    assert s.post(f"{API}/orders/{order['id']}/confirm").json()["detail"] == "ORDER_SOURCE_REQUIRED"
    s.patch(f"{API}/orders/{order['id']}", {"customer_reference": "PO-55"})
    assert s.post(f"{API}/orders/{order['id']}/confirm").json()["status"] == "confirmed"
    priced = s.post(f"{API}/customers/{s.customer}/orders", {**body, "customer_reference": "PO-56",
                                                             "items": [{**body["items"][0], "agreed_unit_price": "3"}]}).json()
    assert priced["currency"] == "SAR"  # the organization's default currency


def test_partial_transfers_to_production_never_exceed_the_order(s):
    order = confirmed_order(s)
    first, second = order["items"]
    lookup = s.get(f"{PROD}/demand-lookups/sales-orders?customer_id={s.customer}").json()
    assert [o["number"] for o in lookup] == [order["order_number"]]
    assert lookup[0]["lines"][0]["remaining_quantity"] == "1000.00"

    key = str(uuid4())
    body = {"sales_order_id": order["id"], "transfer_key": key, "lines": [{"order_item_id": first["id"], "quantity": "600"}]}
    demand = s.post(f"{PROD}/demands/from-sales-order", body)
    assert demand.status_code == 201, demand.text
    demand = demand.json()
    assert demand["sales_order"] == {"id": order["id"], "number": order["order_number"]}
    assert s.post(f"{PROD}/demands/from-sales-order", body).json()["id"] == demand["id"]  # a retry: the same demand

    too_much = {"sales_order_id": order["id"], "lines": [{"order_item_id": first["id"], "quantity": "401"}]}
    assert s.post(f"{PROD}/demands/from-sales-order", too_much).json()["detail"]["code"] == "quantity_exceeds_remaining"

    after = s.get(f"{API}/orders/{order['id']}").json()
    assert after["fulfilment"] == "partial" and after["transferred_quantities"][first["id"]] == "600.000"
    assert "revise" not in after["allowed_actions"] and "cancel" not in after["allowed_actions"]
    assert s.post(f"{API}/orders/{order['id']}/revise", {"reason": "x"}).json()["detail"] == "ORDER_HAS_PRODUCTION_HISTORY"

    detail = s.get(f"{PROD}/demands/{demand['id']}").json()
    line = detail["items"][0]
    assert line["source_order_item_id"] == first["id"] and line["target_spec_json"] == {"width_mm": 19}
    item_path = f"{PROD}/demands/{demand['id']}/items/{line['id']}"
    assert s.patch(item_path, {"target_spec_json": {"width_mm": 25}}).json()["detail"]["code"] == "sales_order_lines_locked"
    assert s.patch(item_path, {"required_quantity": "1001"}).json()["detail"]["code"] == "quantity_exceeds_remaining"
    assert s.patch(item_path, {"required_quantity": "1000"}).status_code == 200
    assert s.post(f"{PROD}/demands/{demand['id']}/items", {"required_quantity": "5", "unit": "kg"}).json()["detail"]["code"] == \
        "sales_order_lines_locked"

    rest = {"sales_order_id": order["id"], "lines": [{"order_item_id": second["id"], "quantity": "500"}]}
    assert s.post(f"{PROD}/demands/from-sales-order", rest).status_code == 201
    full = s.get(f"{API}/orders/{order['id']}").json()
    assert full["fulfilment"] == "full" and full["allowed_actions"] == []
    assert s.get(f"{PROD}/demand-lookups/sales-orders?customer_id={s.customer}").json() == []

    # Cancelling a demand gives its quantity back; reopening it takes it again only if still free.
    assert s.post(f"{PROD}/demands/{demand['id']}/status", {"status": "cancelled"}).status_code == 200
    again = {"sales_order_id": order["id"], "lines": [{"order_item_id": first["id"], "quantity": "300"}]}
    assert s.post(f"{PROD}/demands/from-sales-order", again).status_code == 201
    r = s.post(f"{PROD}/demands/{demand['id']}/status", {"status": "draft"})
    assert r.json()["detail"]["code"] == "quantity_exceeds_remaining"


def test_a_draft_order_cannot_go_to_production(s):
    q = accepted_quote(s)
    order = s.post(f"{API}/quotes/{q['id']}/sales-order").json()
    body = {"sales_order_id": order["id"], "lines": [{"order_item_id": order["items"][0]["id"], "quantity": "1"}]}
    assert s.post(f"{PROD}/demands/from-sales-order", body).json()["detail"]["code"] == "sales_order_not_confirmed"


def test_a_catalogue_product_line_follows_its_specification_template(s):
    strap = {"key": "pp_strap", "name_ar": "شريط", "name_en": "PP Strap", "kind": "finished", "properties": [
        {"key": "width_mm", "name_ar": "العرض", "name_en": "Width", "kind": "number", "unit": "mm", "required": True}]}
    assert s.post("/api/v1/masterdata/products", strap).status_code == 201
    body = {"order_date": "2026-06-09T10:00:00Z", "customer_reference": "PO-1",
            "items": [{"line_no": 1, "product_type": "pp_strap", "requested_spec_json": {"width_mm": "wide"}, "quantity": "10", "unit": "kg"}]}
    assert s.post(f"{API}/customers/{s.customer}/orders", body).json()["detail"] == "ORDER_SPEC_INVALID:width_mm"
    body["items"][0]["requested_spec_json"] = {"width_mm": 19}
    assert s.post(f"{API}/customers/{s.customer}/orders", body).status_code == 201
