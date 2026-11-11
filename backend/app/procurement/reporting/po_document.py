"""The purchase order document (PROC-003), rendered by the reporting core with the company's identity in Arabic or
English. Amounts come from the saved order; nothing is recalculated or stored here."""
from decimal import Decimal
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.db import Base
from app.core.interfaces.reference_lists import names as list_names
from app.core.reporting.contracts import CommonParams, ReportData, ReportDefinition, SectionDefinition
from app.core.reporting.registry import registry
from app.core.reporting.service import template_roots
from app.core.units import unit_label
from app.procurement.application.purchase_order_service import PurchaseOrderService
from app.procurement.application.support import user_names
from app.procurement.domain import permissions as P
from app.procurement.domain import purchase_orders as PO
from app.procurement.infrastructure.models import Material, PurchaseOrder, Supplier

KEY = "procurement.purchase_order"
CURRENCY = {"SAR": ("ريال سعودي", "Saudi Riyal"), "USD": ("دولار أمريكي", "US Dollar")}
PAYMENT = {"advance": ("دفعة مقدمة", "Advance payment"), "on_delivery": ("عند الاستلام", "On delivery"),
           "net_15": ("آجل 15 يومًا", "Net 15 days"), "net_30": ("آجل 30 يومًا", "Net 30 days"), "net_45": ("آجل 45 يومًا", "Net 45 days"),
           "net_60": ("آجل 60 يومًا", "Net 60 days"), "net_90": ("آجل 90 يومًا", "Net 90 days"),
           "letter_of_credit": ("اعتماد مستندي", "Letter of credit"), "other": ("أخرى", "Other")}
INCOTERM = {"EXW": "Ex Works", "FCA": "Free Carrier", "FOB": "Free On Board", "CFR": "Cost and Freight", "CIF": "Cost, Insurance and Freight",
            "CPT": "Carriage Paid To", "CIP": "Carriage and Insurance Paid To", "DAP": "Delivered At Place", "DPU": "Delivered at Place Unloaded",
            "DDP": "Delivered Duty Paid"}


class OrderParams(CommonParams):
    order_id: UUID


def amount(value) -> str:
    return f"{Decimal(value or 0):,.2f}"


def price(value) -> str:
    """Unit prices keep up to four decimals (resin is priced per kilogram), never fewer than two."""
    value = Decimal(value or 0).normalize()
    places = max(2, min(4, -value.as_tuple().exponent if value.as_tuple().exponent < 0 else 0))
    return f"{value:,.{places}f}"


def quantity(value) -> str:
    value = Decimal(value or 0)
    return f"{value:,.0f}" if value == value.to_integral_value() else f"{value.normalize():,f}"


