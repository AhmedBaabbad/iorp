"""PROD-PLAN-001 acceptance cases T01–T44 and regression boundaries."""
from copy import deepcopy
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import pytest
from sqlalchemy import select, text
from app.main import app
from app.dependencies import get_current_user
from app.core.tenancy import TenantContext
from app.core.utils import utc_now
from app.commercial.infrastructure.models import Customer, Quote, QuoteItem
from app.foundation.infrastructure.models import Organization
from app.production.infrastructure.models import ProductionDemand

ROOT = "/api/v1/production"
PERMISSIONS = frozenset([f"production:demands:{a}" for a in ("read", "create", "update", "delete", "release", "cancel")] + ["production:planning:read", "production:planning:sequence", "commercial:customers:read", "commercial:customers:update", "commercial:customers:delete"])
ITEM = {"product_type": "pp_strap", "required_quantity": "500", "unit": "kg", "target_spec_json": {"width_mm": 12, "thickness_mm": .6, "color": "blue"}}


@pytest.fixture
def env(client, db, test_org, test_user):
    org2 = Organization(name="Other", code="other", timezone="UTC")
    db.add(org2); db.flush()
    customers = [Customer(organization_id=o.id, customer_code=f"C-{n}", name=f"Customer {n}") for n, o in enumerate((test_org, test_org, org2))]
    db.add_all(customers); db.flush()
    quotes = []
    for n, customer in enumerate(customers):
        quote = Quote(organization_id=customer.organization_id, customer_id=customer.id, quote_number=f"Q-{n}", issue_date=utc_now(), valid_until=utc_now(), currency="USD", subtotal_amount=10, discount_amount=0, tax_amount=0, total_amount=10, created_by_user_id=test_user.id)
        quote.items = [QuoteItem(line_no=1, product_type="pp_strap", requested_spec_json=deepcopy(ITEM["target_spec_json"]), quantity=500, unit="kg", unit_price=1, line_total=500)]
        db.add(quote); quotes.append(quote)
    db.commit()
    ctx = SimpleNamespace(user=SimpleNamespace(is_organization_root=False), auth_user=SimpleNamespace(permissions=PERMISSIONS), tenant=TenantContext(test_user.id, test_org.id, permissions=PERMISSIONS))
    app.dependency_overrides[get_current_user] = lambda: ctx
    def create(**kwargs):
        payload = {"customer_id": str(customers[0].id), "items": [deepcopy(ITEM)], **kwargs}
        return client.post(f"{ROOT}/demands", json=payload)
    return SimpleNamespace(client=client, db=db, org=test_org, org2=org2, customers=customers, quotes=quotes, ctx=ctx, create=create)


def demand(e, **kwargs):
    response = e.create(**kwargs)
    assert response.status_code == 201, response.text
    return response.json()


def status(e, d, value):
    return e.client.post(f"{ROOT}/demands/{d['id']}/status", json={"status": value})


def detail(e, d):
    return e.client.get(f"{ROOT}/demands/{d['id']}").json()


def test_t01_customer_required(env):
    assert env.client.post(f"{ROOT}/demands", json={"items": [ITEM]}).status_code == 400

def test_t02_cross_org_customer(env):
    assert env.create(customer_id=str(env.customers[2].id)).status_code == 404

def test_t03_missing_customer(env):
    assert env.create(customer_id=str(uuid4())).status_code == 404

def test_t04_quote_optional(env):
    assert demand(env)["quote"] is None

def test_t05_valid_quote(env):
    assert demand(env, quote_id=str(env.quotes[0].id))["quote"]["id"] == str(env.quotes[0].id)

def test_t06_quote_customer_mismatch(env):
    assert env.create(quote_id=str(env.quotes[1].id)).status_code == 400

def test_t07_cross_org_quote(env):
    assert env.create(quote_id=str(env.quotes[2].id)).status_code == 404

def test_t08_snapshot(env):
    d = demand(env, quote_id=str(env.quotes[0].id), items=[])
    r = env.client.post(f"{ROOT}/demands/{d['id']}/import-quote-items")
    assert r.status_code == 200 and r.json()["imported_count"] == 1
    assert r.json()["items"][0]["target_spec_json"] == ITEM["target_spec_json"]
    assert r.json()["items"][0]["id"] != str(env.quotes[0].items[0].id)

