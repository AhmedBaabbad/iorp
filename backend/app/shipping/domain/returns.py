"""Returns (SHIP-004): goods that come back after they left the factory. Pure: no database, no HTTP.

A return has its own number (RT-YYYY-NNNN, prefix in the settings) and always refers to its delivery note; the note
itself never changes. Two kinds:
  delivery  not received at the door — the whole load on a failed delivery, or the refused part of a partial one.
            Nothing to approve (the customer never took the goods):  approved ─receive→ received
  customer  the customer received the goods and later sends (some of) them back:
            requested ─approve(note)→ approved ─receive→ received
            requested ─reject(reason)→ rejected
            requested / approved ─cancel(reason)→ cancelled
A customer may return at most what was delivered, less what earlier returns (not rejected or cancelled) took back.
A return requested after the return window (days after delivery, in the settings) is late: approving it needs a note.
The reason says who is responsible: the factory, the carrier, or the customer. The decision on returned goods
(back to stock, rework, هالك) is quality's, later; "return.received" in the events is its hook.
"""
from datetime import timedelta
from decimal import Decimal

from .rules import CARRIER, PICKUP, ShippingError

DELIVERY, CUSTOMER = "delivery", "customer"
KINDS = (DELIVERY, CUSTOMER)
REQUESTED, APPROVED, REJECTED, RECEIVED, CANCELLED = "requested", "approved", "rejected", "received", "cancelled"
STATUSES = (REQUESTED, APPROVED, REJECTED, RECEIVED, CANCELLED)
OPEN = frozenset({REQUESTED, APPROVED})
VOID = frozenset({REJECTED, CANCELLED})  # take nothing back
DEFAULT_PREFIX = "RT-"
DEFAULT_WINDOW_DAYS = 30
DEFAULT_TOLERANCE_PCT = Decimal("1.00")
ZERO = Decimal("0")

FACTORY, CARRIER_PARTY, CUSTOMER_PARTY, UNDETERMINED = "factory", "carrier", "customer", "undetermined"
TRANSIT_DAMAGE, OTHER = "transit_damage", "other"
# reason -> who is responsible (transit damage depends on who carried the goods).
DELIVERY_REASONS: dict[str, str | None] = {
    "customer_refused": CUSTOMER_PARTY, "site_closed": CUSTOMER_PARTY, "no_receiver": CUSTOMER_PARTY,
    "wrong_address": FACTORY, TRANSIT_DAMAGE: None, "quality_issue": FACTORY, OTHER: UNDETERMINED,
}
CUSTOMER_REASONS: dict[str, str | None] = {
    "quality_defect": FACTORY, "spec_mismatch": FACTORY, "wrong_item": FACTORY, TRANSIT_DAMAGE: None,
    "excess_quantity": CUSTOMER_PARTY, "customer_cancelled": CUSTOMER_PARTY, OTHER: UNDETERMINED,
}
REASONS = {DELIVERY: DELIVERY_REASONS, CUSTOMER: CUSTOMER_REASONS}


def assert_reason(kind, reason, note) -> None:
    if reason not in REASONS[kind]:
        raise ShippingError("RETURN_REASON_UNKNOWN", 400, reason=str(reason))
    if reason == OTHER and not (note or "").strip():
        raise ShippingError("RETURN_NOTE_REQUIRED", 400)


def responsibility(kind, reason, method) -> str:
    party = REASONS[kind][reason]
    if party is None:  # transit damage: whoever carried the goods
        return CARRIER_PARTY if method == CARRIER else CUSTOMER_PARTY if method == PICKUP else FACTORY
    return party


def returnable(delivered: Decimal | None, taken_back: Decimal) -> Decimal:
    return max((delivered or ZERO) - taken_back, ZERO)


def assert_quantities(wanted: dict, available: dict, numbers: dict) -> None:
    """wanted / available: line id -> quantity; at least one line, none above what may still be returned."""
    if not wanted:
        raise ShippingError("LINES_REQUIRED", 400)
    for line_id, quantity in wanted.items():
        if line_id not in available:
            raise ShippingError("LINE_NOT_FOUND", 400)
        if quantity <= ZERO or quantity > available[line_id]:
            raise ShippingError("RETURN_QUANTITY_INVALID", 400, line=numbers[line_id], available=str(available[line_id]))


def is_late(delivered_at, requested_at, window_days) -> bool:
    return delivered_at is not None and requested_at > delivered_at + timedelta(days=window_days)


def assert_can_approve(status, late, note) -> None:
    if status != REQUESTED:
        raise ShippingError("RETURN_NOT_REQUESTED", return_status=status)
    if late and not (note or "").strip():
        raise ShippingError("LATE_RETURN_NEEDS_NOTE", 400)


def assert_can_reject(status, reason) -> None:
    if status != REQUESTED:
        raise ShippingError("RETURN_NOT_REQUESTED", return_status=status)
    if not (reason or "").strip():
        raise ShippingError("REASON_REQUIRED", 400)


def assert_can_receive(status, received: dict, expected: dict) -> None:
    """received: line id -> quantity actually back (0 … what was expected)."""
    if status != APPROVED:
        raise ShippingError("RETURN_NOT_APPROVED", return_status=status)
    for line_id, quantity in received.items():
        if line_id not in expected:
            raise ShippingError("LINE_NOT_FOUND", 400)
        if quantity < ZERO or quantity > expected[line_id]:
            raise ShippingError("RECEIVED_QUANTITY_INVALID", 400)


def assert_can_cancel(kind, status, reason) -> None:
    if kind != CUSTOMER:
        raise ShippingError("DELIVERY_RETURN_NOT_CANCELLABLE")  # the goods are on their way back: receive them
    if status not in OPEN:
        raise ShippingError("RETURN_IS_FINAL", return_status=status)
    if not (reason or "").strip():
        raise ShippingError("REASON_REQUIRED", 400)


def actions(kind, status, can) -> list[str]:
    offered = {REQUESTED: ["approve", "reject", "cancel"], APPROVED: ["receive"] if kind == DELIVERY else ["receive", "cancel"]}
    return [a for a in offered.get(status, []) if can(a)]


def share(weight: Decimal | None, part: Decimal, whole: Decimal) -> Decimal | None:
    """The weight of part of a line, in proportion (the receipt records the actual one)."""
    if weight is None or not whole:
        return None
    return (weight * part / whole).quantize(Decimal("0.001"))
