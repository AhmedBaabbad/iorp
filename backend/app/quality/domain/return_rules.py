"""Quality decisions on returned goods (QUAL-RET-001). Pure: no database, no HTTP.

A shipping return that needs quality (a quality reason, transit damage, "other", or sent by the warehouse) is
inspected line by line: one inspection per returned line, of the quantity that actually came back. The inspection
ends with a split decision instead of a plain close: what goes back to stock, and what is rejected under each
disposition (second grade under a concession, rework, back to the process, scrap «هالك», hold). Each rejected part
becomes a rejection already decided, executed later like any other. Return inspections and their rejections never
block closing a production order: the goods were produced and shipped long before.
"""
from decimal import Decimal

from .enums import Disposition, QualityCheckResult, RejectionReason
from .rules import QualityError, ZERO

# The parts of a return decision, in the order the screen shows them; "to_stock" is the accepted quantity.
PARTS = ("to_stock", "use_as_is", "rework", "return_to_process", "scrap", "hold")
DISPOSITION_OF = {"use_as_is": Disposition.USE_AS_IS, "rework": Disposition.REWORK, "return_to_process": Disposition.RETURN_TO_PROCESS,
                  "scrap": Disposition.SCRAP, "hold": Disposition.HOLD}

# The shipping return reason -> the rejection reason recorded for its rejected parts.
REJECTION_REASON = {"quality_defect": RejectionReason.FAILED_QUALITY_CHECK, "quality_issue": RejectionReason.FAILED_QUALITY_CHECK,
                    "spec_mismatch": RejectionReason.OUT_OF_SPEC}


def split(inspected: Decimal, parts: dict) -> tuple[Decimal, Decimal, QualityCheckResult]:
    """(accepted, rejected, result) of a decision; the parts must add up to what was inspected."""
    if inspected <= ZERO:
        raise QualityError("QUANTITY_INSPECTED_REQUIRED", 400)
    if any(value < ZERO for value in parts.values()):
        raise QualityError("QUANTITY_NEGATIVE", 400)
    total = sum(parts.values(), ZERO)
    if total != inspected:
        raise QualityError("RETURN_SPLIT_MISMATCH", 400, inspected=str(inspected), total=str(total))
    accepted = parts.get("to_stock", ZERO)
    rejected = inspected - accepted
    return accepted, rejected, QualityCheckResult.ACCEPTED if rejected == ZERO else QualityCheckResult.REJECTED


def rejection_reason(return_reason: str | None) -> RejectionReason:
    return REJECTION_REASON.get(return_reason or "", RejectionReason.OTHER)


def assert_awaiting(found: dict | None, already_inspected: bool) -> None:
    if found is None:
        raise QualityError("RETURN_LINE_NOT_FOUND", 404)
    if not found["awaiting_quality"]:
        raise QualityError("RETURN_NOT_AWAITING_QUALITY")
    if already_inspected:
        raise QualityError("RETURN_LINE_ALREADY_INSPECTED")
