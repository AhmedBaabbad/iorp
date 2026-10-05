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
The reason says who is responsible: the factory, the carrier, or the customer.
On receipt (SHIP-005) the goods either go back to stock — the warehouse's call, for returns whose reason says nothing
about the goods themselves (refused, site closed, wrong address, excess quantity…) — or to quality, which inspects them
and decides (back to stock, second grade, rework, back to the process, scrap «هالك»): always for a quality reason,
transit damage or "other", and whenever the warehouse sends them. Quality reads the return; shipping reads its decision.
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
# Reasons that put the goods themselves in question: quality inspects them before any decision.
QUALITY_REASONS = frozenset({"quality_issue", "quality_defect", "spec_mismatch", TRANSIT_DAMAGE, OTHER})


def needs_quality(reason) -> bool:
    return reason in QUALITY_REASONS


def quality_status(received: bool, required: bool, lines_to_inspect: int, checks: list[dict], rejections: list[dict]) -> str | None:
    """Where returned goods stand: not yet back (None); back in stock (not_required); waiting for quality (awaiting);
    being inspected (inspecting); decided, some parts still to carry out (decided); finished (done)."""
    if not received:
        return None
    if not required:
        return "not_required"
    live = [c for c in checks if c["status"] != "cancelled"]
    if not live:
        return "awaiting"
    if len({c["return_line_id"] for c in live}) < lines_to_inspect or any(c["status"] != "closed" for c in live):
        return "inspecting"
    return "decided" if any(r["disposition_status"] != "executed" for r in rejections) else "done"


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
