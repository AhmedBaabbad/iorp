"""Bilingual snapshots, catalog keys and independent specification copies."""
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.quality.domain import permissions as Q
from app.quality.infrastructure.models import QualitySpecification, QualitySpecificationLine
from tests.quality.test_quality_specifications import sq, SPECS, PARAMS, CHECKS, strap_order, code  # noqa: F401
from tests.quality.test_quality_inspections import q, result_env  # noqa: F401
from tests.quality.test_quality_certificates import cq  # noqa: F401


def test_catalog_keys_and_unchanged_legacy_key(sq):
    keys = sq.client.get(f"{SPECS}/numeric-properties")
    assert keys.status_code == 200
    assert {p["key"] for p in keys.json()} == {"width_mm", "thickness_mm", "roll_weight_kg", "length_m"}
    body = dict(code="KEYS", title="Keys", product_type="film", lines=[dict(
        parameter_id=sq.params["WIDTH"], target_source="order_line", order_spec_key="unknown")])
    assert code(sq.client.post(SPECS, json=body)) == "ORDER_SPEC_KEY_UNKNOWN"
    body["lines"][0]["order_spec_key"] = "width_mm"
    draft = sq.client.post(SPECS, json=body).json()
    line = sq.db.scalar(select(QualitySpecificationLine).where(QualitySpecificationLine.specification_id == UUID(draft["id"])))
    line.order_spec_key = "retired_key"
    sq.db.commit()
    body["lines"][0]["order_spec_key"] = "retired_key"
    assert sq.client.patch(f"{SPECS}/{draft['id']}", json={"lines": body["lines"]}).status_code == 200
    body["lines"][0]["order_spec_key"] = "another_unknown"
    assert code(sq.client.patch(f"{SPECS}/{draft['id']}", json={"lines": body["lines"]})) == "ORDER_SPEC_KEY_UNKNOWN"


def test_catalog_and_copy_are_tenant_scoped_and_permission_checked(sq):
    from app.masterdata.infrastructure.models import Product, ProductProperty
    from tests.test_production_allocation_lifecycle import other_org_demand
    foreign = other_org_demand(sq.db)
    product = Product(organization_id=foreign.org.id, code="FOREIGN", key="foreign", name_ar="آخر", name_en="Other", kind="finished", created_by_user_id=sq.user.id)
    product.properties = [ProductProperty(line_no=1, key="foreign_property", name_ar="آخر", name_en="Foreign", kind="number")]
    sq.db.add(product)
    spec = QualitySpecification(organization_id=foreign.org.id, code="FOREIGN", revision=1, title="Foreign", product_type="foreign", status="draft", created_by_user_id=sq.user.id)
    sq.db.add(spec)
    sq.db.commit()
    assert "foreign_property" not in {row["key"] for row in sq.client.get(f"{SPECS}/numeric-properties").json()}
    assert sq.client.post(f"{SPECS}/{spec.id}/copy", json=dict(code="OTHER-COPY", title="Denied")).status_code == 404
    for permission in (Q.SPECS_READ, Q.SPECS_CREATE, Q.SPECS_UPDATE):
        sq.ctx.auth_user.permissions.discard(permission)
    assert sq.client.get(f"{SPECS}/numeric-properties").status_code == 403


@pytest.mark.parametrize("status", ["draft", "active", "superseded"])
def test_copy_all_fields_is_independent_and_audited(sq, status, monkeypatch):
    from app.core.interfaces.activity_log import get_registered_activity_logger
    from app.quality.application.specification_service import LINE_FIELDS
    source = sq.spec(activate=False, lines=[dict(parameter_id=sq.params["WIDTH"], target_source="order_line",
        order_spec_key="thickness_mm", tolerance_minus="0.02", tolerance_plus="0.03", readings_required=3,
        requirement_ar="المطلوب", requirement_en="Required", acceptance_ar="القبول", acceptance_en="Accepted",
        method_ar="قياس", method_en="Measure")])
    original = sq.db.get(QualitySpecification, UUID(source["id"]))
    original.status = status
    sq.db.commit()
    calls = []
    logger = get_registered_activity_logger()
    strict = logger.log_activity_strict
    def record(*args, **kwargs):
        calls.append((args, kwargs))
        return strict(*args, **kwargs)
    monkeypatch.setattr(logger, "log_activity_strict", record)
    response = sq.client.post(f"{SPECS}/{source['id']}/copy", json=dict(code="NEW-COPY", title="Independent"))
    assert response.status_code == 201, response.text
    copied = response.json()
    assert copied["status"] == "draft" and copied["revision"] == 1 and copied["id"] != source["id"]
    assert copied["product_type"] == source["product_type"] and copied["grade"] == source["grade"]
    assert {f: copied["lines"][0][f] for f in LINE_FIELDS} == {f: source["lines"][0][f] for f in LINE_FIELDS}
    assert any(args[2] == "quality_specification.copied" and kw["details"] == {"source_id": source["id"]} for args, kw in calls)
    assert sq.client.get(f"{SPECS}/{source['id']}").json()["status"] == status
    assert code(sq.client.post(f"{SPECS}/{source['id']}/copy", json=dict(code="new-copy", title="Duplicate"))) == "SPECIFICATION_CODE_TAKEN"
    assert sq.client.post(f"{SPECS}/{uuid4()}/copy", json=dict(code="NOT-FOUND", title="Missing")).status_code == 404
    sq.ctx.auth_user.permissions.discard(Q.SPECS_CREATE)
    assert sq.client.post(f"{SPECS}/{source['id']}/copy", json=dict(code="FORBIDDEN", title="Denied")).status_code == 403


