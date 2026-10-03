"""Final order result (PROD-OUTPUT-001). Pure rules and formulas: no database, no framework.

The result has no status of its own. The production order's status decides:
  completed -> entries can be created, edited and deleted
  closed    -> locked; only signed correction entries against an original
  otherwise -> not available

Summary formulas (per order item, and per unit for the whole order; never across units):
  customer_good   = sum(customer_good)            stock_good   = sum(stock_good)
  good_total      = customer_good + stock_good
  samples_total   = sum(sample)                   samples_loss = sum(sample where counts_as_loss)
  scrap_total     = sum(scrap)                    rework_total = sum(rework)
  loss_total      = scrap_total + samples_loss
  total_output    = good_total + samples_total + scrap_total + rework_total
  fulfillment_pct = customer_good / allocated_qty * 100   (None unless allocated_qty > 0)
  yield_pct       = good_total / total_output * 100       (None unless total_output > 0)
  loss_pct        = loss_total / total_output * 100       (None unless total_output > 0)
  variance_qty    = good_total - planned_qty
Every sum includes correction entries with their sign.
"""
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from app.production.domain.enums import ProductionOrderStatus as S, ResultDisposition as D

ZERO = Decimal(0)
AVAILABLE = frozenset({S.COMPLETED, S.CLOSED})
WRITABLE = S.COMPLETED
CORRECTABLE = S.CLOSED
# Loss is fixed by disposition; samples are the only case the user decides.
FIXED_LOSS = {D.SCRAP: True, D.CUSTOMER_GOOD: False, D.STOCK_GOOD: False, D.REWORK: False}


class ResultError(ValueError):
    def __init__(self, code: str, status: int = 409, **detail):
        super().__init__(code)
        self.code, self.status, self.detail = code, status, detail


def assert_writable(order_status):
    """Create, edit and delete: only while the order is completed."""
    status = S(order_status)
    if status == CORRECTABLE:
        raise ResultError("RESULT_LOCKED", order_status=status.value)
    if status != WRITABLE:
        raise ResultError("RESULT_NOT_AVAILABLE", order_status=status.value)


def assert_correctable(order_status):
    status = S(order_status)
    if status != CORRECTABLE:
        raise ResultError("CORRECTION_REQUIRES_CLOSED_ORDER", order_status=status.value)


def resolve_counts_as_loss(disposition, counts_as_loss: bool | None) -> bool:
    """Forced for every disposition except SAMPLE, which must be chosen explicitly (never turned into scrap)."""
    disposition = D(disposition)
    if disposition in FIXED_LOSS:
        return FIXED_LOSS[disposition]
    if counts_as_loss is None:
        raise ResultError("SAMPLE_LOSS_FLAG_REQUIRED", 422)
    return bool(counts_as_loss)


def assert_customer_cap(allocated: Decimal | None, customer_good_before: Decimal, adding: Decimal):
    """customer_good may never exceed what customers were allocated; the excess belongs in stock_good."""
    if allocated is None or allocated <= ZERO:
        raise ResultError("NO_CUSTOMER_ALLOCATION", 422)
    if customer_good_before + adding > allocated:
        raise ResultError("CUSTOMER_GOOD_EXCEEDS_ALLOCATION", 422, allocated_quantity=str(allocated),
                          customer_good_quantity=str(customer_good_before), requested_quantity=str(adding),
                          excess_quantity=str(customer_good_before + adding - allocated))


def assert_effective_not_negative(effective_before: Decimal, delta: Decimal, field: str = "quantity"):
    if effective_before + delta < ZERO:
        raise ResultError("CORRECTION_MAKES_TOTAL_NEGATIVE", 422, field=field, effective_quantity=str(effective_before), requested_delta=str(delta))


@dataclass(frozen=True)
class Entry:
    item_id: object
    disposition: str
    quantity: Decimal
    unit: str
    counts_as_loss: bool
    secondary_quantity: Decimal | None = None
    secondary_unit: str | None = None


def _pct(numerator: Decimal, denominator: Decimal | None):
    if denominator is None or denominator <= ZERO:
        return None
    return (numerator / denominator * 100).quantize(Decimal("0.01"))


def summarize(entries: list[Entry], planned: Decimal, allocated: Decimal | None) -> dict:
    """The formulas above for one set of entries that share a unit."""
    by = defaultdict(lambda: ZERO)
    samples_loss = ZERO
    secondary = defaultdict(lambda: ZERO)
    for e in entries:
        by[D(e.disposition)] += e.quantity
        if D(e.disposition) == D.SAMPLE and e.counts_as_loss:
            samples_loss += e.quantity
        if e.secondary_unit and e.secondary_quantity is not None:
            secondary[e.secondary_unit] += e.secondary_quantity
    customer_good, stock_good = by[D.CUSTOMER_GOOD], by[D.STOCK_GOOD]
    good_total = customer_good + stock_good
    samples_total, scrap_total, rework_total = by[D.SAMPLE], by[D.SCRAP], by[D.REWORK]
    loss_total = scrap_total + samples_loss
    total_output = good_total + samples_total + scrap_total + rework_total
    planned = planned or ZERO
    return dict(
        customer_good=customer_good, stock_good=stock_good, good_total=good_total,
        samples_total=samples_total, samples_loss=samples_loss, scrap_total=scrap_total,
        loss_total=loss_total, rework_total=rework_total, total_output=total_output,
        planned_qty=planned, allocated_qty=allocated,
        fulfillment_pct=_pct(customer_good, allocated), yield_pct=_pct(good_total, total_output),
        loss_pct=_pct(loss_total, total_output), variance_qty=good_total - planned,
        secondary_totals=[dict(unit=u, quantity=q) for u, q in sorted(secondary.items())],
    )
