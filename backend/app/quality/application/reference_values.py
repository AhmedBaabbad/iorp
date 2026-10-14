"""Where quality stores reference-list values (MD-003): a defect's category, a rejection's reason (keys), and the test
method of a parameter or a measurement (its name, as written). Registered at the composition root so master data can
count their use without touching these tables."""
from app.core.interfaces.reference_lists import holder_for
from app.quality.infrastructure.models import QualityCheckMeasurement, QualityDefect, QualityRejection, QualityTestParameter

HOLDERS = (
    holder_for("quality", "defect_category", ((QualityDefect, QualityDefect.defect_category, lambda org: QualityDefect.organization_id == org),)),
    holder_for("quality", "rejection_reason", ((QualityRejection, QualityRejection.rejection_reason, lambda org: QualityRejection.organization_id == org),)),
    holder_for("quality", "test_method", ((QualityTestParameter, QualityTestParameter.method, lambda org: QualityTestParameter.organization_id == org),
                                          (QualityCheckMeasurement, QualityCheckMeasurement.method, lambda org: QualityCheckMeasurement.organization_id == org))),
)
