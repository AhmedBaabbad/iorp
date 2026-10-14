"""The goods receipt note (PROC-001), rendered by the reporting core with the company's identity. Nothing is stored."""
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.db import Base
from app.core.reporting.contracts import CommonParams, ReportData, ReportDefinition, SectionDefinition
from app.core.reporting.registry import registry
from app.core.reporting.service import template_roots
from app.core.units import to_kilograms, unit_label
from app.procurement.application.support import user_names
from app.procurement.domain import permissions as P
from app.procurement.domain import rules
from app.procurement.infrastructure.models import GoodsReceipt, Supplier

KEY = "procurement.goods_receipt"


class ReceiptParams(CommonParams):
    receipt_id: UUID


def _num(value):
    return "" if value is None else format(value.normalize(), "f")


def build(db, tenant, params, selected) -> ReportData:
    ar = params.lang == "ar"
    say = lambda a, e: a if ar else e  # noqa: E731
    r = db.scalar(select(GoodsReceipt).options(selectinload(GoodsReceipt.lines)).where(GoodsReceipt.id == params.receipt_id,
                                                                                       GoodsReceipt.organization_id == tenant.organization_id))
    if r is None:
        raise HTTPException(404, "RECEIPT_NOT_FOUND")
    supplier = db.get(Supplier, r.supplier_id)
    orgs = Base.metadata.tables["foundation_organizations"].c
    zone = ZoneInfo(db.scalar(select(orgs.timezone).where(orgs.id == tenant.organization_id)) or "UTC")
    moment = lambda v: v.astimezone(zone).strftime("%d / %m / %Y  %H:%M") if v else ""  # noqa: E731
    names = user_names(db, tenant.organization_id, [r.created_by_user_id, r.received_by_user_id])
    unit = lambda code: unit_label(code, params.lang)  # noqa: E731
    v = lambda value: value or "—"  # noqa: E731
    party = [(say("المورد", "Supplier"), r.supplier_name), (say("رمز المورد", "Supplier code"), supplier.supplier_code if supplier else "—"),
             (say("الرقم الضريبي", "VAT no."), v(supplier.vat_number if supplier else None)),
             (say("الجوال", "Phone"), v(supplier.phone if supplier else None))]
    refs = [(say("إشعار تسليم المورد", "Supplier's delivery note"), v(r.supplier_delivery_no)),
            (say("فاتورة المورد", "Supplier's invoice"), v(r.supplier_invoice_no)),
            (say("أمر الشراء", "Purchase order"), v(r.purchase_reference)),
            (say("المركبة / السائق", "Vehicle / driver"), " — ".join(x for x in (r.vehicle_plate, r.driver_name) if x) or "—")]
    if r.driver_name:
        refs.append((say("صفة السائق", "Driver affiliation"), say("داخلي", "Internal") if r.driver_affiliation=="internal" else say("خارجي", "External") if r.driver_affiliation=="external" else say("غير محدد — سجل قديم", "Unclassified — legacy record")))
    lines = [dict(no=line.line_no, description=line.description, lot=line.supplier_lot or "—", quantity=_num(line.quantity), unit=unit(line.unit),
                  packages=str(line.package_count) if line.package_count is not None else "—",
                  weight=f"{_num(line.weight)} {unit(line.weight_unit)}" if line.weight is not None else "—",
                  inspect=say("نعم", "Yes") if line.inspection_required else "—") for line in r.lines]
    weights = [to_kilograms(line.weight, line.weight_unit) for line in r.lines if line.weight is not None]
    per_unit: dict = {}
    for line in r.lines:
        per_unit[line.unit] = per_unit.get(line.unit, 0) + line.quantity
    document = dict(number=r.receipt_no, date=r.receipt_date.strftime("%d / %m / %Y"), status=r.status, party=party, refs=refs, lines=lines,
                    quantities=" · ".join(f"{_num(q)} {unit(u)}" for u, q in per_unit.items()),
                    weight=f"{_num(sum(weights))} {unit('kg')}" if weights else "", notes=r.notes, cancel_reason=r.cancel_reason,
                    prepared_by=names.get(r.created_by_user_id) or "", received_by=names.get(r.received_by_user_id) or "",
                    received_at=moment(r.received_at), driver=r.driver_name or "", any_inspection=any(line.inspection_required for line in r.lines))
    return ReportData(sections=[], subject=r.receipt_no, document=document)


def watermark(data, lang):
    status = data.document.get("status")
    if status == rules.DRAFT:
        return "مسودة" if lang == "ar" else "DRAFT"
    if status == rules.CANCELLED:
        return "ملغى" if lang == "ar" else "CANCELLED"
    return ""


def register_receipt_document():
    if registry.get(KEY):
        return
    root = Path(__file__).parent / "templates"
    if root not in template_roots:
        template_roots.append(root)
    registry.register(ReportDefinition(
        KEY, "procurement", "إشعار استلام مواد", "Goods Receipt Note", ReceiptParams, (SectionDefinition("document", "الإشعار", "Receipt"),),
        P.RECEIPTS_READ, build, "grn_body.html", watermark=watermark, filename_prefix="GRN",
        layout_templates=("grn_document.html", "header.html", "footer.html"), listed=False, classification="external"))
