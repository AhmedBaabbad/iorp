"""Operational waste (PROD-WASTE-001). Pure rules: no database, no framework.

A waste record is material lost while an order runs: start-up, changeover, trim, a machine
fault. It always belongs to a production order, optionally to one of its runs (which says
where and in which shift). It is not the order's scrap: defective finished product is recorded
once in the final result, and waste is never added to the result's totals.

Whether a record can change is derived from the order's status; waste has no status of its own:
  in_progress, on_hold, completed -> record, edit, delete (completed: late entries)
  closed                          -> locked
  draft, released, cancelled      -> not available
"""
from decimal import Decimal

from app.core.units import UNITS
from app.production.domain.enums import ProductionOrderStatus as S, ProductionRunStatus as R, WasteCategory

WRITABLE = frozenset({S.IN_PROGRESS, S.ON_HOLD, S.COMPLETED})
LOCKED = S.CLOSED


class WasteError(ValueError):
    def __init__(self, code: str, status: int = 409, **detail):
        super().__init__(code)
        self.code, self.status, self.detail = code, status, detail


def assert_writable(order_status):
    status = S(order_status)
    if status == LOCKED:
        raise WasteError("WASTE_LOCKED", order_status=status.value)
    if status not in WRITABLE:
        raise WasteError("WASTE_NOT_AVAILABLE", order_status=status.value)


def assert_unit(unit):
    """A waste quantity's unit is a code of the central list (app/core/units.py), the same codes quotations, orders and
    shipments use; never free text or a translated label. The list is global and has no inactive codes."""
    if unit not in UNITS:
        raise WasteError("UNIT_UNKNOWN", 422, unit=unit)


def split_categories(total: Decimal, lines) -> list[tuple[str, Decimal]]:
    """A record's categories with their share of its quantity (PROD-QUALITY-FIX-001).

    lines: (category, quantity or None). One category takes the whole quantity (its own, when given, must equal it).
    Several categories each need a quantity > 0, no category twice, and the shares must add up to the record's
    quantity exactly: a unit of waste is counted under one category only, so category totals never double count.
    """
    lines = [(WasteCategory(category).value, quantity) for category, quantity in lines]
    if not lines:
        raise WasteError("WASTE_CATEGORY_REQUIRED", 422)
    names = [category for category, _ in lines]
    if len(names) != len(set(names)):
        raise WasteError("WASTE_CATEGORY_DUPLICATE", 422, categories=sorted({n for n in names if names.count(n) > 1}))
    if len(lines) == 1 and lines[0][1] is None:
        return [(lines[0][0], total)]
    for category, quantity in lines:
        if quantity is None:
            raise WasteError("WASTE_CATEGORY_QUANTITY_REQUIRED", 422, category=category)
        if not quantity.is_finite() or quantity <= 0:
            raise WasteError("WASTE_CATEGORY_QUANTITY_INVALID", 422, category=category)
    shares = sum((quantity for _, quantity in lines), Decimal(0))
    if shares != total:
        raise WasteError("WASTE_CATEGORY_TOTAL_MISMATCH", 422, quantity_wasted=str(total), categories_total=str(shares))
    return [(category, quantity) for category, quantity in lines]


def assert_run_usable(run_order_id, order_id, run_status):
    """A run can carry waste only for its own order, and not once it was cancelled."""
    if run_order_id != order_id:
        raise WasteError("RUN_NOT_IN_ORDER", 422)
    if R(run_status) == R.CANCELLED:
        raise WasteError("RUN_CANCELLED", 422)


def resolve_work_center(requested, run_work_center, order_work_center):
    """Where the waste happened: the run's work center, else the one given, else the order's."""
    if run_work_center is not None:
        if requested is not None and requested != run_work_center:
            raise WasteError("WORK_CENTER_MISMATCH", 422)
        return run_work_center
    return requested or order_work_center
