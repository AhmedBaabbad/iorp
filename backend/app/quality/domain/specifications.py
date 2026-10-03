"""Specifications and measurements (QUAL-SPEC-001). Pure: no database, no HTTP.

Test parameter: what is measured or checked — numeric (readings in a unit) or attribute (conforming / not).
Specification (the TDS): a controlled document, one per product (and grade), numbered by the factory
(e.g. ROF-TDS-PP-001) with revisions:  draft ─activate→ active ─(a newer revision is activated)→ superseded.
Only a draft is edited; changing an active one means revising it (a new draft, revision + 1).
Each line sets a parameter's acceptance:
  target    fixed, or taken from the order line's specification key (e.g. width_mm), or none
  limits    lower = minimum, or target − tolerance below;  upper = maximum, or target + tolerance above
            (either side may be open, e.g. a minimum roll length)
  attribute the requirement and acceptance wording; the inspector records conforming / not conforming.
Measurement plan: applying a specification to an inspection copies its lines with their limits resolved for
that lot, so later revisions never change an inspection already made (nor a certificate built from it).
A numeric result passes when every reading lies within its limits (inclusive); with no limit at all it is
only recorded. A plan must be fully measured before the inspection closes, and an inspection with a failed
measurement cannot close as "accepted".
"""
from decimal import Decimal, InvalidOperation

from app.quality.domain.rules import QualityError

NUMERIC, ATTRIBUTE = "numeric", "attribute"
KINDS = (NUMERIC, ATTRIBUTE)
FIXED, ORDER_LINE, NO_TARGET = "fixed", "order_line", "none"
TARGET_SOURCES = (FIXED, ORDER_LINE, NO_TARGET)
DRAFT, ACTIVE, SUPERSEDED = "draft", "active", "superseded"
PENDING, PASS, FAIL, RECORDED = "pending", "pass", "fail", "recorded"
CONFORMING, NONCONFORMING = "conforming", "nonconforming"
MAX_READINGS = 50

# Parameters a strapping-band factory checks; offered once per organization, then edited freely.
STANDARD_PARAMETERS = (
    ("WIDTH", "العرض", "Width", NUMERIC, "mm", "Calibrated vernier caliper"),
    ("THICKNESS", "السماكة", "Thickness", NUMERIC, "mm", "Calibrated thickness gauge / micrometer"),
    ("ROLL_WEIGHT", "وزن الرول الصافي", "Net roll weight", NUMERIC, "kg", "Calibrated weighing scale"),
    ("ROLL_LENGTH", "طول الرول", "Roll length", NUMERIC, "m", "Length counter / calculated from verified g/m"),
    ("BREAK_STRENGTH", "قوة الكسر", "Break strength", NUMERIC, "N", "Tensile tester"),
    ("ELONGATION", "الاستطالة عند الكسر", "Elongation at break", NUMERIC, "%", "Tensile tester"),
    ("COLOR", "اللون", "Color", ATTRIBUTE, None, "Approved color sample / visual inspection"),
    ("EMBOSSING", "النقشة", "Embossing", ATTRIBUTE, None, "Visual inspection"),
    ("WINDING", "جودة اللف", "Winding quality", ATTRIBUTE, None, "Visual inspection"),
    ("SURFACE", "السطح والمظهر", "Surface / appearance", ATTRIBUTE, None, "Visual inspection"),
    ("CORE_PACKAGING", "الكور والتغليف", "Core / packaging", ATTRIBUTE, None, "Visual inspection"),
)


def decimal(value):
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


# ── specification documents ─────────────────────────────────────────────────────────────────────

def assert_draft(status) -> None:
    if status != DRAFT:
        raise QualityError("SPECIFICATION_NOT_DRAFT", spec_status=status)