def test_t09_quote_edits_independent(env):
    d = demand(env, quote_id=str(env.quotes[0].id), items=[])
    env.client.post(f"{ROOT}/demands/{d['id']}/import-quote-items")
    env.quotes[0].items[0].requested_spec_json = {"width_mm": 99}
    env.quotes[0].items[0].quantity = 99
    env.db.commit()
    assert detail(env, d)["items"][0]["target_spec_json"]["width_mm"] == 12
    assert float(detail(env, d)["items"][0]["required_quantity"]) == 500

def test_t10_import_without_quote(env):
    d = demand(env)
    assert env.client.post(f"{ROOT}/demands/{d['id']}/import-quote-items").status_code == 400

def test_t11_generated_number(env):
    assert demand(env)["demand_number"] == f"PD-{date.today().year}-000001"

def test_t12_scoped_sequence(env):
    assert demand(env)["demand_number"].endswith("000001")
    assert demand(env)["demand_number"].endswith("000002")
    env.ctx.tenant = TenantContext(env.ctx.tenant.user_id, env.org2.id, permissions=PERMISSIONS)
    assert demand(env, customer_id=str(env.customers[2].id))["demand_number"].endswith("000001")

def test_t13_list(env):
    demand(env)
    r = env.client.get(f"{ROOT}/demands")
    assert r.status_code == 200 and r.json()["total"] == 1

def test_t14_detail_items(env):
    assert detail(env, demand(env))["items"][0]["unit"] == "kg"

def test_t15_update_draft(env):
    d = demand(env)
    r = env.client.patch(f"{ROOT}/demands/{d['id']}", json={"notes": "Updated", "items": [{**ITEM, "unit": "roll"}]})
    assert r.status_code == 200 and r.json()["notes"] == "Updated"
    assert detail(env, d)["items"][0]["unit"] == "roll"

def test_t16_delete_draft(env):
    d = demand(env)
    assert env.client.delete(f"{ROOT}/demands/{d['id']}").status_code == 200
    assert env.client.get(f"{ROOT}/demands/{d['id']}").status_code == 404

def test_t17_delete_non_draft(env):
    d = demand(env); status(env, d, "ready_for_planning")
    assert env.client.delete(f"{ROOT}/demands/{d['id']}").status_code == 409

def test_t18_mark_ready(env):
    assert status(env, demand(env), "ready_for_planning").status_code == 200

def test_t19_cancel(env):
    assert status(env, demand(env), "cancelled").status_code == 200

def test_t20_planned_via_partial(env):
    d = demand(env); status(env, d, "ready_for_planning")
    assert status(env, d, "planned").status_code == 409
    assert status(env, d, "partially_planned").status_code == 409
    assert status(env, d, "planned").status_code == 409

def test_t21_replan(env):
    d = demand(env)
    assert status(env, d, "ready_for_planning").status_code == 200
    assert status(env, d, "partially_planned").status_code == 409
    assert status(env, d, "planned").status_code == 409

def test_t22_reopen(env):
    d = demand(env); status(env, d, "cancelled")
    assert status(env, d, "draft").status_code == 200

def test_t23_invalid_transition(env):
    assert status(env, demand(env), "planned").status_code == 409

def test_t24_planning_only(env):
    demand(env); ready = demand(env); status(env, ready, "ready_for_planning")
    partial = demand(env); status(env, partial, "ready_for_planning"); status(env, partial, "partially_planned")
    data = env.client.get(f"{ROOT}/planning/demands").json()
    assert data["total"] == 2 and {d["id"] for d in data["items"]} == {ready["id"], partial["id"]}

def test_t25_filters(env):
    d = demand(env, priority="urgent", requested_delivery_date="2026-12-01"); status(env, d, "ready_for_planning")
    for query, count in [(f"customer_id={env.customers[0].id}", 1), ("priority=low", 0), ("requested_delivery_from=2026-11-01&requested_delivery_to=2026-12-31", 1), ("requested_delivery_from=2027-01-01", 0), ("product_type=pp_strap", 1), ("search=Customer%200", 1), ("search=absent", 0)]:
        assert env.client.get(f"{ROOT}/planning/demands?{query}").json()["total"] == count

