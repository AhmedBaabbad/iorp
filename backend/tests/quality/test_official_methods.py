from uuid import UUID

from sqlalchemy import select

from app.masterdata.infrastructure.models import ListItem
from app.quality.infrastructure.models import QualitySpecificationLine, QualityTestParameter, QualityCheckMeasurement
from tests.quality.test_quality_specifications import sq, PARAMS, SPECS, strap_order  # noqa: F401
from tests.quality.test_quality_inspections import q, result_env  # noqa: F401


def official(env, english="Micrometer", arabic="ميكرومتر"):
    item = ListItem(organization_id=env.org.id, list="test_method", key="official", name_ar=arabic, name_en=english, active=True, sort_order=1)
    env.db.add(item)
    env.db.commit()
    return item


def test_parameter_official_names_reject_unknown_and_keep_legacy(sq):
    item = official(sq)
    body = dict(code="METHOD", name_ar="اختبار", name_en="Test", kind="numeric", unit="mm", method_en=item.name_en, method_ar="غير رسمي")
    response = sq.client.post(PARAMS, json=body)
    assert response.status_code == 201, response.text
    parameter = response.json()
    assert (parameter["method_ar"], parameter["method_en"]) == (item.name_ar, item.name_en)
    for values in (dict(method_en="Unknown"), dict(method_en=None, method_ar="غير رسمي")):
        response = sq.client.post(PARAMS, json={**body, "code":"UNKNOWN", **values})
        assert response.status_code == 422 and response.json()["detail"]["code"] == "REFERENCE_VALUE_UNAVAILABLE"
    saved = sq.db.get(QualityTestParameter, UUID(parameter["id"]))
    saved.method_ar, saved.method_en = "قديم", "Legacy method"
    sq.db.commit()
    response = sq.client.patch(f"{PARAMS}/{saved.id}", json=dict(method_en="Legacy method", method_ar="قديم"))
    assert response.status_code == 200 and response.json()["method_ar"] == "قديم"
    response = sq.client.patch(f"{PARAMS}/{saved.id}", json=dict(method_en="Another unknown"))
    assert response.status_code == 422
    response = sq.client.patch(f"{PARAMS}/{saved.id}", json=dict(method_en=item.name_en))
    assert response.status_code == 200 and response.json()["method_ar"] == item.name_ar
    item.active = False
    sq.db.commit()
    assert sq.client.patch(f"{PARAMS}/{saved.id}", json=dict(method_en=item.name_en)).status_code == 200
    assert sq.client.post(PARAMS, json={**body, "code":"INACTIVE"}).status_code == 422


def test_specification_line_validates_and_preserves_legacy_without_deleting_lines(sq):
    item = official(sq)
    body = dict(parameter_id=sq.params["WIDTH"], target_source="order_line", order_spec_key="width_mm", method_en=item.name_en, method_ar="غير رسمي")
    draft = sq.spec(activate=False, lines=[body])
    assert draft["lines"][0]["method_ar"] == item.name_ar
    line = sq.db.scalar(select(QualitySpecificationLine).where(QualitySpecificationLine.specification_id == UUID(draft["id"])))
    line.method_ar, line.method_en = "قديم", "Legacy line method"
    sq.db.commit()
    payload = {**body, "method_ar":"قديم", "method_en":"Legacy line method"}
    response = sq.client.patch(f"{SPECS}/{draft['id']}", json=dict(lines=[payload]))
    assert response.status_code == 200 and response.json()["lines"][0]["method_ar"] == "قديم"
    response = sq.client.patch(f"{SPECS}/{draft['id']}", json=dict(lines=[{**payload, "method_en":"Unknown"}]))
    assert response.status_code == 422
    assert sq.client.get(f"{SPECS}/{draft['id']}").json()["lines"][0]["method_en"] == "Legacy line method"


def test_seed_validates_official_methods_and_rolls_back(q):
    from app.quality.domain.specifications import STANDARD_PARAMETERS
    official(q, english="Not a standard method")
    response = q.client.post(f"{PARAMS}/standard")
    assert response.status_code == 422
    assert q.client.get(PARAMS).json() == []
    q.db.query(ListItem).delete()
    methods = sorted({row[5] for row in STANDARD_PARAMETERS if row[5]})
    for index, method in enumerate(methods):
        q.db.add(ListItem(organization_id=q.org.id, list="test_method", key=f"method-{index}", name_ar=f"طريقة {index}", name_en=method, active=True, sort_order=index))
    q.db.commit()
    response = q.client.post(f"{PARAMS}/standard")
    assert response.status_code == 200, response.text
    assert all(row["method_ar"] and row["method_en"] in methods for row in response.json() if row["method_en"])


def test_rename_updates_both_names_in_parameters_lines_and_measurements_only_in_organization(sq):
    from app.masterdata.application.list_service import ListService
    from app.masterdata.api.schemas import ListItemUpdate
    from tests.test_production_allocation_lifecycle import other_org_demand
    item = official(sq)
    parameter = sq.db.get(QualityTestParameter, UUID(sq.params["WIDTH"]))
    parameter.method_en, parameter.method_ar = item.name_en, item.name_ar
    sq.db.commit()
    spec = sq.spec(lines=[dict(parameter_id=sq.params["WIDTH"], target_source="order_line", order_spec_key="width_mm", method_en=item.name_en)])
    check = sq.opened(strap_order(sq), check_type="finished_product_inspection")
    foreign = other_org_demand(sq.db)
    other = QualityTestParameter(organization_id=foreign.org.id, code="FOREIGN", name_ar="آخر", name_en="Other", kind="numeric", method_en=item.name_en, method_ar=item.name_ar)
    sq.db.add(other)
    sq.db.commit()
    ListService(sq.db, sq.ctx.tenant).update(item.id, ListItemUpdate(name_ar="طريقة جديدة", name_en="Renamed method"))
    sq.db.expire_all()
    for model, identifier in ((QualityTestParameter, parameter.id), (QualitySpecificationLine, UUID(spec["lines"][0]["id"])),
                              (QualityCheckMeasurement, UUID(check["measurements"][0]["id"]))):
        row = sq.db.get(model, identifier)
        assert (row.method_ar, row.method_en) == ("طريقة جديدة", "Renamed method")
    assert (other.method_ar, other.method_en) == ("ميكرومتر", "Micrometer")
    # Arabic-only legacy snapshots must be updated and counted too.
    parameter.method_en = None
    sq.db.commit()
    assert ListService(sq.db, sq.ctx.tenant).uses(item) >= 3
    ListService(sq.db, sq.ctx.tenant).update(item.id, ListItemUpdate(name_ar="تعديل عربي فقط"))
    sq.db.expire_all()
    assert (parameter.method_ar, parameter.method_en) == ("تعديل عربي فقط", "Renamed method")
