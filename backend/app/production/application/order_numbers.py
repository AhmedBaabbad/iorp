"""Production order numbers: PO-YYYY-NNNNNN from a locked per-organization, per-year counter (core/numbering.py).

Both ways of making an order (by hand and from planning) take their number here, so the format is one and a number is
never issued twice, nor reused after an order is deleted or cancelled.
"""
from app.core import numbering
from app.production.infrastructure.models import ProductionOrderCounter

PREFIX, WIDTH = "PO", 6


def next_order_number(db, organization_id) -> str:
    year = numbering.organization_year(db, organization_id)
    value = numbering.take(db, ProductionOrderCounter, value_field="last_value", organization_id=organization_id, year=year)
    return numbering.reference(PREFIX, year, value, WIDTH)
