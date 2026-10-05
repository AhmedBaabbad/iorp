"""The non-conformance report document (QUAL-NCR-002), rendered by the reporting core with the company's identity, so it
can also go to a supplier. Everything printed comes from the report; nothing is stored."""
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select

from app.core.db import Base
from app.core.reporting.contracts import CommonParams, ReportData, ReportDefinition, SectionDefinition
from app.core.reporting.registry import registry
from app.core.units import unit_label
from app.quality.application.ncr_service import NCRService
from app.quality.domain import ncr as N
from app.quality.domain import permissions as Q
from app.quality.infrastructure.models import NonConformanceReport

KEY = "quality.ncr"
STATUS = {N.OPEN: ("مفتوح", "Open"), N.INVESTIGATION: ("قيد التحقيق", "Under investigation"), N.ACTION: ("إجراءات تصحيحية", "Corrective action"),
          N.VERIFICATION: ("قيد التحقق", "Verification"), N.CLOSED: ("مغلق", "Closed"), N.CANCELLED: ("ملغى", "Cancelled")}
SEVERITY = {"minor": ("بسيطة", "Minor"), "major": ("جوهرية", "Major"), "critical": ("حرجة", "Critical")}
SOURCE = {"internal_production": ("الإنتاج الداخلي", "Internal production"), "incoming_material": ("مواد واردة", "Incoming material"),
          "supplier": ("مورد", "Supplier"), "warehouse": ("المستودع", "Warehouse"), "customer_return": ("مرتجع عميل", "Customer return"),
          "other": ("أخرى", "Other")}
TYPE = {"material_non_conformance": ("عدم مطابقة مادة", "Material"), "product_non_conformance": ("عدم مطابقة منتج", "Product"),
        "process_non_conformance": ("عدم مطابقة عملية", "Process"), "packaging_non_conformance": ("عدم مطابقة تغليف", "Packaging"),
        "documentation_non_conformance": ("عدم مطابقة مستندات", "Documentation"), "other": ("أخرى", "Other")}
CATEGORY = {"man": ("الإنسان", "Man"), "machine": ("الآلة", "Machine"), "material": ("المادة", "Material"), "method": ("الطريقة", "Method"),
            "measurement": ("القياس", "Measurement"), "environment": ("البيئة", "Environment")}
METHOD = {"five_whys": ("لماذا الخمسة", "5 Whys"), "fishbone": ("مخطط عظم السمكة", "Fishbone"), "other": ("أخرى", "Other")}
DISPOSITION = {"return_to_supplier": ("إرجاع للمورد", "Return to supplier"), "use_as_is": ("قبول كما هو باستثناء", "Use as is (concession)"),
               "sort": ("فرز وإعادة فحص", "Sort and re-inspect"), "rework": ("إعادة تشغيل", "Rework"), "regrade": ("درجة ثانية", "Regrade"),
               "return_to_process": ("إعادة تدوير", "Recycle"), "scrap": ("هالك", "Scrap"), "hold": ("حجز", "Hold")}
KIND = {"correction": ("تصحيح فوري", "Correction"), "corrective": ("إجراء تصحيحي", "Corrective"), "preventive": ("إجراء وقائي", "Preventive")}
ACTION_STATUS = {N.ACTION_OPEN: ("مفتوح", "Open"), N.ACTION_DONE: ("منجز", "Done"), N.ACTION_CANCELLED: ("ملغى", "Cancelled")}
SUPPLIER_ACTION = {"none": ("لا إجراء", "None"), "notify": ("إشعار المورد", "Notice to the supplier"), "return_goods": ("إرجاع البضاعة", "Goods returned"),
                   "scar": ("طلب إجراء تصحيحي من المورد (SCAR)", "Supplier corrective action request (SCAR)")}
CLAIM = {"none": ("لا مطالبة", "None"), "claimed": ("مُطالَب بها", "Claimed"), "accepted": ("مقبولة", "Accepted"), "rejected": ("مرفوضة", "Rejected"),
         "recovered": ("مُستردة", "Recovered")}
COST = {"cost_material": ("المواد", "Material"), "cost_labor": ("العمالة والتوقف", "Labour and downtime"), "cost_scrap": ("الهالك", "Scrap"),
        "cost_transport": ("النقل", "Transport"), "cost_other": ("أخرى", "Other")}


class NCRParams(CommonParams):
    report_id: UUID


def _num(value):
    if value is None:
        return ""
    return format(value.normalize(), "f") if hasattr(value, "normalize") else str(value)


