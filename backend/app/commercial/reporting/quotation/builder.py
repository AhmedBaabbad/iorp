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
from app.commercial.application.quote_terms import document_terms
from app.commercial.domain.units import unit_label
from app.core.units import spec_text
from app.commercial.infrastructure.models import Customer, Quote
from app.commercial.reporting.customers import providers
from app.commercial.reporting.customers.queries import scoped
from app.core.interfaces.product_catalog import ProductInfo, products as catalog_products
from app.core.reporting.contracts import ReportData

CURRENCY = {"SAR": ("ر.س", "SAR"), "USD": ("دولار", "USD")}


def amount(value) -> str:
    return f"{Decimal(value or 0):,.2f}"


def quantity(value) -> str:
    value = Decimal(value or 0)
    return f"{value:,.0f}" if value == value.to_integral_value() else f"{value.normalize():,f}"


def spec_in(product: ProductInfo | None, spec, lang: str) -> str:
    """A specification as printed. With the product's template (MD-001): each value in the template's order, a choice by its
    label and a number with its unit, in the document's language; values outside the template follow as written."""
    if not product or not isinstance(spec, dict):
        return spec_text(spec)
    ar, parts, known = lang == "ar", [], set()
    for prop in product.properties:
        known.add(prop.key)
        value = spec.get(prop.key)
        if value in (None, ""):
            continue
        if prop.kind == "choice":
            value = next((o[1] if ar else o[2] for o in prop.options if o[0] == str(value)), value)
        parts.append(f"{value} {unit_label(prop.unit, lang)}" if prop.unit else str(value))
    rest = spec_text({k: v for k, v in spec.items() if k not in known})
    return " × ".join([*parts, *([rest] if rest else [])])


def describe(item, ar: bool, product: ProductInfo | None = None) -> str:
    """The line as printed: its description in the document's language, else the other one, else the product (its name in
    the document's language when it is one of the organization's products) and its specification."""
    first, second = (item.description_ar, item.description_en) if ar else (item.description_en, item.description_ar)
    text = (first or second or "").strip()
    if text:
        return text
    lang = "ar" if ar else "en"
    name = product.name(lang) if product else item.product_type
    spec = spec_in(product, item.requested_spec_json, lang)
    return f"{name} — {spec}" if spec else name


def percent(value) -> str:
    value = Decimal(value or 0)
    return f"{value.normalize():f}%" if value != value.to_integral_value() else f"{value:.0f}%"


def discount_label(items, tr) -> str:
    """"Discount (10%)" when every line has the same percentage, else the lines it applies to: "Discount on line 1 (10%)"."""
    rates = {Decimal(i.discount_percent) for i in items}
    if len(rates) == 1:
        return tr("الخصم", "Discount") + f" ({percent(next(iter(rates)))})"
    lines = [i for i in items if i.discount_amount]
    on = tr("، ", ", ").join(f"{i.line_no} ({percent(i.discount_percent)})" for i in lines)
    return tr("الخصم على البند " if len(lines) == 1 else "الخصم على البنود ", "Discount on line " if len(lines) == 1 else "Discount on lines ") + on


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
    known = catalog_products(db, tenant.organization_id, {i.product_type for i in items})
    # Discount first (a percentage of the lines), then VAT on what remains (domain/pricing.py).
    discounted = any(i.discount_amount for i in items)
    if discounted:
        totals = [(tr("المجموع قبل الخصم", "Subtotal before discount"), amount(quote.subtotal_amount), "subtotal"),
                  (discount_label(items, tr), "- " + amount(quote.discount_amount), "discount"),
                  (tr("المجموع بعد الخصم", "Subtotal after discount"), amount(Decimal(quote.subtotal_amount) - Decimal(quote.discount_amount)), "subtotal")]
    elif quote.discount_amount:  # a quotation from before line discounts, printed as it was saved
        totals = [(tr("المجموع قبل الضريبة", "Subtotal before VAT"), amount(quote.subtotal_amount), "subtotal"),
                  (tr("الخصم", "Discount"), "- " + amount(quote.discount_amount), "discount")]
    else:
        totals = [(tr("المجموع قبل الضريبة", "Subtotal before VAT"), amount(quote.subtotal_amount), "subtotal")]
    vat_label = tr("ضريبة القيمة المضافة", "VAT") + (f" ({rate}%)" if rate is not None else "")
    totals.append((vat_label, amount(quote.tax_amount), "tax"))
    totals.append((tr("الإجمالي شامل الضريبة", "Total including VAT"), amount(quote.total_amount), "total"))
    # Only what is written in the document's language: a term without it is not printed (no mixing of languages).
    terms = [dict(title=title, body=body) for t in document_terms(db, quote)
             for title, body in [(t['title_ar'], t['body_ar']) if ar else (t['title_en'], t['body_en'])] if title and body]
    from app.commercial.application.quote_terms import terms_source
    document = dict(
        terms_source=terms_source(db,quote),
        number=quote.quote_number, date=day(quote.issue_date), valid_until=day(quote.valid_until),
        customer=customer.name, attention=quote.attention or "", subject=quote.subject or "",
        currency=currency,
        items=[dict(no=i.line_no, description=describe(i, ar, known.get(i.product_type)), quantity=quantity(i.quantity), unit=unit_label(i.unit, p.lang),
                    unit_price=amount(i.unit_price), total=amount(i.line_total),
                    discount=(f"{percent(i.discount_percent)} = {amount(i.discount_amount)}" if i.discount_amount else "—"),
                    net=amount(i.net_total)) for i in items],
        discounted=discounted,
        totals=totals, notes=quote.notes or "", terms=terms,
        signature_title=settings["signature_title_ar"] if ar else settings["signature_title_en"], preparer=preparer or "",
    )
    return ReportData(sections=[], subject=quote.quote_number, prepared_for=customer.name, document=document)