def assert_line(kind, line) -> None:
    """One specification line, given its parameter's kind. `line` is a mapping of the line's fields."""
    if kind == ATTRIBUTE:
        if not (line.get("requirement") or "").strip():
            raise QualityError("REQUIREMENT_REQUIRED", 400, parameter=line.get("parameter_code"))
        return
    source = line.get("target_source") or NO_TARGET
    if source not in TARGET_SOURCES:
        raise QualityError("TARGET_SOURCE_INVALID", 400, parameter=line.get("parameter_code"))
    if source == ORDER_LINE and not (line.get("order_spec_key") or "").strip():
        raise QualityError("ORDER_SPEC_KEY_REQUIRED", 400, parameter=line.get("parameter_code"))
    if source == FIXED and decimal(line.get("target_value")) is None:
        raise QualityError("TARGET_REQUIRED", 400, parameter=line.get("parameter_code"))
    minus, plus = decimal(line.get("tolerance_minus")), decimal(line.get("tolerance_plus"))
    low, high = decimal(line.get("min_value")), decimal(line.get("max_value"))
    if any(v is not None and v < 0 for v in (minus, plus)):
        raise QualityError("TOLERANCE_NEGATIVE", 400, parameter=line.get("parameter_code"))
    if low is not None and high is not None and low > high:
        raise QualityError("LIMITS_INVALID", 400, parameter=line.get("parameter_code"))
    has_tolerance = source != NO_TARGET and (minus is not None or plus is not None)
    if low is None and high is None and not has_tolerance:
        raise QualityError("LIMITS_REQUIRED", 400, parameter=line.get("parameter_code"))
    if int(line.get("readings_required") or 1) < 1:
        raise QualityError("READINGS_REQUIRED_INVALID", 400, parameter=line.get("parameter_code"))


def assert_can_activate(status, line_count) -> None:
    assert_draft(status)
    if line_count == 0:
        raise QualityError("SPECIFICATION_EMPTY")


# ── measurement plan ────────────────────────────────────────────────────────────────────────────

def resolve_limits(line, lot_spec: dict | None):
    """(target, lower, upper) for one lot. A target from the order line comes from its specification key."""
    source = line.get("target_source") or NO_TARGET
    target = None
    if source == FIXED:
        target = decimal(line.get("target_value"))
    elif source == ORDER_LINE:
        target = decimal((lot_spec or {}).get(line.get("order_spec_key")))
        if target is None:
            raise QualityError("LOT_SPEC_VALUE_MISSING", 409, parameter=line.get("parameter_code"), key=line.get("order_spec_key"))
    minus, plus = decimal(line.get("tolerance_minus")), decimal(line.get("tolerance_plus"))
    lower, upper = decimal(line.get("min_value")), decimal(line.get("max_value"))
    if lower is None and target is not None and minus is not None:
        lower = target - minus
    if upper is None and target is not None and plus is not None:
        upper = target + plus
    return target, lower, upper


def parse_readings(values) -> list[Decimal]:
    readings = []
    for value in values or []:
        number = decimal(value)
        if number is None:
            raise QualityError("READING_INVALID", 400, value=str(value))
        readings.append(number)
    if len(readings) > MAX_READINGS:
        raise QualityError("TOO_MANY_READINGS", 400, maximum=MAX_READINGS)
    return readings


def evaluate(kind, readings, attribute_result, lower, upper, required=1):
    """(count, minimum, maximum, mean, status) of one measurement."""
    if kind == ATTRIBUTE:
        if attribute_result not in (CONFORMING, NONCONFORMING):
            return 0, None, None, None, PENDING
        return 1, None, None, None, PASS if attribute_result == CONFORMING else FAIL
    if len(readings) < max(1, required):
        stats = (len(readings), min(readings), max(readings), _mean(readings)) if readings else (0, None, None, None)
        return (*stats, PENDING)
    low, high, mean = min(readings), max(readings), _mean(readings)
    if lower is None and upper is None:
        return len(readings), low, high, mean, RECORDED
    failed = (lower is not None and low < lower) or (upper is not None and high > upper)
    return len(readings), low, high, mean, FAIL if failed else PASS


def _mean(readings):
    return (sum(readings) / len(readings)).quantize(Decimal("0.0001")) if readings else None


def assert_plan_complete(statuses, result) -> None:
    """Closing an inspection that has a plan: everything measured; a failed measurement is never "accepted"."""
    if any(s == PENDING for s in statuses):
        raise QualityError("MEASUREMENTS_INCOMPLETE", count=sum(1 for s in statuses if s == PENDING))
    if str(getattr(result, "value", result)) == "accepted" and any(s == FAIL for s in statuses):
        raise QualityError("ACCEPTED_WITH_FAILED_MEASUREMENT", 400)
