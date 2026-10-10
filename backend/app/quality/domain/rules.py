"""Quality inspection and rejection rules (QUAL-001). Pure: no database, no HTTP.

Check lifecycle:     open ─start→ under_inspection ─close(result)→ closed
                     open / under_inspection ─cancel(reason)→ cancelled
  closed and cancelled checks are final (no edits).
Result (set only when closing):
  accepted            nothing rejected
  rejected            something rejected
  conditional_accept  released with a noted deviation (any split)
  needs_reinspection  another inspection pass follows (any split)
Quantities are decimals in the inspected line's unit: accepted + rejected = inspected.

Rejection lifecycle: pending ─decide(disposition)→ decided ─execute→ executed
  A decided rejection may be re-decided until it is executed. "hold" is a temporary quarantine:
  it cannot be executed, only re-decided to a final disposition. "use_as_is" needs the concession
  approver and its justification. Executed rejections are final.
Production close gate: an order cannot close while it has an open or under-inspection check, or
a rejection that is pending or on hold.
"""
from decimal import Decimal

from app.quality.domain.enums import Disposition as D, DispositionStatus as DS, QualityCheckResult as R, QualityCheckStatus as S
from app.quality.domain.permissions import CHECK_ACTIONS, REJECTION_ACTIONS

ZERO = Decimal("0")
ACTIVE = frozenset({S.OPEN, S.UNDER_INSPECTION})
FINAL = frozenset({S.CLOSED, S.CANCELLED})
# Orders a check or a rejection may be recorded against: running, held or completed (closing locks quality).
ORDER_STATUSES = frozenset({"in_progress", "on_hold", "completed"})
# A reinspection may also be made on a closed order: its retained samples are measured again, e.g. when a customer
# asks for a certificate after shipment. The order stays closed; the close gate is not involved.
REINSPECTION_ORDER_STATUSES = ORDER_STATUSES | {"closed"}


def order_statuses(check_type) -> frozenset:
    """The order statuses an inspection of this type may be opened on."""
    return REINSPECTION_ORDER_STATUSES if str(getattr(check_type, "value", check_type)) == "reinspection" else ORDER_STATUSES


class QualityError(ValueError):
    def __init__(self, code: str, status: int = 409, **detail):
        super().__init__(code)
        self.code, self.status, self.detail = code, status, detail


def assert_editable(status) -> None:
    if S(status) in FINAL:
        raise QualityError("CHECK_IS_FINAL", check_status=S(status).value)


def assert_can_start(status) -> None:
    if S(status) != S.OPEN:
        raise QualityError("CHECK_NOT_OPEN", check_status=S(status).value)


def assert_can_finish(status) -> None:
    """Close or cancel: only an open or under-inspection check."""
    if S(status) not in ACTIVE:
        raise QualityError("CHECK_IS_FINAL", check_status=S(status).value)


def assert_quantities(inspected: Decimal, accepted: Decimal, rejected: Decimal) -> None:
    if inspected <= ZERO:
        raise QualityError("QUANTITY_INSPECTED_REQUIRED", 400)
    if accepted < ZERO or rejected < ZERO:
        raise QualityError("QUANTITY_NEGATIVE", 400)
    if accepted + rejected != inspected:
        raise QualityError("QUANTITY_BALANCE", 400, inspected=str(inspected), accepted=str(accepted), rejected=str(rejected))


def assert_result_matches(result, rejected: Decimal) -> None:
    result = R(result)
    if result == R.ACCEPTED and rejected > ZERO:
        raise QualityError("ACCEPTED_WITH_REJECTED_QUANTITY", 400)
    if result == R.REJECTED and rejected <= ZERO:
        raise QualityError("REJECTED_WITHOUT_QUANTITY", 400)


def is_unresolved(status, disposition) -> bool:
    """A rejection that blocks closing its production order: no decision yet, or only a hold."""
    return DS(status) == DS.PENDING or (DS(status) == DS.DECIDED and disposition is not None and D(disposition) == D.HOLD)


def assert_can_decide(status) -> None:
    if DS(status) == DS.EXECUTED:
        raise QualityError("REJECTION_IS_FINAL")


def assert_decision(disposition, concession_approved_by: str | None, decision_notes: str | None) -> None:
    if D(disposition) == D.USE_AS_IS and not ((concession_approved_by or "").strip() and (decision_notes or "").strip()):
        raise QualityError("CONCESSION_DETAILS_REQUIRED", 400)


def assert_can_execute(status, disposition) -> None:
    if DS(status) == DS.EXECUTED:
        raise QualityError("REJECTION_IS_FINAL")
    if DS(status) != DS.DECIDED or disposition is None:
        raise QualityError("DECISION_REQUIRED")
    if D(disposition) == D.HOLD:
        raise QualityError("HOLD_IS_NOT_FINAL")


def assert_rejection_editable(status) -> None:
    if DS(status) != DS.PENDING:
        raise QualityError("REJECTION_ALREADY_DECIDED")


def assert_rejection_quantity(quantity: Decimal, available: Decimal | None) -> None:
    """A rejection from a check cannot exceed what that check rejected (minus its other rejections)."""
    if quantity <= ZERO:
        raise QualityError("QUANTITY_REQUIRED", 400)
    if available is not None and quantity > available:
        raise QualityError("QUANTITY_EXCEEDS_CHECK", 400, available=str(available))


# Severity order (PROD-QUALITY-FIX-001): a record with several defects takes the highest severity among them.
SEVERITY_RANK = {"minor": 1, "major": 2, "critical": 3}


def highest_severity(severities) -> str | None:
    """The most severe of the given severities (critical > major > minor); None when there are none."""
    values = [str(getattr(s, "value", s)) for s in severities if s is not None]
    return max(values, key=SEVERITY_RANK.__getitem__) if values else None


def check_actions(status, can) -> list[str]:
    s = S(status)
    offered = (["edit", "measure", "start", "close", "cancel"] if s == S.OPEN else ["edit", "measure", "close", "cancel"] if s == S.UNDER_INSPECTION else [])
    return [a for a in offered if can(CHECK_ACTIONS[a])]


def rejection_actions(status, disposition, can) -> list[str]:
    s = DS(status)
    offered = ["edit", "decide"] if s == DS.PENDING else (["decide"] + ([] if disposition and D(disposition) == D.HOLD else ["execute"])) if s == DS.DECIDED else []
    return [a for a in offered if can(REJECTION_ACTIONS[a])]
