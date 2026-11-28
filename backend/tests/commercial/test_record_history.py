"""PR2 of the unified record history: commercial records keep who changed what (old → new), in the same transaction."""
import pytest
from sqlalchemy import func, select

from app.commercial.infrastructure.models import Customer
from app.foundation.infrastructure.models import TenantActivityLog
from tests.commercial.test_sales_order_lifecycle import API, accepted_quote, auth_headers, quote, s  # noqa: F401  (fixtures)

HISTORY = "/api/v1/record-history"


def history(s, kind, identity):
    r = s.get(f"{HISTORY}/{kind}/{identity}")
    assert r.status_code == 200, r.text
    return r.json()["items"]


def entry(items, action):
    return next(i for i in items if i["action"] == action)


def changed(item, field, line=None):
    return next(c for c in item["details"]["changes"] if c["field"] == field and c.get("line") == line)


def test_quote_records_creation_edits_lines_and_steps_with_reason(s, test_user):
    q = quote(s, notes="first")
    items = [{**i, "unit": "kg"} for i in q["items"]]
    items[0]["quantity"], items[0]["requested_spec_json"] = "1200", {"width_mm": 25}
    body = {"notes": "second", "items": [{k: i[k] for k in ("line_no", "product_type", "requested_spec_json", "quantity", "unit",
                                                             "unit_price")} for i in items[:1]]}
    assert s.patch(f"{API}/quotes/{q['id']}", body).status_code == 200
    assert s.post(f"{API}/quotes/{q['id']}/issue").status_code == 200
    assert s.post(f"{API}/quotes/{q['id']}/reject", {"reason": "Price too high"}).status_code == 200

    items = history(s, "quote", q["id"])
    assert [i["action"] for i in items][:2] == ["quote.rejected", "quote.issued"]
    created = entry(items, "quote.created")
    assert created["actor_name"] == test_user.full_name
    assert changed(created, "quantity", 2)["new"] == "500" and changed(created, "quantity", 2)["line_change"] == "added"
    updated = entry(items, "quote.updated")
    assert {k: changed(updated, "notes")[k] for k in ("old", "new")} == {"old": "first", "new": "second"}
    assert {k: changed(updated, "quantity", 1)[k] for k in ("old", "new")} == {"old": "1000", "new": "1200"}
    assert {k: changed(updated, "requested_spec_json.width_mm", 1)[k] for k in ("old", "new")} == {"old": 19, "new": 25}
    assert changed(updated, "quantity", 2)["line_change"] == "removed"
    rejected = entry(items, "quote.rejected")
    assert rejected["details"]["reason"] == "Price too high"
    assert {k: changed(rejected, "status")[k] for k in ("old", "new")} == {"old": "issued", "new": "rejected"}


def test_an_edit_that_changes_nothing_writes_nothing(s):
    q = quote(s, notes="same")
    before = len(history(s, "quote", q["id"]))
    assert s.patch(f"{API}/quotes/{q['id']}", {"notes": "same"}).status_code == 200
    assert len(history(s, "quote", q["id"])) == before


def test_sales_order_steps_and_deleted_draft_kept_under_customer(s):
    q = accepted_quote(s)
    order = s.post(f"{API}/quotes/{q['id']}/sales-order").json()
    assert s.patch(f"{API}/orders/{order['id']}", {"customer_reference": "PO-77"}).status_code == 200
    assert s.post(f"{API}/orders/{order['id']}/confirm").status_code == 200
    assert s.post(f"{API}/orders/{order['id']}/revise", {"reason": "Customer changed the width"}).status_code == 200
    items = history(s, "sales_order", order["id"])
    assert entry(items, "sales_order.created")["details"]["related"]["quote_number"] == q["quote_number"]
    assert changed(entry(items, "sales_order.created"), "quote")["new"] == q["quote_number"]
    assert changed(entry(items, "sales_order.updated"), "customer_reference")["new"] == "PO-77"
    confirmed = entry(items, "sales_order.confirmed")
    assert confirmed["actor_name"] == "Confirming Manager"
    revised = entry(items, "sales_order.revised")
    assert revised["details"]["reason"] == "Customer changed the width" and changed(revised, "revision")["new"] == 2

    draft = s.post(f"{API}/customers/{s.customer}/orders", {"order_date": "2026-06-09T10:00:00Z", "items": [
        {"line_no": 1, "product_type": "Steel Rod", "quantity": "100.00", "unit": "kg"}]})
    assert draft.status_code == 201, draft.text
    assert s.delete(f"{API}/orders/{draft.json()['id']}").status_code in (200, 204)
    gone = entry(history(s, "customer", s.customer), "sales_order.deleted")
    assert gone["details"]["related"]["subject_name"] == draft.json()["order_number"]
    assert s.get(f"{HISTORY}/sales_order/{draft.json()['id']}").status_code == 404


