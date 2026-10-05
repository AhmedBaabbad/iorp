"""The return note (SHIP-004): goods coming back against a delivery note, rendered by the reporting core with the
company's external identity. Nothing is stored."""
from decimal import Decimal
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
from app.shipping.application.support import user_names
from app.shipping.domain import permissions as P
from app.shipping.domain import returns as R
from app.shipping.infrastructure.models import Shipment, ShipmentReturn
from .document import _num

KEY = "shipping.return_note"
KINDS = {R.DELIVERY: ("مرتجع قبل الاستلام", "Not received at delivery"), R.CUSTOMER: ("مرتجع من العميل بعد الاستلام", "Returned by the customer")}
STATUSES = {R.REQUESTED: ("قيد الاعتماد", "Awaiting approval"), R.APPROVED: ("معتمد — بانتظار الاستلام", "Approved — awaiting receipt"),
            R.REJECTED: ("مرفوض", "Rejected"), R.RECEIVED: ("مُستلم في المصنع", "Received at the factory"), R.CANCELLED: ("ملغى", "Cancelled")}
REASONS = {
    "customer_refused": ("رفض العميل الاستلام", "Customer refused"), "site_closed": ("الموقع مغلق", "Site closed"),
    "no_receiver": ("لا يوجد مستلم", "Nobody to receive"), "wrong_address": ("عنوان خاطئ", "Wrong address"),
    "transit_damage": ("تلف أثناء النقل", "Damaged in transit"), "quality_issue": ("مشكلة جودة ظاهرة", "Visible quality problem"),
    "quality_defect": ("عيب جودة", "Quality defect"), "spec_mismatch": ("مواصفات غير مطابقة", "Not to specification"),
    "wrong_item": ("صنف خاطئ", "Wrong item"), "excess_quantity": ("كمية زائدة", "Excess quantity"),
    "customer_cancelled": ("ألغى العميل الطلب", "Customer cancelled"), "other": ("أخرى", "Other"),
}
PARTIES = {R.FACTORY: ("المصنع", "Factory"), R.CARRIER_PARTY: ("شركة الشحن", "Carrier"), R.CUSTOMER_PARTY: ("العميل", "Customer"),
           R.UNDETERMINED: ("غير محدد", "Undetermined")}


class ReturnNoteParams(CommonParams):
    return_id: UUID


def build(db, tenant, params, selected) -> ReportData:
    ar = params.lang == "ar"
    tr = lambda pair: pair[0] if ar else pair[1]  # noqa: E731
    say = lambda a, e: a if ar else e  # noqa: E731
    r = db.scalar(select(ShipmentReturn).options(selectinload(ShipmentReturn.lines)).where(
        ShipmentReturn.id == params.return_id, ShipmentReturn.organization_id == tenant.organization_id))
    if r is None:
        raise HTTPException(404, "RETURN_NOT_FOUND")
    s = db.get(Shipment, r.shipment_id)
    orgs = Base.metadata.tables["foundation_organizations"].c
    zone = ZoneInfo(db.scalar(select(orgs.timezone).where(orgs.id == tenant.organization_id)) or "UTC")
    moment = lambda v: v.astimezone(zone).strftime("%d / %m / %Y  %H:%M") if v else "—"  # noqa: E731
    names = user_names(db, tenant.organization_id, [r.created_by_user_id, r.decided_by_user_id, r.received_by_user_id])
    unit = lambda code: unit_label(code, params.lang)  # noqa: E731
    weight = lambda value, code: f"{_num(value)} {unit(code)}" if value is not None else "—"  # noqa: E731
    party = [(say("العميل", "Customer"), r.customer_name), (say("إشعار التسليم", "Delivery note"), s.shipment_no),
             (say("تاريخ التسليم", "Delivered"), moment(s.delivered_at) if r.kind == R.CUSTOMER else moment(s.dispatched_at)),
             (say("مرجع العميل", "Customer reference"), r.customer_reference or s.customer_reference or "—")]
    if r.kind == R.DELIVERY and r.attempt > 1:
        party.append((say("المحاولة", "Attempt"), str(r.attempt)))
    cause = [(say("السبب", "Reason"), tr(REASONS[r.reason])),
             (say("المسؤولية", "Responsibility"), tr(PARTIES[r.responsibility])), (say("الحالة", "Status"), tr(STATUSES[r.status]))]
    if r.carrier_claim_ref:
        cause.append((say("مطالبة شركة الشحن", "Carrier claim"), r.carrier_claim_ref))
    if r.is_late:
        cause.append((say("بعد مهلة الإرجاع", "After the return window"), say("نعم", "Yes")))
    received = r.status == R.RECEIVED
    lines = [dict(no=line.line_no, description=line.description, batch=line.production_order_no, width=_num(line.width_mm) or "—",
                  thickness=_num(line.thickness_mm) or "—", unit=unit(line.unit), quantity=_num(line.quantity),
                  received=_num(line.received_quantity) if received else "—",
                  weight=weight(line.received_weight if received and line.received_weight is not None else line.weight, line.weight_unit))
             for line in r.lines]
    weights = [to_kilograms(line.received_weight if received and line.received_weight is not None else line.weight, line.weight_unit)
               for line in r.lines if (line.received_weight if received else line.weight) is not None]
    document = dict(
        number=r.return_no, date=moment(r.requested_at).split("  ")[0], kind=tr(KINDS[r.kind]), party=party, cause=cause, lines=lines,
        weight=weight(sum(weights, Decimal("0")).quantize(Decimal("0.001")), "kg") if weights else "—", details=r.details,
        decision_note=r.decision_note, receipt_notes=r.receipt_notes, cancel_reason=r.cancel_reason, status=r.status,
        prepared_by=names.get(r.created_by_user_id) or "", decided_by=names.get(r.decided_by_user_id) or "",
        received_by=names.get(r.received_by_user_id) or "", received_at=moment(r.received_at) if received else "")
    return ReportData(sections=[], subject=r.return_no, document=document)


def watermark(data, lang):
    status = data.document.get("status")
    if status in (R.REJECTED, R.CANCELLED):
        return {R.REJECTED: ("مرفوض", "REJECTED"), R.CANCELLED: ("ملغى", "CANCELLED")}[status][0 if lang == "ar" else 1]
    return ""


def register_return_note():
    if registry.get(KEY):
        return
    root = Path(__file__).parent / "templates"
    if root not in template_roots:
        template_roots.append(root)
    registry.register(ReportDefinition(
        KEY, "shipping", "إشعار مرتجع", "Return Note", ReturnNoteParams, (SectionDefinition("document", "الإشعار", "Return note"),),
        P.RETURNS_READ, build, "rt_body.html", watermark=watermark, filename_prefix="RT",
        layout_templates=("dn_document.html", "header.html", "footer.html"), listed=False, classification="external"))
