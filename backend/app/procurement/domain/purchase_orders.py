"""Purchase orders (PROC-003). Pure: no database, no HTTP.

A purchase order (PO-YYYY-NNNN, prefix in the settings) asks a registered supplier for materials or services at agreed
prices, in Saudi riyals or US dollars, with or without VAT (the organization's rate, 15 % in the Kingdom: a local supplier;
none: an import from abroad). The rate and the default currency are the organization's general settings (master data):

  draft ─approve→ approved ─send→ sent ─(goods receipts)→ partially_received → received
  approved · sent · partially_received ─close(reason)→ closed            (nothing more is expected)
  draft · approved · sent ─cancel(reason)→ cancelled                     (not once anything was received)

Only a draft is edited. Approving needs at least one line, a total above zero and a supplier that is not blocked. What
was received comes from the confirmed goods receipts made against the order's lines; the order moves to partially
received or received by itself. Amounts are computed here, never trusted from the browser: line = quantity × unit
price; subtotal − discount = taxable; VAT = taxable × rate; total = taxable + VAT, each rounded to 0.01.
"""
from decimal import ROUND_HALF_UP, Decimal

from .rules import ProcurementError

DRAFT, APPROVED, SENT, PARTIAL, RECEIVED, CLOSED, CANCELLED = (
    "draft", "approved", "sent", "partially_received", "received", "closed", "cancelled")
STATUSES = (DRAFT, APPROVED, SENT, PARTIAL, RECEIVED, CLOSED, CANCELLED)
# Open for receiving: goods may be received against these.
RECEIVABLE = (APPROVED, SENT, PARTIAL)
FINAL = (RECEIVED, CLOSED, CANCELLED)

CURRENCIES = ("SAR", "USD")
# Who pays what in delivery (Incoterms 2020), for imports; a local delivery usually has none.
INCOTERMS = ("EXW", "FCA", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP")
PAYMENT_TERMS = ("advance", "on_delivery", "net_15", "net_30", "net_45", "net_60", "net_90", "letter_of_credit", "other")
DEFAULT_PREFIX = "PO-"
ZERO, CENT = Decimal("0"), Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(value or 0).quantize(CENT, rounding=ROUND_HALF_UP)


def line_total(quantity, unit_price) -> Decimal:
    return money(Decimal(quantity or 0) * Decimal(unit_price or 0))


def totals(lines: list[tuple], discount, tax_rate) -> dict:
    """lines: (quantity, unit_price). The order's subtotal, discount, taxable amount, VAT and total."""
    subtotal = sum((line_total(q, p) for q, p in lines), ZERO)
    discount = money(discount)
    if discount < ZERO or discount > subtotal:
        raise ProcurementError("DISCOUNT_INVALID", 400, subtotal=str(subtotal))
    taxable = subtotal - discount
    tax = money(taxable * Decimal(tax_rate) / 100)
    return dict(subtotal=subtotal, discount=discount, taxable=taxable, tax_amount=tax, total=taxable + tax)


def assert_header(currency, tax_rate, incoterm, payment_terms, allowed_rates) -> None:
    """allowed_rates: none, the organization's VAT rate, and the rate the order already has (kept if the rate changed since)."""
    if currency not in CURRENCIES:
        raise ProcurementError("CURRENCY_UNKNOWN", 400)
    if Decimal(tax_rate) not in {Decimal(r) for r in allowed_rates}:
        raise ProcurementError("TAX_RATE_UNKNOWN", 400)
    if incoterm is not None and incoterm not in INCOTERMS:
        raise ProcurementError("INCOTERM_UNKNOWN", 400)
    if payment_terms is not None and payment_terms not in PAYMENT_TERMS:
        raise ProcurementError("PAYMENT_TERMS_UNKNOWN", 400)


def assert_line(line) -> None:
    if line.quantity is None or line.quantity <= ZERO:
        raise ProcurementError("QUANTITY_REQUIRED", 400, line=line.line_no)
    if line.unit_price is None or line.unit_price < ZERO:
        raise ProcurementError("UNIT_PRICE_INVALID", 400, line=line.line_no)
    if not (line.description or "").strip():
        raise ProcurementError("DESCRIPTION_REQUIRED", 400, line=line.line_no)


def assert_editable(status) -> None:
    if status != DRAFT:
        raise ProcurementError("ORDER_NOT_DRAFT", order_status=status)


def assert_can_approve(status, line_count, total, supplier_status) -> None:
    assert_editable(status)
    if line_count == 0:
        raise ProcurementError("LINES_REQUIRED", 400)
    if total <= ZERO:
        raise ProcurementError("TOTAL_REQUIRED", 400)
    if supplier_status == "blocked":
        raise ProcurementError("SUPPLIER_BLOCKED")


def assert_can_send(status) -> None:
    if status != APPROVED:
        raise ProcurementError("ORDER_NOT_APPROVED", order_status=status)


def assert_can_close(status, reason) -> None:
    if status not in RECEIVABLE:
        raise ProcurementError("ORDER_NOT_OPEN", order_status=status)
    if not (reason or "").strip():
        raise ProcurementError("REASON_REQUIRED", 400)


def assert_can_cancel(status, received_any, reason) -> None:
    if status not in (DRAFT, APPROVED, SENT):
        raise ProcurementError("ORDER_CANNOT_BE_CANCELLED", order_status=status)
    if received_any:
        raise ProcurementError("ORDER_HAS_RECEIPTS")
    if not (reason or "").strip():
        raise ProcurementError("REASON_REQUIRED", 400)


def assert_receivable(status) -> None:
    if status not in RECEIVABLE:
        raise ProcurementError("ORDER_NOT_OPEN_FOR_RECEIPT", order_status=status)


def received_status(status, ordered_received: list[tuple]) -> str:
    """After a goods receipt is confirmed or cancelled: (ordered, received) per line → the order's status."""
    if status not in RECEIVABLE and status != RECEIVED:
        return status
    if ordered_received and all(received >= ordered for ordered, received in ordered_received):
        return RECEIVED
    if any(received > ZERO for _, received in ordered_received):
        return PARTIAL
    return SENT if status in (SENT, PARTIAL, RECEIVED) else status


def actions(status, can, received_any=False) -> list[str]:
    offered = {
        DRAFT: ["edit", "approve", "cancel"],
        APPROVED: ["send", "receive", "close", "cancel"],
        SENT: ["receive", "close", "cancel"],
        PARTIAL: ["receive", "close"],
    }.get(status, [])
    return [a for a in offered if can(a) and not (a == "cancel" and received_any)]
