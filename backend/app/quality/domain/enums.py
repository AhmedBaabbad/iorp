from enum import Enum


class QualityCheckType(str, Enum):
    # Inspection triggered during an active production run.
    IN_PROCESS_INSPECTION = "in_process_inspection"
    # Final inspection before a finished batch is released.
    FINISHED_PRODUCT_INSPECTION = "finished_product_inspection"
    # Inspection of a commercial sample (future: links to Commercial/Sample).
    SAMPLE_INSPECTION = "sample_inspection"
    # Re-check after rework or corrective action on a previously rejected lot.
    REINSPECTION = "reinspection"
    # Inspection opened in direct response to a reported quality issue.
    ISSUE_TRIGGERED = "issue_triggered"
    # Catch-all for inspections that do not fit a named business type.
    GENERAL = "general"


class QualityCheckStatus(str, Enum):
    # Check has been created but the physical inspection has not started.
    OPEN = "open"
    # Inspection is actively in progress.
    UNDER_INSPECTION = "under_inspection"
    # Inspection is concluded and result has been recorded.
    CLOSED = "closed"
    # Withdrawn before a result (created by mistake, lot no longer available); a reason is kept.
    CANCELLED = "cancelled"


class QualityCheckResult(str, Enum):
    # Entire inspected quantity met the specification.
    ACCEPTED = "accepted"
    # Inspected quantity failed; defect records are expected to follow.
    REJECTED = "rejected"
    # Accepted with noted deviations or conditional release.
    CONDITIONAL_ACCEPT = "conditional_accept"
    # A further inspection pass is required before a final decision.
    NEEDS_REINSPECTION = "needs_reinspection"


class DefectCategory(str, Enum):
    # Dimensional non-conformance: length, width, diameter.
    DIMENSION = "dimension"
    # Thickness or gauge deviation, common in film and roll factories.
    THICKNESS = "thickness"
    # Surface defects such as scratches, marks, or contamination spots.
    SURFACE = "surface"
    # Color deviation or inconsistency.
    COLOR = "color"
    # Tensile or mechanical strength failure.
    STRENGTH = "strength"
    # Winding defects: uneven roll, loose winding, or core issues.
    WINDING = "winding"
    # Weight out of tolerance.
    WEIGHT = "weight"
    # Packaging defect or damage.
    PACKAGING = "packaging"
    # Labeling error or missing information.
    LABELING = "labeling"
    # Finish quality: roughness, texture, or appearance.
    FINISH = "finish"
    # Catch-all for unclassified defects.
    OTHER = "other"


class DefectSeverity(str, Enum):
    # Cosmetic or marginal; does not affect core function.
    MINOR = "minor"
    # Significantly affects function or customer expectations.
    MAJOR = "major"
    # Renders product unusable, unsafe, or fully rejected.
    CRITICAL = "critical"


class RejectionReason(str, Enum):
    # Rejected because the quality check result was failed.
    FAILED_QUALITY_CHECK = "failed_quality_check"
    # Rejected due to a critical severity defect.
    CRITICAL_DEFECT = "critical_defect"
    # Product is outside specifications.
    OUT_OF_SPEC = "out_of_spec"
    # Dimensional non-conformance.
    DIMENSION_FAILURE = "dimension_failure"
    # Surface defects caused rejection.
    SURFACE_FAILURE = "surface_failure"
    # Packaging non-conformance.
    PACKAGING_FAILURE = "packaging_failure"
    # Labeling errors or missing labeling information.
    LABELING_ISSUE = "labeling_issue"
    # Catch-all; must be accompanied by rejection notes.
    OTHER = "other"


class Disposition(str, Enum):
    # Quarantine pending further decision or investigation.
    HOLD = "hold"
    # Permanently discard; cannot be recovered.
    SCRAP = "scrap"
    # Send back for correction and re-inspection.
    REWORK = "rework"
    # Reintroduce into the production process.
    RETURN_TO_PROCESS = "return_to_process"
    # Accepted as it is under an approved concession (e.g. the customer accepts a minor deviation).
    USE_AS_IS = "use_as_is"


class DispositionStatus(str, Enum):
    # Rejected quantity awaiting a disposition decision.
    PENDING = "pending"
    # Disposition decided (hold, scrap, rework, return to process or use as is), not yet carried out.
    DECIDED = "decided"
    # Decision carried out; the rejection is final.
    EXECUTED = "executed"


class NCRSourceType(str, Enum):
    # Non-conformance discovered during manufacturing.
    INTERNAL_PRODUCTION = "internal_production"
    # Non-conforming material received from supplier.
    INCOMING_MATERIAL = "incoming_material"
    # Supplier-related non-conformance beyond incoming material.
    SUPPLIER = "supplier"
    # Issue found during warehouse or storage.
    WAREHOUSE = "warehouse"
    # Returned goods from customer with non-conformance.
    CUSTOMER_RETURN = "customer_return"
    # Unclassified source; details belong in description.
    OTHER = "other"


class NCRReportType(str, Enum):
    # Raw material or component does not meet specification.
    MATERIAL_NON_CONFORMANCE = "material_non_conformance"
    # Finished or semi-finished product does not meet specification.
    PRODUCT_NON_CONFORMANCE = "product_non_conformance"
    # Process deviation or process failure.
    PROCESS_NON_CONFORMANCE = "process_non_conformance"
    # Packaging does not meet requirements.
    PACKAGING_NON_CONFORMANCE = "packaging_non_conformance"
    # Missing, incorrect, or incomplete documentation.
    DOCUMENTATION_NON_CONFORMANCE = "documentation_non_conformance"
    # Catch-all; details belong in description.
    OTHER = "other"
