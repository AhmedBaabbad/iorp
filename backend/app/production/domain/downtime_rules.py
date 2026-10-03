"""Machine downtime (PROD-DOWNTIME-001). Pure rules: no database, no framework.

A downtime event is a period in which a work center (machine) did not produce. It belongs to
the work center; the production order and run it interrupted are optional context, because a
machine also stops when nothing is scheduled on it.

- Open while it has no end time; closing sets the end and the duration is computed.
- One work center cannot have two stops at the same time: periods never overlap, and only one
  can be open.
- Planned stops (maintenance, breaks, no orders) are outside planned production time; every
  other category, changeover included, is an availability loss. `planned` is derived, never input.
- Linked to an order: allowed while it is in progress, on hold or completed; locked once the
  order is closed; never on a draft, released or cancelled order.
"""
from datetime import datetime, timedelta
from decimal import Decimal

from app.production.domain.enums import DowntimeCategory as C, ProductionOrderStatus as S, ProductionRunStatus as R

PLANNED = frozenset({C.PLANNED_MAINTENANCE, C.BREAK_MEETING, C.NO_ORDERS})
LINKABLE_ORDER = frozenset({S.IN_PROGRESS, S.ON_HOLD, S.COMPLETED})
# Clocks on shop-floor devices drift; a start a little ahead of the server is still "now".
CLOCK_SKEW = timedelta(minutes=5)


class DowntimeError(ValueError):
    def __init__(self, code: str, status: int = 409, **detail):
        super().__init__(code)
        self.code, self.status, self.detail = code, status, detail


def is_planned(category) -> bool:
    return C(category) in PLANNED


def assert_order_linkable(order_status):
    status = S(order_status)
    if status == S.CLOSED:
        raise DowntimeError("DOWNTIME_LOCKED", order_status=status.value)
    if status not in LINKABLE_ORDER:
        raise DowntimeError("ORDER_NOT_RUNNING", order_status=status.value)


def assert_run_usable(run_status):
    if R(run_status) == R.CANCELLED:
        raise DowntimeError("RUN_CANCELLED", 422)


def assert_period(start: datetime, end: datetime | None, now: datetime):
    if start > now + CLOCK_SKEW:
        raise DowntimeError("START_IN_FUTURE", 422)
    if end is not None:
        if end <= start:
            raise DowntimeError("END_BEFORE_START", 422)
        if end > now + CLOCK_SKEW:
            raise DowntimeError("END_IN_FUTURE", 422)


def overlaps(start: datetime, end: datetime | None, other_start: datetime, other_end: datetime | None) -> bool:
    """Half-open periods [start, end); an open period runs until further notice."""
    return (other_end is None or start < other_end) and (end is None or other_start < end)


def duration_minutes(start: datetime, end: datetime | None) -> Decimal | None:
    if end is None:
        return None
    return (Decimal((end - start).total_seconds()) / Decimal(60)).quantize(Decimal("0.01"))


def elapsed_minutes(start: datetime, now: datetime) -> Decimal:
    """Minutes so far of a stop that is still open (never negative)."""
    return max(Decimal(0), (Decimal((now - start).total_seconds()) / Decimal(60)).quantize(Decimal("0.01")))
