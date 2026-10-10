"""The delivery note (SHIP-001, SHIP-004), rendered by the reporting core with the company's external identity. Nothing is stored."""
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.db import Base
from app.core.reporting.contracts import CommonParams, ReportData, ReportDefinition, SectionDefinition
from app.core.reporting.registry import registry
from app.core.reporting.service import template_roots
from app.core.units import unit_label
from app.core.interfaces.reference_lists import names as list_names
from app.shipping.application.support import user_names
from app.shipping.domain import permissions as P
from app.shipping.domain import rules
from app.shipping.infrastructure.models import Shipment, ShipmentReturn

KEY = "shipping.delivery_note"
METHODS = {rules.PICKUP: ("استلام من المصنع", "Collection at the factory"), rules.FACTORY_DELIVERY: ("توصيل بسيارة المصنع", "Factory delivery"),
           rules.CARRIER: ("شركة شحن", "Carrier")}


class DeliveryNoteParams(CommonParams):
    shipment_id: UUID


def _num(value):
    if value is None:
        return ""
    text = format(value.normalize(), "f")
    return text


def build(db, tenant, params, selected) -> ReportData:
    ar = params.lang == "ar"
    tr = lambda a, e: a if ar else e  # noqa: E731
    s = db.scalar(select(Shipment).options(selectinload(Shipment.lines)).where(Shipment.id == params.shipment_id,
                                                                               Shipment.organization_id == tenant.organization_id))
    if s is None:
        raise HTTPException(404, "SHIPMENT_NOT_FOUND")
    orgs = Base.metadata.tables["foundation_organizations"].c
    zone = ZoneInfo(db.scalar(select(orgs.timezone).where(orgs.id == tenant.organization_id)) or "UTC")
    moment = lambda v: v.astimezone(zone).strftime("%d / %m / %Y  %H:%M") if v else ""  # noqa: E731
    names = user_names(db, tenant.organization_id, [s.created_by_user_id])
    party = [(tr("العميل", "Customer"), s.customer_name), (tr("مرجع العميل / أمر الشراء", "Customer reference / PO"), s.customer_reference or "—"),
             (tr("المستلم", "Recipient"), s.consignee_name or s.customer_name), (tr("جوال المستلم", "Recipient phone"), s.consignee_phone or "—"),
             (tr("المدينة", "City"), list_names(db, tenant.organization_id, "city", [s.delivery_city], params.lang).get(s.delivery_city) or "—"), (tr("عنوان التسليم", "Delivery address"), s.delivery_address or "—")]
    if s.delivery_method == rules.CARRIER:
        transport = [(tr("شركة الشحن", "Carrier"), s.carrier_name or "—"), (tr("رقم البوليصة / التتبع", "Waybill / tracking no."), s.tracking_no or "—")]
    else:
        who = tr("المستلم من المصنع", "Collected by") if s.delivery_method == rules.PICKUP else tr("السائق", "Driver")
        transport = [(who, s.driver_name or "—"), (tr("الجوال", "Phone"), s.driver_phone or "—"),
                     (tr("رقم اللوحة", "Vehicle plate"), s.vehicle_plate or "—"), (tr("نوع المركبة", "Vehicle type"), s.vehicle_type or "—")]
        if s.delivery_method == rules.PICKUP:
            transport.append((tr("رقم الهوية / الإقامة", "ID / Iqama no."), s.driver_id_no or "—"))
    transport.append((tr("وقت الخروج", "Dispatched"), moment(s.dispatched_at) or "—"))
    totals = rules.totals(s.lines)
    unit = lambda code: unit_label(code, params.lang)  # noqa: E731
    weight = lambda value, code: f"{_num(value)} {unit(code)}" if value is not None else "—"  # noqa: E731
    lines = [dict(no=line.line_no, description=line.description, width=_num(line.width_mm) or "—", thickness=_num(line.thickness_mm) or "—",
                  quantity=_num(line.quantity), unit=unit(line.unit), weight=weight(line.weight, line.weight_unit), batch=line.production_order_no,
                  delivered=_num(line.delivered_quantity) if s.status == rules.PARTIALLY_DELIVERED else None) for line in s.lines]
    returns = db.scalars(select(ShipmentReturn.return_no).where(ShipmentReturn.organization_id == tenant.organization_id,
                                                                ShipmentReturn.shipment_id == s.id).order_by(ShipmentReturn.created_at)).all()
    document = dict(
        number=s.shipment_no, date=s.shipment_date.strftime("%d / %m / %Y"), method=METHODS[s.delivery_method][0 if ar else 1],
        party=party, transport=transport, lines=lines, notes=s.notes, status=s.status,
        quantities=" · ".join(f"{_num(q)} {unit(u)}" for u, q in totals["quantities"].items()),
        weight=weight(totals["weight_kg"], "kg") if totals["weight_kg"] is not None else "",
        prepared_by=names.get(s.created_by_user_id) or "", driver=s.driver_name if s.delivery_method != rules.CARRIER else s.carrier_name,
        received_by=s.received_by_name, received_at=moment(s.delivered_at), cancel_reason=s.cancel_reason, close_reason=s.close_reason,
        attempt=s.attempt, returns=" · ".join(returns))
    return ReportData(sections=[], subject=s.shipment_no, document=document)


def watermark(data, lang):
    status = data.document.get("status")
    if status == rules.DRAFT:
        return "مسودة" if lang == "ar" else "DRAFT"
    if status == rules.CANCELLED:
        return "ملغى" if lang == "ar" else "CANCELLED"
    if status == rules.NOT_DELIVERED:
        return "لم تُسلَّم" if lang == "ar" else "NOT DELIVERED"
    return ""


def register_delivery_note():
    if registry.get(KEY):
        return
    template_roots.append(Path(__file__).parent / "templates")
    registry.register(ReportDefinition(
        KEY, "shipping", "إشعار تسليم", "Delivery Note", DeliveryNoteParams, (SectionDefinition("document", "الإشعار", "Delivery note"),),
        P.SHIPMENTS_READ, build, "dn_body.html", watermark=watermark, filename_prefix="DN",
        # The corporate header and footer are the core's shared external variant (DOC-IDENTITY-001).
        layout_templates=("dn_document.html", "header.html", "footer.html"), listed=False, classification="external"))