def test_copy_rolls_back_when_strict_audit_fails(sq, monkeypatch):
    from app.core.interfaces.activity_log import get_registered_activity_logger
    from app.quality.application.specification_service import SpecificationService
    from app.quality.api.specification_schemas import SpecificationCopy
    source = sq.spec(activate=False)
    def fail(*args, **kwargs):
        raise RuntimeError("Audit unavailable")
    monkeypatch.setattr(get_registered_activity_logger(), "log_activity_strict", fail)
    with pytest.raises(RuntimeError, match="Audit unavailable"):
        SpecificationService(sq.db, sq.ctx.tenant).copy(UUID(source["id"]), SpecificationCopy(code="ROLLBACK", title="Copy"))
    assert sq.db.scalar(select(QualitySpecification).where(QualitySpecification.code == "ROLLBACK")) is None


def test_bilingual_snapshot_and_missing_property_details(sq):
    sq.client.patch(f"{PARAMS}/{sq.params['WIDTH']}", json=dict(method_ar="طريقة المعامل", method_en="Parameter method"))
    spec = sq.spec(lines=[dict(parameter_id=sq.params["WIDTH"], target_source="order_line", order_spec_key="width_mm",
        tolerance_minus="0.1", tolerance_plus="0.2", requirement_ar="عرض مطلوب", requirement_en="Required width",
        acceptance_ar="ضمن الحدود", acceptance_en="Within limits", method_ar="طريقة السطر")])
    ranged = sq.opened(strap_order(sq, width_mm={"min": .70, "max": .75}), check_type="finished_product_inspection")["measurements"][0]
    assert (float(ranged["lower_limit"]), float(ranged["upper_limit"])) == (.70, .75)
    assert ranged["method_ar"] == "طريقة السطر" and ranged["method_en"] == "Parameter method"
    for field in ("requirement_ar", "requirement_en", "acceptance_ar", "acceptance_en"):
        assert ranged[field] == spec["lines"][0][field]
    scalar = sq.opened(strap_order(sq, width_mm=5), check_type="finished_product_inspection")["measurements"][0]
    assert (float(scalar["lower_limit"]), float(scalar["upper_limit"])) == (4.9, 5.2)
    missing = sq.opened(strap_order(sq, color="Black"), check_type="finished_product_inspection")
    response = sq.client.post(f"{CHECKS}/{missing['id']}/plan", json=dict(specification_id=spec["id"]))
    detail = response.json()["detail"]
    assert detail["code"] == "LOT_SPEC_VALUE_MISSING" and detail["key"] == "width_mm"
    assert detail["parameter_en"] == "Width" and detail["parameter_ar"]
    sq.client.patch(f"{PARAMS}/{sq.params['WIDTH']}", json=dict(method_ar="تغيير", method_en="Changed"))
    frozen = sq.client.get(f"{CHECKS}/{missing['id']}").json()
    assert frozen["measurements"] == []


@pytest.mark.parametrize("lang,expected", [("en", "English"), ("ar", "عربي")])
def test_wording_language_and_legacy_fallback(lang, expected):
    from app.quality.domain.wording import wording
    assert wording({"method_ar": "عربي", "method_en": "English"}, "method", lang) == expected
    assert wording({"method_ar": "", "method_en": "English"}, "method", "ar") == "English"
    assert wording({"method": "Legacy frozen text"}, "method", lang) == "Legacy frozen text"


def test_certificate_prints_own_language_and_preserves_frozen_words(cq):
    from app.quality.infrastructure.models import QualityTestParameter
    color = cq.db.scalar(select(QualitySpecificationLine).join(QualityTestParameter).where(QualityTestParameter.code == "COLOR"))
    color.requirement_ar, color.requirement_en = "متطلب عربي محفوظ", "Frozen English requirement"
    color.acceptance_ar, color.acceptance_en = "قبول عربي محفوظ", "Frozen English acceptance"
    color.method_ar, color.method_en = "طريقة عربية محفوظة", "Frozen English method"
    cq.db.commit()
    check = cq.measured_check()
    draft = cq.draft(check)
    color.requirement_en = "Edited after inspection"
    color.method_ar = "تعديل لاحق"
    cq.db.commit()
    for lang, present, absent in (
        ("en", ("Frozen English requirement", "Frozen English acceptance", "Frozen English method"), "متطلب عربي محفوظ"),
        ("ar", ("متطلب عربي محفوظ", "قبول عربي محفوظ", "طريقة عربية محفوظة"), "Frozen English requirement"),
    ):
        response = cq.client.post("/api/v1/reports/quality.certificate/preview", json=dict(certificate_id=draft["id"], lang=lang))
        assert response.status_code == 200, response.text
        assert all(word in response.text for word in present)
        assert absent not in response.text and "Edited after inspection" not in response.text
