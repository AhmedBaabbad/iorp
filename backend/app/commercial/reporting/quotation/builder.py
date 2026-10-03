"""The quotation document (QUOTE-DOC-001): one quote, printed for the customer in Arabic or English.

Reads the quote and its customer within the caller's customer scope and the organization's quotation
settings (signature and terms). The corporate header and footer (identity, legal data, bank accounts)
are the reporting core's external variant. Amounts come from the saved quote; nothing is recalculated here.
"""
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select

from app.commercial.application.quote_settings_service import QuoteSettingsService
from app.commercial.domain.units import unit_label
from app.commercial.infrastructure.models import Customer, Quote
from app.commercial.reporting.customers import providers
from app.commercial.reporting.customers.queries import scoped
from app.core.reporting.contracts import ReportData

CURRENCY = {"SAR": ("ر.س", "SAR"), "USD": ("دولار", "USD")}


def amount(value) -> str:
    return f"{Decimal(value or 0):,.2f}"


def quantity(value) -> str:
    value = Decimal(value or 0)
    return f"{value:,.0f}" if value == value.to_integral_value() else f"{value.normalize():,f}"


def spec_text(spec) -> str:
    if not isinstance(spec, dict):
        return ""
    return " × ".join(str(v) for v in spec.values() if v not in (None, ""))


def describe(item, ar: bool) -> str:
    """The line as printed: its description in the document's language, else the other one, else product and spec."""
    first, second = (item.description_ar, item.description_en) if ar else (item.description_en, item.description_ar)
    text = (first or second or "").strip()
    if text:
        return text
    spec = spec_text(item.requested_spec_json)
    return f"{item.product_type} — {spec}" if spec else item.product_type


def vat_rate(quote) -> Decimal | None:
    if quote.tax_rate is not None:
        return Decimal(quote.tax_rate).normalize()
    taxable = Decimal(quote.subtotal_amount) - Decimal(quote.discount_amount)
    if quote.tax_amount and taxable > 0:  # quotes saved before the rate was stored
        return (Decimal(quote.tax_amount) * 100 / taxable).quantize(Decimal("0.01")).normalize()
    return None


def build(db, tenant, p, selected) -> ReportData:
    ar = p.lang == "ar"
    tr = lambda a, e: a if ar else e  # noqa: E731
    quote = db.scalar(select(Quote).where(Quote.id == p.quote_id, Quote.organization_id == tenant.organization_id))
    if quote is None:
        raise HTTPException(404, "QUOTE_NOT_FOUND")
    # A sales representative sees only their own customers' quotations, like the customer itself.
    customer = db.scalar(scoped(db, tenant).where(Customer.id == quote.customer_id))
    if customer is None:
        raise HTTPException(404, "QUOTE_NOT_FOUND")
    identity = providers.identity_factory(db, tenant)
    zone = ZoneInfo(identity.timezone())
    day = lambda v: v.astimezone(zone).strftime("%d / %m / %Y") if v else ""  # noqa: E731
    currency = CURRENCY.get(quote.currency, (quote.currency, quote.currency))[0 if ar else 1]
    settings = QuoteSettingsService(db, tenant.organization_id).read()
    preparer = identity.user_names([quote.created_by_user_id]).get(quote.created_by_user_id) if settings["show_preparer_name"] else None
    rate = vat_rate(quote)
    items = sorted(quote.items, key=lambda i: i.line_no)
    totals = [(tr("المجموع قبل الضريبة", "Subtotal before VAT"), amount(quote.subtotal_amount), "subtotal")]
    if quote.discount_amount:
        totals.append((tr("الخصم", "Discount"), "- " + amount(quote.discount_amount), "discount"))
    vat_label = tr("ضريبة القيمة المضافة", "VAT") + (f" ({rate}%)" if rate is not None else "")
    totals.append((vat_label, amount(quote.tax_amount), "tax"))
    totals.append((tr("الإجمالي شامل الضريبة", "Total including VAT"), amount(quote.total_amount), "total"))
    terms = [dict(title=(t.title_ar if ar else (t.title_en or t.title_ar)), body=(t.body_ar if ar else (t.body_en or t.body_ar)))
             for t in QuoteSettingsService(db, tenant.organization_id).terms(active_only=True)]
    document = dict(
        number=quote.quote_number, date=day(quote.issue_date), valid_until=day(quote.valid_until),
        customer=customer.name, attention=quote.attention or "", subject=quote.subject or "",
        currency=currency,
        items=[dict(no=i.line_no, description=describe(i, ar), quantity=quantity(i.quantity), unit=unit_label(i.unit, p.lang),
                    unit_price=amount(i.unit_price), total=amount(i.line_total)) for i in items],
        totals=totals, notes=quote.notes or "", terms=terms,
        signature_title=settings["signature_title_ar"] if ar else settings["signature_title_en"], preparer=preparer or "",
    )
    return ReportData(sections=[], subject=quote.quote_number, prepared_for=customer.name, document=document)
