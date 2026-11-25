"""Where quality stores reference-list values (MD-003): a defect's category, a rejection's reason (keys), and the test
method of a parameter or a measurement (its name, as written). Registered at the composition root so master data can
count their use without touching these tables."""
from sqlalchemy import func, or_, select, update
from app.core.interfaces.product_types import count_values
from app.core.interfaces.reference_lists import ReferenceHolder, holder_for, list_items
from app.quality.infrastructure.models import QualityCheckMeasurement, QualityDefect, QualityRejection, QualityTestParameter, QualitySpecificationLine, QualitySpecification


def _method_columns(organization_id):
    return (
        (QualityTestParameter, QualityTestParameter.organization_id == organization_id),
        (QualityCheckMeasurement, QualityCheckMeasurement.organization_id == organization_id),
        (QualitySpecificationLine, QualitySpecificationLine.specification_id.in_(
            select(QualitySpecification.id).where(QualitySpecification.organization_id == organization_id))),
    )


def _method_usage(db, organization_id):
    totals = {}
    for model, scope in _method_columns(organization_id):
        value = func.coalesce(func.nullif(model.method_en, ""), model.method_ar)
        for text, count in count_values(db, value, scope).items():
            totals[text] = totals.get(text, 0) + count
    return totals


def _method_renamed(db, organization_id, old_ar, old_en, new_ar, new_en):
    changed = 0
    for model, scope in _method_columns(organization_id):
        match = or_(model.method_en == old_en,
                    (or_(model.method_en.is_(None), model.method_en == "")) & (model.method_ar == old_ar))
        result = db.execute(update(model).where(scope, match).values(method_ar=new_ar, method_en=new_en)
                            .execution_options(synchronize_session=False))
        changed += result.rowcount or 0
    return changed


def _method_map(db, organization_id, old, key):
    item = list_items(db, organization_id, "test_method", [key]).get(key)
    return _method_renamed(db, organization_id, old, old, item.name_ar, item.name_en) if item else 0

HOLDERS = (
    holder_for("quality", "defect_category", ((QualityDefect, QualityDefect.defect_category, lambda org: QualityDefect.organization_id == org),)),
    holder_for("quality", "rejection_reason", ((QualityRejection, QualityRejection.rejection_reason, lambda org: QualityRejection.organization_id == org),)),
    ReferenceHolder("quality", "test_method", _method_usage, _method_map, _method_renamed),
)
