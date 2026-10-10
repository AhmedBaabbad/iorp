"""MD-002: reference lists — sectors, opportunity sources, countries and cities: the usual values, a city's country,
choosing from the lists on customers, suppliers and shipments, mapping legacy texts, and printing names."""
from dataclasses import replace

import pytest
from sqlalchemy import select

from app.commercial.infrastructure.models import Customer
from app.masterdata.domain import permissions as MD
from app.procurement.domain import permissions as PR
from app.procurement.infrastructure.models import Supplier
from tests.commercial.test_customer_reports import env, preview, reports_env, result_env  # noqa: F401  (fixture chain)
from tests.commercial.test_quotation_document import doc_env  # noqa: F401

ROOT = "/api/v1/masterdata"
CUSTOMERS = "/api/v1/commercial/customers"


@pytest.fixture
def ml(doc_env):
    doc_env.ctx.auth_user.permissions |= set(MD.ALL) | set(PR.ALL) | {"commercial:customers:update"}
    doc_env.ctx.tenant = replace(doc_env.ctx.tenant, permissions=frozenset(doc_env.ctx.auth_user.permissions))
    return doc_env


def code(r):
    return r.json()["detail"]["code"]


def items(e, name):
    return {i["key"]: i for i in e.client.get(f"{ROOT}/lists", params={"list": name}).json()}


def test_the_usual_values_and_a_citys_country(ml):
    added = ml.client.post(f"{ROOT}/lists/city/standard").json()
    assert {"riyadh", "jeddah", "al_kharj"} <= {i["key"] for i in added} and all(i["parent_key"] == "sa" for i in added)
    assert items(ml, "country")["sa"]["name_ar"] == "المملكة العربية السعودية"  # its country came with it
    assert ml.client.post(f"{ROOT}/lists/city/standard").json() == []  # nothing twice
    assert code(ml.client.post(f"{ROOT}/lists/city", json=dict(name_ar="العلا", name_en="AlUla"))) == "PARENT_REQUIRED"
    assert code(ml.client.post(f"{ROOT}/lists/city", json=dict(name_ar="دبي", name_en="Dubai", parent_key="ae"))) == "PARENT_REQUIRED"
    city = ml.client.post(f"{ROOT}/lists/city", json=dict(name_ar="العلا", name_en="AlUla", parent_key="sa"))
    assert city.status_code == 201 and city.json()["key"] == "alula"
    assert code(ml.client.post(f"{ROOT}/lists/sector", json=dict(name_ar="التعدين", name_en="Mining", parent_key="sa"))) == "PARENT_NOT_ALLOWED"
    assert code(ml.client.post(f"{ROOT}/lists/city", json=dict(key="riyadh", name_ar="الرياض", name_en="Riyadh", parent_key="sa"))) == "ITEM_KEY_TAKEN"
    assert ml.client.post(f"{ROOT}/lists/colour", json=dict(name_ar="أحمر", name_en="Red")).status_code == 422
    r = ml.client.patch(f"{ROOT}/lists/items/{city.json()['id']}", json=dict(name_en="Al Ula", active=False)).json()
    assert (r["key"], r["name_en"], r["active"]) == ("alula", "Al Ula", False)


def test_once_a_list_has_items_a_customer_chooses_from_it(ml):
    customer = f"{CUSTOMERS}/{ml.customer.id}"
    assert ml.client.patch(customer, json=dict(sector="anything")).status_code == 200  # no sectors defined: free text
    ml.client.post(f"{ROOT}/lists/sector/standard")
    r = ml.client.patch(customer, json=dict(sector="cartons"))
    assert r.status_code == 400 and "not in the list" in r.json()["detail"]
    assert ml.client.patch(customer, json=dict(sector="packaging")).json()["sector"] == "packaging"
    ml.db.execute(Customer.__table__.update().where(Customer.id == ml.customer.id).values(sector="كرتون"))
    ml.db.commit()
    assert ml.client.patch(customer, json=dict(sector="كرتون", phone=None)).status_code == 200  # the stored text may stay
    assert ml.client.patch(customer, json=dict(city="جدة")).status_code == 200  # cities are still free (no city defined)


def test_legacy_texts_are_mapped_in_every_module(ml):
    ml.db.execute(Customer.__table__.update().where(Customer.id == ml.customer.id).values(city="الرياض"))
    ml.db.add(Supplier(organization_id=ml.org.id, supplier_code="SUP-9001", name="Gulf Polymers", category="raw_material", status="pending",
                       city="الرياض", country="السعودية", created_by_user_id=ml.user.id))
    ml.db.commit()
    ml.client.post(f"{ROOT}/lists/city/standard")
    row = next(r for r in ml.client.get(f"{ROOT}/lists/city/legacy").json() if r["value"] == "الرياض")
    assert row["uses"]["commercial"] >= 1 and row["uses"]["procurement"] == 1
    r = ml.client.post(f"{ROOT}/lists/city/legacy/map", json=dict(value="الرياض", item_id=items(ml, "city")["riyadh"]["id"]))
    assert r.status_code == 200, r.text
    assert r.json()["changed"]["procurement"] == 1 and r.json()["changed"]["shipping"] == 0
    assert ml.db.scalar(select(Supplier.city).where(Supplier.supplier_code == "SUP-9001")) == "riyadh"
    assert code(ml.client.post(f"{ROOT}/lists/city/legacy/map", json=dict(value="nowhere", item_id=items(ml, "city")["riyadh"]["id"]))) == \
        "LEGACY_VALUE_NOT_FOUND"
    # a supplier now chooses from the cities and countries
    sup = ml.client.post("/api/v1/procurement/suppliers", json=dict(name="Masterbatch Co", city="dammam"))
    assert sup.status_code == 201, sup.text
    assert code(ml.client.post("/api/v1/procurement/suppliers", json=dict(name="Other", city="Dammam City"))) == "LIST_VALUE_UNKNOWN"


def test_reports_print_the_names(ml):
    ml.client.post(f"{ROOT}/lists/city/standard")
    ml.client.post(f"{ROOT}/lists/sector/standard")
    ml.client.patch(f"{CUSTOMERS}/{ml.customer.id}", json=dict(city="al_kharj", sector="packaging"))
    ar = preview(ml, "directory", lang="ar")
    assert ar.status_code == 200, ar.text
    assert "الخرج" in ar.text and "التعبئة والتغليف" in ar.text and "al_kharj" not in ar.text
    assert "Al Kharj" in preview(ml, "directory", lang="en").text


def test_lists_need_their_permissions(ml):
    ml.ctx.auth_user.permissions = {MD.LISTS_READ}
    ml.ctx.tenant = replace(ml.ctx.tenant, permissions=frozenset(ml.ctx.auth_user.permissions))
    assert ml.client.get(f"{ROOT}/lists").status_code == 200
    assert ml.client.post(f"{ROOT}/lists/sector/standard").status_code == 403
    assert ml.client.get(f"{ROOT}/lists/sector/legacy").status_code == 403