def build(db, tenant, params, selected) -> ReportData:
    ar = params.lang == "ar"
    say = lambda a, e: a if ar else e  # noqa: E731
    o = db.scalar(select(PurchaseOrder).options(selectinload(PurchaseOrder.lines)).where(
        PurchaseOrder.id == params.order_id, PurchaseOrder.organization_id == tenant.organization_id))
    if o is None:
        raise HTTPException(404, "ORDER_NOT_FOUND")
    supplier = db.get(Supplier, o.supplier_id)
    orgs = Base.metadata.tables["foundation_organizations"].c
    zone = ZoneInfo(db.scalar(select(orgs.timezone).where(orgs.id == tenant.organization_id)) or "UTC")
    day = lambda v: v.strftime("%d / %m / %Y") if v else ""  # noqa: E731
    moment = lambda v: v.astimezone(zone).strftime("%d / %m / %Y") if v else ""  # noqa: E731
    names = user_names(db, tenant.organization_id, [o.created_by_user_id, o.approved_by_user_id])
    from app.core.interfaces import approvals
    signed = approvals.latest(approvals.signatures(db, tenant.organization_id, "purchase_order", [o.id]).get(o.id, []), "approve")
    approver = names.get(o.approved_by_user_id) or ""
    if signed and signed["delegated"]:  # the signer, and whose authority it was
        approver = (f"{signed['signer_name']} — بالتفويض عن {signed['authority_name']}" if params.lang == "ar"
                    else f"{signed['signer_name']} — on behalf of {signed['authority_name']}")
    v = lambda value: value or "—"  # noqa: E731
    # MD-002: the supplier's city and country by their names in the document's language.
    city = list_names(db, tenant.organization_id, "city", [supplier.city], params.lang).get(supplier.city) if supplier else None
    if supplier and supplier.city and supplier.city.endswith('_other') and supplier.city_other:
        city = supplier.city_other
    country = list_names(db, tenant.organization_id, "country", [supplier.country], params.lang).get(supplier.country) if supplier else None
    address = " — ".join(x for x in (supplier.address, city, country) if x) if supplier else ""
    party = [(say("المورد", "Supplier"), o.supplier_name), (say("رمز المورد", "Supplier code"), supplier.supplier_code if supplier else "—"),
             (say("الرقم الضريبي", "VAT no."), v(supplier.vat_number if supplier else None)),
             (say("السجل التجاري", "CR no."), v(supplier.cr_number if supplier else None)),
             (say("العنوان", "Address"), v(address)), (say("عناية", "Attention"), v(o.attention)),
             (say("الجوال", "Phone"), v(supplier.phone if supplier else None)), (say("البريد", "E-mail"), v(supplier.email if supplier else None))]
    payment = PAYMENT[o.payment_terms][not ar] if o.payment_terms else ""
    delivery = [(say("مكان التسليم", "Deliver to"), v(o.delivery_place)),
                (say("تاريخ التوريد المطلوب", "Required by"), v(day(o.required_date))),
                (say("شروط الدفع", "Payment terms"), v(" — ".join(x for x in (payment, o.payment_terms_note) if x))),
                (say("شروط التسليم", "Delivery terms"), f"{o.incoterm} — {INCOTERM[o.incoterm]}" if o.incoterm else "—"),
                (say("عرض المورد", "Supplier's quotation"), v(o.supplier_quote_ref))]
    codes = dict(db.execute(select(Material.id, Material.material_code).where(Material.id.in_([line.material_id for line in o.lines if line.material_id])))
                 .all()) if o.lines else {}
    lines = [dict(no=line.line_no, description=line.description, code=codes.get(line.material_id, ""), notes=line.notes or "",
                  quantity=quantity(line.quantity), unit=unit_label(line.unit, params.lang), unit_price=price(line.unit_price),
                  amount=amount(line.line_total)) for line in o.lines]
    taxed = Decimal(o.tax_rate) > 0
    totals = [(say("المجموع", "Subtotal"), amount(o.subtotal_amount), "subtotal")]
    if o.discount_amount:
        totals += [(say("الخصم", "Discount"), "- " + amount(o.discount_amount), "discount"),
                   (say("المجموع بعد الخصم", "Subtotal after discount"), amount(o.subtotal_amount - o.discount_amount), "subtotal")]
    if taxed:
        totals.append((say("ضريبة القيمة المضافة", "VAT") + f" ({Decimal(o.tax_rate).normalize():f}%)", amount(o.tax_amount), "tax"))
    totals.append((say("الإجمالي شامل الضريبة", "Total including VAT") if taxed else say("الإجمالي", "Total"), amount(o.total_amount), "total"))
    vat_note = "" if taxed else say("الأسعار لا تشمل ضريبة القيمة المضافة (توريد من خارج المملكة أو غير خاضع للضريبة).",
                                    "Prices exclude VAT (supplied from outside the Kingdom or not subject to VAT).")
    document = dict(
        number=o.po_number, date=day(o.order_date), required_date=day(o.required_date), status=o.status, currency=o.currency,
        currency_name=CURRENCY.get(o.currency, (o.currency, o.currency))[not ar], supplier=party, delivery=delivery, subject=o.subject or "",
        lines=lines, totals=totals, vat_note=vat_note, notes=o.notes or "", terms=PurchaseOrderService(db, tenant).terms(params.lang),
        prepared_by=names.get(o.created_by_user_id) or "", approved_by=approver, approved_at=moment(o.approved_at),
        cancel_reason=o.cancel_reason)
    return ReportData(sections=[], subject=o.po_number, prepared_for=o.supplier_name, document=document)


def watermark(data, lang):
    status = data.document.get("status")
    if status == PO.DRAFT:
        return "مسودة — غير معتمد" if lang == "ar" else "DRAFT — NOT APPROVED"
    if status == PO.CANCELLED:
        return "ملغى" if lang == "ar" else "CANCELLED"
    return ""


def register_purchase_order_document():
    if registry.get(KEY):
        return
    root = Path(__file__).parent / "templates"
    if root not in template_roots:
        template_roots.append(root)
    registry.register(ReportDefinition(
        KEY, "procurement", "أمر شراء", "Purchase Order", OrderParams, (SectionDefinition("document", "أمر الشراء", "Purchase order"),),
        P.PO_READ, build, "po_body.html", watermark=watermark, filename_prefix="PO",
        layout_templates=("po_document.html", "header.html", "footer.html"), listed=False, classification="external"))
