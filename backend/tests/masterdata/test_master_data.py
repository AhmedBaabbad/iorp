"""MD-001: master data — products with their specification templates, choosing product types from the list in every
module, mapping legacy product types, the VAT rate and default currency, and the module boundaries."""
import ast
from dataclasses import replace
from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.commercial.infrastructure.models import QuoteItem
from app.masterdata.domain import permissions as MD
from app.production.infrastructure.models import ProductionDemand, ProductionDemandItem
from app.quality.infrastructure.models import QualitySpecification
from tests.commercial.test_customer_reports import env, reports_env, result_env  # noqa: F401  (fixture chain)
from tests.commercial.test_quotation_document import QUOTES, create_quote, doc_env, html  # noqa: F401

ROOT = "/api/v1/masterdata"
STRAP = dict(name_ar="شريط تربيط PP", name_en="PP Strap", kind="finished", default_unit="roll", properties=[
    dict(key="width_mm", name_ar="العرض", name_en="Width", kind="number", unit="mm", required=True),
    dict(key="thickness_mm", name_ar="السماكة", name_en="Thickness", kind="number", unit="mm"),
    dict(key="color", name_ar="اللون", name_en="Colour", kind="choice", options=[
        dict(value="white", label_ar="أبيض", label_en="White"), dict(value="black", label_ar="أسود", label_en="Black")]),
])


@pytest.fixture
def md(doc_env):
    doc_env.ctx.auth_user.permissions |= set(MD.ALL)
    doc_env.ctx.tenant = replace(doc_env.ctx.tenant, permissions=frozenset(doc_env.ctx.auth_user.permissions))
    return doc_env


def product(e, **over):
    r = e.client.post(f"{ROOT}/products", json={**STRAP, **over})
    assert r.status_code == 201, r.text
    return r.json()


def code(r):
    return r.json()["detail"]["code"]


def test_a_product_has_a_fixed_key_and_a_specification_template(md):
    p = product(md)
    assert (p["code"], p["key"], p["name_en"], p["default_unit"]) == ("PRD-0001", "pp_strap", "PP Strap", "roll")
    assert [q["key"] for q in p["properties"]] == ["width_mm", "thickness_mm", "color"] and p["properties"][2]["options"][0]["label_ar"] == "أبيض"
    assert code(md.client.post(f"{ROOT}/products", json=STRAP)) == "PRODUCT_KEY_TAKEN"
    assert code(md.client.post(f"{ROOT}/products", json={**STRAP, "key": "PP Strap"})) == "PRODUCT_KEY_INVALID"
    bad = [dict(key="color", name_ar="لون", name_en="Colour", kind="choice")]
    assert code(md.client.post(f"{ROOT}/products", json={**STRAP, "key": "film", "properties": bad})) == "OPTIONS_REQUIRED"
    dup = [STRAP["properties"][0], STRAP["properties"][0]]
    assert code(md.client.post(f"{ROOT}/products", json={**STRAP, "key": "film", "properties": dup})) == "PROPERTY_KEY_DUPLICATE"
    assert md.client.patch(f"{ROOT}/products/{p['id']}", json=dict(key="x")).status_code == 422  # the key never changes
    p = md.client.patch(f"{ROOT}/products/{p['id']}", json=dict(name_ar="أشرطة تربيط PP", active=False)).json()
    assert p["key"] == "pp_strap" and p["name_ar"] == "أشرطة تربيط PP" and p["active"] is False
    assert md.client.get(f"{ROOT}/products", params=dict(active_only=True)).json() == []


def test_once_products_exist_a_product_type_is_chosen_from_the_list(md):
    assert create_quote(md)["items"][0]["product_type"] == "strap"  # no product defined yet: nothing enforced
    product(md)
    r = md.client.post(f"{QUOTES}/customers/{md.customer.id}/quotes", json=dict(
        issue_date="2026-10-05T00:00:00Z", valid_until="2026-10-12T00:00:00Z", currency="SAR", tax_rate="15",
        items=[dict(line_no=1, product_type="strap", quantity="10", unit="roll", unit_price="5")]))
    assert r.status_code == 400 and "product list" in r.json()["detail"]
    q = create_quote(md, items=[dict(line_no=1, product_type="pp_strap", requested_spec_json={"width_mm": 19, "color": "white"},
                                     quantity="10", unit="roll", unit_price="5")])
    assert q["items"][0]["product_type"] == "pp_strap"
    old = create_quote(md, items=[dict(line_no=1, product_type="pp_strap", quantity="1", unit="roll", unit_price="5")])
    md.db.execute(QuoteItem.__table__.update().where(QuoteItem.quote_id == UUID(old["id"])).values(product_type="legacy text"))
    md.db.commit()
    keep = md.client.patch(f"{QUOTES}/quotes/{old['id']}", json=dict(items=[dict(line_no=1, product_type="legacy text", quantity="2", unit="roll",
                                                                                 unit_price="5")]))
    assert keep.status_code == 200, keep.text  # a value the quotation already stores may stay on it


