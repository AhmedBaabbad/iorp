"""Incoming inspection (QUAL-INC-001): the decision on a received lot of purchased material. Pure: no database, no HTTP.

Every received lot of a material marked "inspected on arrival" (procurement) is inspected against its material's
specification, of the quantity received. The inspection ends with a split decision instead of a plain close: what is
released for use, and what is not — used as it is under a concession, sorted and re-inspected, returned to the supplier,
scrapped, or held. Anything not released opens a non-conformance report about the supplier (source incoming material),
one item per decision. Incoming inspections never touch production orders.
"""
from .enums import QualityCheckResult
from .rules import QualityError, ZERO

# The parts of a lot decision, in the order the screen shows them; "released" is the accepted quantity.
PARTS = ("released", "use_as_is", "sort", "return_to_supplier", "scrap", "hold")
NOT_RELEASED = PARTS[1:]  # each becomes an item of the NCR with this disposition


def split(inspected, parts: dict):
    """(released, not released, result); the parts must add up to what was inspected."""
    if inspected <= ZERO:
        raise QualityError("QUANTITY_INSPECTED_REQUIRED", 400)
    if any(value < ZERO for value in parts.values()):
        raise QualityError("QUANTITY_NEGATIVE", 400)
    total = sum(parts.values(), ZERO)
    if total != inspected:
        raise QualityError("LOT_SPLIT_MISMATCH", 400, inspected=str(inspected), total=str(total))
    released = parts.get("released", ZERO)
    rejected = inspected - released
    return released, rejected, QualityCheckResult.ACCEPTED if rejected == ZERO else QualityCheckResult.REJECTED


def assert_awaiting(found: dict | None, already_inspected: bool) -> None:
    if found is None:
        raise QualityError("RECEIPT_LINE_NOT_FOUND", 404)
    if not found["awaiting_inspection"]:
        raise QualityError("LOT_NOT_AWAITING_INSPECTION")
    if already_inspected:
        raise QualityError("LOT_ALREADY_INSPECTED")