def test_customer_keeps_its_contacts_sites_interactions_and_follow_ups(s, test_user):
    assert s.patch(f"{API}/customers/{s.customer}", {"notes": "VIP"}).status_code == 200
    contact = s.post(f"{API}/customers/{s.customer}/directory/contacts", {"name": "Sara", "phone": "+966500000001"}).json()
    site = s.post(f"{API}/customers/{s.customer}/directory/sites",
                  {"name": "Main plant", "address": "Industrial 2", "contact_id": contact["id"]})
    assert site.status_code == 201, site.text
    interaction = s.post(f"{API}/customers/{s.customer}/interactions",
                         {"interaction_type": "call", "interaction_date": "2026-06-01T10:00:00Z", "subject": "Intro"}).json()
    assert s.patch(f"{API}/customers/{s.customer}/interactions/{interaction['id']}", {"subject": "Intro call"}).status_code == 200
    follow_up = s.post(f"{API}/customers/{s.customer}/follow-ups", {"due_date": "2026-07-01T10:00:00Z", "reason": "Send price"}).json()
    assert s.post(f"{API}/follow-ups/{follow_up['id']}/complete", {}).status_code == 200
    assert s.delete(f"{API}/follow-ups/{follow_up['id']}").status_code in (200, 204)

    items = history(s, "customer", s.customer)
    assert {k: changed(entry(items, "customer.updated"), "notes")[k] for k in ("old", "new")} == {"old": None, "new": "VIP"}
    created = entry(items, "customer.created")
    assert changed(created, "sales_owner")["new"] == test_user.full_name  # a person, never an id
    assert entry(items, "customer.contact_added")["details"]["related"]["subject_name"] == "Sara"
    assert changed(entry(items, "customer.site_added"), "contact")["new"] == "Sara"
    assert {k: changed(entry(items, "interaction.updated"), "subject")[k] for k in ("old", "new")} == {"old": "Intro", "new": "Intro call"}
    completed = entry(items, "followup.completed")
    assert {k: changed(completed, "status")[k] for k in ("old", "new")} == {"old": "pending", "new": "completed"}
    assert changed(entry(items, "followup.deleted"), "reason")["old"] == "Send price"


def test_sample_and_its_evaluations(s, db, test_org, test_user):
    from app.masterdata.infrastructure.models import Product
    db.add(Product(organization_id=test_org.id, code='PRD-H', key='industrial_adhesive', name_ar='Test product',
                   name_en='Test product', created_by_user_id=test_user.id))
    db.commit()
    sample = s.post(f"{API}/customers/{s.customer}/samples", {"sample_code": "SAMP-H", "product_type": "industrial_adhesive",
                                                             "request_date": "2026-06-09T10:00:00Z", "notes": "a"}).json()
    assert s.patch(f"{API}/samples/{sample['id']}", {"notes": "b"}).status_code == 200
    evaluation = s.post(f"{API}/samples/{sample['id']}/evaluations", {"evaluation_date": "2026-06-10T10:00:00Z",
        "result_status": "accepted", "comments": "ok", "next_action": "proceed_to_quote"}).json()
    assert s.patch(f"{API}/sample-evaluations/{evaluation['id']}", {"comments": "very good"}).status_code == 200
    assert s.delete(f"{API}/sample-evaluations/{evaluation['id']}").status_code == 204

    items = history(s, "sample", sample["id"])
    assert changed(entry(items, "sample.updated"), "notes")["new"] == "b"
    added = entry(items, "sample.evaluation_added")
    assert changed(added, "result_status")["new"] == "accepted" and changed(added, "status")["new"] == "evaluated"
    assert {k: changed(entry(items, "sample.evaluation_updated"), "comments")[k] for k in ("old", "new")} == {"old": "ok", "new": "very good"}
    assert changed(entry(items, "sample.evaluation_deleted"), "status")["new"] == "delivered"


def test_history_follows_the_records_visibility(s, db, monkeypatch, client):
    q = quote(s)
    for kind, identity in (("quote", q["id"]), ("customer", s.customer)):
        assert s.get(f"{HISTORY}/{kind}/{identity}").status_code == 200
    # An "own" reader does not see another sales owner's customer, nor its records' history (RBAC-002).
    customer = db.get(Customer, __import__("uuid").UUID(s.customer))
    customer.sales_owner_user_id = None
    db.commit()
    from app.core.interfaces.authorization_policy import AccessScope
    monkeypatch.setattr("app.commercial.application.visibility.resolve_effective_scope", lambda *a, **k: AccessScope.OWN)
    for kind, identity in (("quote", q["id"]), ("customer", s.customer)):
        r = s.get(f"{HISTORY}/{kind}/{identity}")
        assert r.status_code == 404 and r.json()["detail"]["code"] == "RECORD_HISTORY_UNAVAILABLE"
    assert client.get(f"{HISTORY}/quote/{q['id']}").status_code == 401


def test_failed_history_rolls_the_change_back(s, db, monkeypatch):
    q = quote(s, notes="kept")
    before = db.scalar(select(func.count()).select_from(TenantActivityLog))

    def broken(*args, **kwargs):
        raise RuntimeError("history unavailable")
    from app.core.interfaces.activity_log import get_registered_activity_logger
    monkeypatch.setattr(get_registered_activity_logger(), "log_activity_strict", broken)
    with pytest.raises(RuntimeError, match="history unavailable"):
        s.patch(f"{API}/quotes/{q['id']}", {"notes": "lost"})
    monkeypatch.undo()
    db.expire_all()
    assert s.get(f"{API}/quotes/{q['id']}").json()["notes"] == "kept"
    assert db.scalar(select(func.count()).select_from(TenantActivityLog)) == before