def test_the_quotation_prints_the_product_name_and_labelled_specification(md):
    product(md)
    q = create_quote(md, items=[dict(line_no=1, product_type="pp_strap", requested_spec_json={"width_mm": 19, "thickness_mm": 0.85, "color": "white"},
                                     quantity="10", unit="roll", unit_price="5")])
    assert "شريط تربيط PP — 19 مم × 0.85 مم × أبيض" in html(md, q, "ar")  # the name, then the template's order and labels
    assert "PP Strap — 19 mm × 0.85 mm × White" in html(md, q, "en")


def test_legacy_product_types_are_mapped_by_each_module(md):
    create_quote(md, items=[dict(line_no=1, product_type="اشرطة تربيط ", quantity="1", unit="roll", unit_price="5")])
    demand = ProductionDemand(organization_id=md.org.id, demand_number=f"PD-{uuid4().hex[:6]}", customer_id=md.customer.id, request_date=date.today(),
                              created_by_user_id=md.user.id)
    md.db.add(demand)
    md.db.flush()
    md.db.add(ProductionDemandItem(production_demand_id=demand.id, line_no=1, product_type="اشرطة تربيط ", required_quantity=5, unit="roll"))
    md.db.add(QualitySpecification(organization_id=md.org.id, code="SPEC-1", revision=1, title="Strap", product_type="pp_strap", status="active",
                                   created_by_user_id=md.user.id))
    md.db.commit()
    legacy = md.client.get(f"{ROOT}/products/legacy").json()
    row = next(r for r in legacy if r["value"] == "اشرطة تربيط ")
    assert row["uses"] == {"commercial": 1, "production": 1} and row["total"] == 2
    assert any(r["value"] == "pp_strap" for r in legacy)  # used but not a product yet
    p = product(md)
    assert not any(r["value"] == "pp_strap" for r in md.client.get(f"{ROOT}/products/legacy").json())  # now a product
    r = md.client.post(f"{ROOT}/products/legacy/map", json=dict(value="اشرطة تربيط ", product_id=p["id"]))
    assert r.status_code == 200, r.text
    assert r.json()["changed"] == {"commercial": 1, "production": 1, "quality": 0, "procurement": 0}
    assert md.db.scalar(select(ProductionDemandItem.product_type).where(ProductionDemandItem.production_demand_id == demand.id)) == "pp_strap"
    assert code(md.client.post(f"{ROOT}/products/legacy/map", json=dict(value="nothing", product_id=p["id"]))) == "LEGACY_VALUE_NOT_FOUND"


def test_vat_rate_and_default_currency(md):
    s = md.client.get(f"{ROOT}/settings").json()
    assert (s["vat_rate"], s["default_currency"]) == ("15.00", "SAR")
    s = md.client.patch(f"{ROOT}/settings", json=dict(vat_rate="5", default_currency="USD")).json()
    assert (s["vat_rate"], s["default_currency"]) == ("5.00", "USD")
    assert md.client.patch(f"{ROOT}/settings", json=dict(default_currency="EUR")).status_code == 422
    r = md.client.post(f"{QUOTES}/customers/{md.customer.id}/quotes", json=dict(
        issue_date="2026-10-05T00:00:00Z", valid_until="2026-10-12T00:00:00Z", currency="SAR", tax_rate="15",
        items=[dict(line_no=1, product_type="strap", quantity="10", unit="roll", unit_price="5")]))
    assert r.status_code == 400 and "5%" in r.json()["detail"]  # the organization's rate is now 5 %
    assert create_quote(md, tax_rate="5")["tax_rate"] in ("5.00", "5", 5)
    assert create_quote(md, tax_rate="0")


def test_permissions(md):
    p = product(md)
    md.ctx.auth_user.permissions = {MD.PRODUCTS_READ}
    md.ctx.tenant = replace(md.ctx.tenant, permissions=frozenset(md.ctx.auth_user.permissions))
    assert md.client.get(f"{ROOT}/products").json()[0]["actions"] == []
    assert md.client.patch(f"{ROOT}/products/{p['id']}", json=dict(name_ar="x")).status_code == 403
    assert md.client.get(f"{ROOT}/products/legacy").status_code == 403
    assert md.client.patch(f"{ROOT}/settings", json=dict(vat_rate="10")).status_code == 403


def test_master_data_imports_no_module_and_no_module_imports_it():
    app_root = Path(__file__).resolve().parents[2] / "app"
    def imports(folder):
        found = set()
        for path in folder.rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.ImportFrom) and node.module:
                    found.add(node.module)
        return found
    others = ("app.commercial", "app.production", "app.quality", "app.shipping", "app.procurement", "app.foundation", "app.workforce", "app.platform")
    assert sorted(m for m in imports(app_root / "masterdata") if m.startswith(others)) == []
    for module in ("commercial", "production", "quality", "procurement", "shipping"):
        assert not [m for m in imports(app_root / module) if m.startswith("app.masterdata")], module
    from app.masterdata.infrastructure import models
    tables = [c.__tablename__ for c in vars(models).values() if isinstance(c, type) and hasattr(c, "__tablename__") and c.__module__ == models.__name__]
    assert tables and all(t.startswith("masterdata_") for t in tables)
