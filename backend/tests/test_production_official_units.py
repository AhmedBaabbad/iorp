"""Official units at create/update boundaries, including unchanged historical values."""
from datetime import date
from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.production.api.schemas import ProductionOrderCreate, ProductionOrderUpdate, ProductionOrderItemCreate, ProductionOrderItemUpdate
from app.production.api.demand_schemas import CreateDemandItemRequest, UpdateDemandItemRequest, ReplaceDemandItemRequest
from tests.test_production_demands import env as demand_env, demand, detail, ROOT, ITEM
from app.production.infrastructure.models import ProductionDemandItem
from uuid import UUID


@pytest.mark.parametrize("schema,payload", [
    (CreateDemandItemRequest, dict(required_quantity="1")),
    (ProductionOrderItemCreate, dict(line_no=1, planned_quantity="1")),
    (ProductionOrderCreate, dict(work_center_id=uuid4(), product_type="film", planned_quantity="1", planned_start_date=date(2026, 1, 1), planned_end_date=date(2026, 1, 2))),
])
def test_create_requires_official_symbol(schema, payload):
    with pytest.raises(ValidationError, match="UNIT_UNKNOWN"):
        schema(**payload, unit="pcs")
    assert schema(**payload, unit="piece").unit == "piece"


@pytest.mark.parametrize("schema,payload", [
    (UpdateDemandItemRequest, {}), (ProductionOrderUpdate, {}),
    (ProductionOrderItemUpdate, {}), (ReplaceDemandItemRequest, dict(required_quantity="1")),
])
def test_update_accepts_only_official_or_exact_unchanged_saved_unit(schema, payload):
    assert schema(**payload, unit="pcs").validate_unit_change("pcs").unit == "pcs"
    assert schema(**payload, unit="piece").validate_unit_change("pcs").unit == "piece"
    with pytest.raises(ValueError, match="UNIT_UNKNOWN"):
        schema(**payload, unit="pcs").validate_unit_change("kg")
    with pytest.raises(ValidationError, match="UNIT_UNKNOWN"):
        schema.model_validate(dict(payload, unit="pcs"), context={"previous_unit": "kg"})


def test_legacy_whitespace_not_changed_by_demand_update_parser():
    assert UpdateDemandItemRequest(unit=" legacy ").validate_unit_change(" legacy ").unit == " legacy "


def test_demand_api_preserves_legacy_on_edit_and_rejects_new_unknown_units(demand_env):
    env = demand_env
    invalid = env.create(items=[dict(ITEM, unit="pcs")])
    assert invalid.status_code == 400 and "UNIT_UNKNOWN" in invalid.text
    saved = detail(env, demand(env))
    item = env.db.get(ProductionDemandItem, UUID(saved["items"][0]["id"]))
    item.unit = "pcs"
    env.db.commit()
    path = f"{ROOT}/demands/{saved['id']}/items/{item.id}"
    unchanged = env.client.patch(path, json={"unit": "pcs", "notes": "Kept historical unit"})
    assert unchanged.status_code == 200, unchanged.text
    assert unchanged.json()["unit"] == "pcs"
    corrected = env.client.patch(path, json={"unit": "piece"})
    assert corrected.status_code == 200, corrected.text
    rejected = env.client.patch(path, json={"unit": "pcs"})
    assert rejected.status_code == 422 and "UNIT_UNKNOWN" in rejected.text


def test_whole_demand_edit_matches_legacy_units_by_saved_line_id(demand_env):
    env = demand_env
    saved = detail(env, demand(env))
    item = env.db.get(ProductionDemandItem, UUID(saved["items"][0]["id"]))
    item.unit = "pcs"
    env.db.commit()
    response = env.client.patch(f"{ROOT}/demands/{saved['id']}", json={"items": [dict(ITEM, id=str(item.id), unit="pcs")]})
    assert response.status_code == 200, response.text
    assert detail(env, saved)["items"][0]["unit"] == "pcs"
    current_id = detail(env, saved)["items"][0]["id"]
    duplicate = env.client.patch(f"{ROOT}/demands/{saved['id']}", json={"items": [dict(ITEM, id=current_id, unit="pcs", line_no=line) for line in (1, 2)]})
    assert duplicate.status_code == 409 and "duplicate_line_number" in duplicate.text
    rejected = env.client.patch(f"{ROOT}/demands/{saved['id']}", json={"items": [dict(ITEM, unit="unknown-new")]})
    assert rejected.status_code == 422 and "UNIT_UNKNOWN" in rejected.text