def test_t26_ordering(env):
    low = demand(env, priority="low", requested_delivery_date="2026-10-01")
    late = demand(env, priority="urgent", requested_delivery_date="2026-12-01")
    early = demand(env, priority="urgent", requested_delivery_date="2026-11-01")
    for d in (low, late, early): status(env, d, "ready_for_planning")
    assert [r["id"] for r in env.client.get(f"{ROOT}/planning/demands").json()["items"]] == [early["id"], late["id"], low["id"]]
    env.client.post(f"{ROOT}/planning/demands/{low['id']}/reorder", json={"new_position": 1})
    assert env.client.get(f"{ROOT}/planning/demands").json()["items"][0]["id"] == low["id"]

def test_t27_reorder(env):
    ds = [demand(env) for _ in range(3)]
    for d in ds: status(env, d, "ready_for_planning")
    r = env.client.post(f"{ROOT}/planning/demands/{ds[2]['id']}/reorder", json={"new_position": 1})
    assert r.status_code == 200
    items = env.client.get(f"{ROOT}/planning/demands").json()["items"]
    assert [d["planning_sequence"] for d in items] == [1, 2, 3]
    assert items[0]["id"] == ds[2]["id"]

def test_t28_reorder_permission(env):
    d = demand(env); env.ctx.auth_user.permissions = PERMISSIONS - {"production:planning:sequence"}
    assert env.client.post(f"{ROOT}/planning/demands/{d['id']}/reorder", json={"new_position": 1}).status_code == 403

def test_t29_org_isolation(env):
    d = demand(env); env.ctx.tenant = TenantContext(env.ctx.tenant.user_id, env.org2.id)
    assert env.client.get(f"{ROOT}/demands/{d['id']}").status_code == 404
    assert env.client.get(f"{ROOT}/demands").json()["total"] == 0
    assert env.client.patch(f"{ROOT}/demands/{d['id']}", json={"notes": "wrong"}).status_code == 404

def test_t30_cross_org_import(env):
    assert env.client.get(f"{ROOT}/demand-lookups/quotes/{env.quotes[2].id}/items?customer_id={env.customers[0].id}").status_code == 404

def test_t31_scope_not_accepted(env):
    assert env.create(organization_id=str(env.org2.id)).status_code == 400
    assert env.create(demand_number="MANUAL").status_code == 400

def test_t32_read_permission(env):
    env.ctx.auth_user.permissions = PERMISSIONS - {"production:demands:read"}
    assert env.client.get(f"{ROOT}/demands").status_code == 403

def test_t33_create_permission(env):
    env.ctx.auth_user.permissions = PERMISSIONS - {"production:demands:create"}
    assert env.create().status_code == 403

def test_t34_sequence_permission(env):
    env.ctx.auth_user.permissions = frozenset({"production:planning:read"})
    assert env.client.post(f"{ROOT}/planning/demands/{uuid4()}/reorder", json={"new_position": 1}).status_code == 403

def test_t35_arbitrary_json(env):
    spec = {"nested": {"values": [1, True, None]}, "material": "custom"}
    assert detail(env, demand(env, items=[{**ITEM, "target_spec_json": spec}]))["items"][0]["target_spec_json"] == spec

def test_t36_pp_specs(env):
    assert detail(env, demand(env))["items"][0]["target_spec_json"] == ITEM["target_spec_json"]

def test_t37_other_industry(env):
    spec = {"flute": "B", "length_mm": 600}
    assert detail(env, demand(env, items=[{**ITEM, "product_type": "carton_box", "target_spec_json": spec}]))["items"][0]["target_spec_json"] == spec

def test_t38_customer_deletion(env):
    d = demand(env)
    c = env.customers[0]
    impact = env.client.get(f"/api/v1/commercial/customers/{c.id}/deletion-impact")
    assert impact.status_code == 200 and impact.json()["production_demands"] == 1 and impact.json()["is_blocked"]
    assert env.client.delete(f"/api/v1/commercial/customers/{c.id}").status_code == 400
    assert env.client.patch(f"/api/v1/commercial/customers/{c.id}", json={"status": "inactive"}).status_code == 400
    status(env, d, "cancelled")
    assert env.client.patch(f"/api/v1/commercial/customers/{c.id}", json={"status": "inactive"}).status_code == 200

