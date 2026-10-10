"""The lifecycle of a quotation and of a sales order (SALES-001). Pure: no database, no HTTP.

Quotation — a negotiation, edited only while it is a draft:

  draft ─issue→ issued ─accept→ accepted                       (final: the agreement a sales order is made from)
                issued ─reject(reason)→ rejected · ─expire→ expired
  issued · rejected · expired ─revise(reason)→ draft           (a new revision; the history keeps every step)

Sales order — the agreement with the customer, the source of production demands:

  draft ─confirm→ confirmed ─(production demands, in parts)→ fully transferred
  confirmed ─revise(reason)→ draft      only before anything was sent to production
  draft · confirmed ─cancel(reason)→ cancelled   (confirmed: only before anything was sent to production)

Once confirmed nothing on it changes: not its lines, quantities, specifications nor prices. Confirming needs a line and a
source: an accepted quotation of the same customer, or a direct order with the customer's own reference (its purchase
order number). Prices are optional; when any is given, the order has a currency.
"""
from decimal import Decimal

DRAFT, ISSUED, ACCEPTED, REJECTED, EXPIRED = "draft", "issued", "accepted", "rejected", "expired"
QUOTE_TRANSITIONS = {
    DRAFT: {ISSUED},
    ISSUED: {ACCEPTED, REJECTED, EXPIRED, DRAFT},
    REJECTED: {DRAFT},
    EXPIRED: {DRAFT},
    ACCEPTED: set(),
}
QUOTE_NEEDS_REASON = {REJECTED, DRAFT}  # rejecting, and revising back to a draft

CONFIRMED, CANCELLED, CONVERTED = "confirmed", "cancelled", "converted_to_production"
ORDER_TRANSITIONS = {
    DRAFT: {CONFIRMED, CANCELLED},
    CONFIRMED: {DRAFT, CANCELLED},
    CANCELLED: set(),
    CONVERTED: set(),  # an earlier status, kept for old orders
}


class LifecycleError(ValueError):
    """A refusal with a code the screens translate (sent as the HTTP detail)."""


def value(status) -> str:
    return getattr(status, "value", status)


def assert_quote_editable(status) -> None:
    if value(status) != DRAFT:
        raise LifecycleError("QUOTE_NOT_DRAFT")


def assert_quote_transition(current, new, reason) -> None:
    current, new = value(current), value(new)
    if new not in QUOTE_TRANSITIONS.get(current, set()):
        raise LifecycleError("QUOTE_INVALID_TRANSITION")
    if new in QUOTE_NEEDS_REASON and not (reason or "").strip():
        raise LifecycleError("QUOTE_REASON_REQUIRED")


def quote_actions(status, can_update, can_create_order) -> list[str]:
    status = value(status)
    out = []
    if can_update:
        out += {DRAFT: ["edit", "issue"], ISSUED: ["accept", "reject", "expire", "revise"], REJECTED: ["revise"], EXPIRED: ["revise"]}.get(status, [])
    if status == ACCEPTED and can_create_order:
        out.append("create_order")
    return out


def assert_order_editable(status) -> None:
    if value(status) != DRAFT:
        raise LifecycleError("ORDER_LOCKED")


def assert_order_transition(current, new, reason, sent_to_production: bool) -> None:
    current, new = value(current), value(new)
    if new not in ORDER_TRANSITIONS.get(current, set()):
        raise LifecycleError("ORDER_INVALID_TRANSITION")
    if current == CONFIRMED and sent_to_production:
        raise LifecycleError("ORDER_HAS_PRODUCTION_HISTORY")
    if (current == CONFIRMED or new == CANCELLED) and not (reason or "").strip():
        raise LifecycleError("ORDER_REASON_REQUIRED")


def assert_can_confirm(line_count, quote_status, customer_reference, priced, currency) -> None:
    """quote_status: the linked quotation's status, or None for a direct order."""
    if line_count == 0:
        raise LifecycleError("ORDER_LINES_REQUIRED")
    if quote_status is not None and value(quote_status) != ACCEPTED:
        raise LifecycleError("ORDER_QUOTE_NOT_ACCEPTED")
    if quote_status is None and not (customer_reference or "").strip():
        raise LifecycleError("ORDER_SOURCE_REQUIRED")
    if priced and not currency:
        raise LifecycleError("ORDER_CURRENCY_REQUIRED")


def fulfilment(ordered_sent: list[tuple[Decimal, Decimal]]) -> str:
    """none · partial · full: how much of the order's lines was sent to production."""
    if not ordered_sent or all(sent <= 0 for _, sent in ordered_sent):
        return "none"
    return "full" if all(sent >= ordered for ordered, sent in ordered_sent) else "partial"


def order_actions(status, sent_to_production, fully_sent, can) -> list[str]:
    """can(action) -> bool checks the permission."""
    status = value(status)
    offered = {
        DRAFT: ["edit", "confirm", "cancel", "delete"],
        CONFIRMED: [*(["transfer"] if not fully_sent else []), *(["revise", "cancel"] if not sent_to_production else [])],
    }.get(status, [])
    return [a for a in offered if can(a)]
