"""MD-003: classifications a department names are reference lists the organization manages; an item nothing uses is
deleted, one in use only deactivated; items the system writes itself are never deleted; a new organization starts with
every list's usual values."""
from sqlalchemy import func, select

from app.core.interfaces.reference_lists import seed_organization_lists
from app.foundation.domain.enums import OrganizationStatus
from app.foundation.infrastructure.models import Organization
from app.masterdata.domain import lists as L
from app.masterdata.infrastructure.models import ListItem
from app.procurement.infrastructure.models import Supplier
from tests.masterdata.test_reference_lists import ROOT, code, items, ml  # noqa: F401  (fixture chain)
from tests.commercial.test_customer_reports import env, preview, reports_env, result_env  # noqa: F401
from tests.commercial.test_quotation_document import doc_env  # noqa: F401

SUPPLIERS = "/api/v1/procurement/suppliers"


def test_an_unused_item_is_deleted_one_in_use_is_only_deactivated(ml):
    ml.client.post(f"{ROOT}/lists/supplier_category/standard")
    mistake = ml.client.post(f"{ROOT}/lists/supplier_category", json=dict(name_ar="قطع غيار", name_en="Spare parts")).json()
    assert mistake["uses"] == 0 and not mistake.get("protected")
    assert ml.client.delete(f"{ROOT}/lists/items/{mistake['id']}").json() == {"deleted": 1}
    assert "spare_parts" not in items(ml, "supplier_category")

    supplier = ml.client.post(SUPPLIERS, json=dict(name="Gulf Resins", category="packaging"))
    assert supplier.status_code == 201, supplier.text
    used = items(ml, "supplier_category")["packaging"]
    assert used["uses"] == 1
    refused = ml.client.delete(f"{ROOT}/lists/items/{used['id']}")
    assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "ITEM_IN_USE", "uses": 1})
    assert ml.client.patch(f"{ROOT}/lists/items/{used['id']}", json=dict(active=False)).json()["active"] is False


def test_a_category_must_be_an_active_item_of_the_organizations_list(ml):
    ml.client.post(f"{ROOT}/lists/supplier_category/standard")
    assert code(ml.client.post(SUPPLIERS, json=dict(name="Unknown kind", category="space_travel"))) == "CATEGORY_UNKNOWN"
    custom = ml.client.post(f"{ROOT}/lists/supplier_category", json=dict(name_ar="نقل", name_en="Transport")).json()
    assert ml.client.post(SUPPLIERS, json=dict(name="Fast Trucks", category=custom["key"])).status_code == 201


def test_items_the_system_writes_are_never_deleted(ml):
    ml.client.post(f"{ROOT}/lists/rejection_reason/standard")
    reasons = items(ml, "rejection_reason")
    assert reasons["out_of_spec"]["protected"] is True and reasons["critical_defect"]["protected"] is False
    assert code(ml.client.delete(f"{ROOT}/lists/items/{reasons['out_of_spec']['id']}")) == "ITEM_PROTECTED"


def test_a_country_with_cities_is_not_deleted(ml):
    ml.client.post(f"{ROOT}/lists/city/standard")
    assert code(ml.client.delete(f"{ROOT}/lists/items/{items(ml, 'country')['sa']['id']}")) == "ITEM_HAS_CHILDREN"


def test_a_text_list_counts_records_by_the_name_they_keep(ml):
    ml.client.post(f"{ROOT}/lists/workforce_skill/standard")
    assert ml.client.get(f"{ROOT}/lists/workforce_skill/legacy").json() == []  # nothing to map: they keep the name


def test_a_new_organization_starts_with_every_lists_usual_values(db):
    org = Organization(name="New Plant", code="new-plant", status=OrganizationStatus.ACTIVE, timezone="UTC")
    db.add(org); db.commit()
    seed_organization_lists(db, org.id)
    db.commit()
    counts = dict(db.execute(select(ListItem.list, func.count()).where(ListItem.organization_id == org.id).group_by(ListItem.list)).all())
    assert counts == {name: len(rows) for name, rows in L.STANDARD.items()}
    seed_organization_lists(db, org.id)  # nothing twice
    db.commit()
    assert db.scalar(select(func.count()).select_from(ListItem).where(ListItem.organization_id == org.id)) == sum(counts.values())
    assert not db.scalar(select(func.count()).select_from(Supplier))