def build(db, tenant, params, selected) -> ReportData:
    ar = params.lang == "ar"
    tr = lambda pair: pair[0] if ar else pair[1]  # noqa: E731
    say = lambda a, e: a if ar else e  # noqa: E731
    r = db.scalar(select(NonConformanceReport).where(NonConformanceReport.id == params.report_id, NonConformanceReport.organization_id == tenant.organization_id))
    if r is None:
        raise HTTPException(404, "NCR_NOT_FOUND")
    orgs = Base.metadata.tables["foundation_organizations"].c
    zone = ZoneInfo(db.scalar(select(orgs.timezone).where(orgs.id == tenant.organization_id)) or "UTC")
    moment = lambda v: v.astimezone(zone).strftime("%d / %m / %Y") if v else ""  # noqa: E731
    day = lambda v: v.strftime("%d / %m / %Y") if v else "—"  # noqa: E731
    service = NCRService(db, tenant)
    view = service.views([r], lambda _code: False, detail=True)[0]
    v = lambda value: value if value not in (None, "") else "—"  # noqa: E731
    identity = [(say("رقم التقرير", "Report no."), r.report_number), (say("التاريخ", "Date"), day(r.report_date)),
                (say("الخطورة", "Severity"), tr(SEVERITY[r.severity])), (say("الحالة", "Status"), tr(STATUS[r.status])),
                (say("المصدر", "Source"), tr(SOURCE[r.source_type.value])), (say("النوع", "Type"), tr(TYPE[r.report_type.value])),
                (say("المرجع", "Reference"), v(r.reference_code)), (say("المسؤول", "Owner"), v(view["owner_name"])),
                (say("تاريخ الاستحقاق", "Due date"), day(r.due_date))]
    source = [(label, value) for label, value in (
        (say("المورد", "Supplier"), r.supplier_name), (say("مرجع المورد (شحنة / فاتورة / دفعة)", "Supplier reference (delivery / invoice / lot)"), r.supplier_reference),
        (say("العميل", "Customer"), r.customer_name), (say("أمر الإنتاج", "Production order"), view["order_number"]),
        (say("المرتجع", "Return"), view["return_no"]), (say("فحص الجودة", "Inspection"), view["inspection_code"]),
        (say("حالة الرفض", "Rejection"), view["rejection_code"])) if value]
    items = [dict(no=i.line_no, name=i.item_name, reference=i.item_reference or "", issue=i.issue_description,
                  quantity=f"{_num(i.quantity_affected)} {unit_label(i.unit, params.lang) if i.unit else ''}".strip() if i.quantity_affected is not None else "—",
                  disposition=tr(DISPOSITION[i.disposition]) if i.disposition else "—", disposition_notes=i.disposition_notes) for i in view["items"]]
    actions = [dict(no=a["line_no"], kind=tr(KIND[a["kind"]]), description=a["description"], owner=v(a["owner_name"]), due=day(a["due_date"]),
                    status=tr(ACTION_STATUS[a["status"]]), evidence=a["evidence"] or a["cancel_reason"] or "") for a in view["corrective_actions"]]
    costs = [(tr(COST[name]), _num(getattr(r, name))) for name in N.COSTS if getattr(r, name) is not None]
    document = dict(
        number=r.report_number, title=r.title, description=r.description, status=r.status, status_label=tr(STATUS[r.status]),
        severity=r.severity, identity=identity, source=source, affected=items, containment=r.containment,
        contained=f"{v(view['contained_by_name'])} · {moment(r.contained_at)}" if r.contained_at else "",
        root_cause=r.root_cause, category=tr(CATEGORY[r.root_cause_category]) if r.root_cause_category else "",
        method=tr(METHOD[r.root_cause_method]) if r.root_cause_method else "", no_action=r.no_action_justification,
        investigated=f"{v(view['investigated_by_name'])} · {moment(r.investigated_at)}" if r.investigated_at else "",
        actions=actions, verification=r.verification_notes, verified_effective=r.status == N.CLOSED and r.verified_at is not None,
        verified=f"{v(view['verified_by_name'])} · {moment(r.verified_at)}" if r.verified_at else "", attempts=r.verification_attempts,
        review_due=str(r.effectiveness_due_date) if r.effectiveness_due_date else "", review_result=r.effectiveness_result or "",
        review_notes=r.effectiveness_notes or "",
        reviewed=f"{v(view['effectiveness_reviewed_by_name'])} · {moment(r.effectiveness_reviewed_at)}" if r.effectiveness_reviewed_at else "",
        supplier_action=tr(SUPPLIER_ACTION[r.supplier_action]) if r.supplier_action != "none" else "", supplier_response=r.supplier_response,
        supplier_responded=day(r.supplier_responded_at) if r.supplier_responded_at else "",
        costs=costs, total_cost=_num(view["total_cost"]) if view["total_cost"] is not None else "",
        claim=f"{_num(r.claim_amount)} — {tr(CLAIM[r.claim_status])}" if r.claim_amount is not None else (tr(CLAIM[r.claim_status]) if r.claim_status != "none" else ""),
        cancel_reason=r.cancel_reason, detected_by=v(view["detected_by_name"]),
        investigator=view["investigated_by_name"] or "", verifier=view["verified_by_name"] or "")
    return ReportData(sections=[], subject=r.report_number, document=document)


def watermark(data, lang):
    return ("ملغى" if lang == "ar" else "CANCELLED") if data.document.get("status") == N.CANCELLED else ""


def register_ncr_document():
    if registry.get(KEY):
        return
    registry.register(ReportDefinition(
        KEY, "quality", "تقرير عدم مطابقة", "Non-Conformance Report", NCRParams, (SectionDefinition("document", "التقرير", "Report"),),
        Q.NCR_READ, build, "ncr_body.html", watermark=watermark, filename_prefix="NCR",
        layout_templates=("ncr_document.html", "header.html", "footer.html"), listed=False, classification="external"))
