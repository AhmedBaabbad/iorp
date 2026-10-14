"""Quotation arithmetic: a discount is a percentage of a line, taken before VAT.

    line total      = quantity × unit price
    line discount   = line total × discount % (rounded to the halala on the line)
    after discount  = Σ line total − Σ line discount
    VAT             = after discount × VAT %
    total           = after discount + VAT

A discount on every line is the same percentage on each line; a discount on one line leaves the others at 0 %.
"""
from decimal import ROUND_HALF_UP, Decimal

HALALA = Decimal("0.01")
UNIT_PRICE = Decimal("0.0001")  # a sales order's agreed unit price keeps four places so the net line total stays exact


def money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(HALALA, rounding=ROUND_HALF_UP)


def line_total(quantity: Decimal, unit_price: Decimal) -> Decimal:
    return money(Decimal(quantity) * Decimal(unit_price))


def line_discount(total: Decimal, percent: Decimal) -> Decimal:
    return money(Decimal(total) * Decimal(percent or 0) / 100)


def net_unit_price(unit_price: Decimal, percent: Decimal) -> Decimal:
    """The unit price after the line's discount, as a sales order made from the quotation agrees it."""
    return (Decimal(unit_price) * (100 - Decimal(percent or 0)) / 100).quantize(UNIT_PRICE, rounding=ROUND_HALF_UP)


def vat(taxable: Decimal, rate: Decimal) -> Decimal:
    return money(max(Decimal(taxable), Decimal("0")) * Decimal(rate) / 100)