def test_t39_quote_delete_set_null(env):
    env.db.commit(); env.db.execute(text("PRAGMA foreign_keys=ON"))
    d = demand(env, quote_id=str(env.quotes[0].id))
    env.db.delete(env.quotes[0]); env.db.commit(); env.db.expire_all()
    assert detail(env, d)["quote"] is None and len(detail(env, d)["items"]) == 1

def test_t40_add_item(env):
    d = demand(env)
    r = env.client.post(f"{ROOT}/demands/{d['id']}/items", json=ITEM)
    assert r.status_code == 201 and r.json()["line_no"] == 2

@pytest.mark.parametrize("quantity", [0, -1, "NaN", "0.0001"])
def test_t41_positive_quantity(env, quantity):
    assert env.create(items=[{**ITEM, "required_quantity": quantity}]).status_code == 400

def test_t42_unique_line(env):
    assert env.create(items=[{**ITEM, "line_no": 1}, {**ITEM, "line_no": 1}]).status_code == 409

def test_t43_no_order_field():
    assert "commercial_order_id" not in ProductionDemand.__table__.columns
    assert "production_order_id" not in ProductionDemand.__table__.columns

def test_t44_no_order_dependency():
    root = Path(__file__).parents[1] / "app" / "production"
    for path in (root / "application/demand_service.py", root / "api/routes_demands.py", root / "infrastructure/demand_repository.py"):
        source = path.read_text(encoding="utf-8")
        assert "CommercialOrder" not in source and "app.commercial" not in source

def test_atomic_update_rollback(env):
    d = demand(env)
    r = env.client.patch(f"{ROOT}/demands/{d['id']}", json={"items": [{**ITEM, "line_no": 1}, {**ITEM, "line_no": 1}]})
    assert r.status_code == 409
    env.db.rollback()
    assert len(detail(env, d)["items"]) == 1

def test_null_patch_and_edit_guards(env):
    d = demand(env)
    assert env.client.patch(f"{ROOT}/demands/{d['id']}", json={"customer_id": None}).status_code == 400
    status(env, d, "cancelled")
    assert env.client.post(f"{ROOT}/demands/{d['id']}/items", json=ITEM).status_code == 409

def test_item_patch_delete_and_parent_scope(env):
    d = demand(env); other = demand(env)
    item = detail(env, d)["items"][0]
    assert env.client.patch(f"{ROOT}/demands/{other['id']}/items/{item['id']}", json={"unit": "m"}).status_code == 404
    assert env.client.patch(f"{ROOT}/demands/{d['id']}/items/{item['id']}", json={"unit": "m"}).status_code == 200
    assert env.client.delete(f"{ROOT}/demands/{d['id']}/items/{item['id']}").status_code == 200

def test_empty_cannot_be_ready(env):
    assert status(env, demand(env, items=[]), "ready_for_planning").status_code == 400


def test_list_shows_only_chosen_statuses_and_counts_the_hidden(env):
    draft, ready, cancelled = demand(env), demand(env), demand(env)
    status(env, ready, "ready_for_planning")
    status(env, cancelled, "cancelled")
    body = env.client.get(f"{ROOT}/demands", params=[("statuses", "draft"), ("statuses", "ready_for_planning")]).json()
    assert {d["id"] for d in body["items"]} == {draft["id"], ready["id"]}
    assert body["total"] == 2 and body["hidden_by_status"] == 1
    # Other filters still apply before counting what is hidden.
    body = env.client.get(f"{ROOT}/demands", params=[("statuses", "draft"), ("search", draft["demand_number"])]).json()
    assert body["total"] == 1 and body["hidden_by_status"] == 0
    # Without statuses nothing is hidden.
    body = env.client.get(f"{ROOT}/demands").json()
    assert body["total"] == 3 and body["hidden_by_status"] is None
    assert env.client.get(f"{ROOT}/demands", params={"statuses": "bogus"}).status_code in (400, 422)
