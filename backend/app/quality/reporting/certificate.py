"""The Certificate of Analysis document (QUAL-COA-001), rendered by the reporting core with the external identity.

Everything printed comes from the certificate record (frozen when the draft was made); nothing is stored.
"""
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from app.core.reporting.contracts import CommonParams, ReportData, ReportDefinition, SectionDefinition
from app.core.reporting.registry import registry
from app.quality.application.support import user_names
from app.quality.domain import permissions as Q
from app.quality.infrastructure.models import QualityCertificate

KEY = "quality.certificate"


class CertificateParams(CommonParams):
    certificate_id: UUID
    lang: str = "en"


def _num(value):
    if value in (None, ""):
        return None
    text = str(value)
    return text.rstrip("0").rstrip(".") if "." in text else text


def _limits(m, ar):
    lower, upper = _num(m.get("lower")), _num(m.get("upper"))
    if lower and upper:
        return f"{lower} – {upper}"
    if lower:
        return ("الأدنى " if ar else "Min. ") + lower
    if upper:
        return ("الأعلى " if ar else "Max. ") + upper
    return "—"


def _result(m, ar):
    if m["kind"] == "attribute":
        verdict = {"conforming": ("مطابق", "Conforming"), "nonconforming": ("غير مطابق", "Not conforming")}.get(m.get("attribute_result") or "", ("—", "—"))
        return " — ".join(p for p in (verdict[0 if ar else 1], m.get("observation")) if p and p != "—") or "—"
    mean, low, high, count = _num(m.get("mean")), _num(m.get("minimum")), _num(m.get("maximum")), m.get("count") or 0
    if count > 1:
        return f"{mean} ({low} – {high}, n={count})"
    return mean or "—"


def build(db, tenant, params, selected) -> ReportData:
    ar = params.lang == "ar"
    tr = lambda a, e: a if ar else e  # noqa: E731
    c = db.scalar(select(QualityCertificate).where(QualityCertificate.id == params.certificate_id, QualityCertificate.organization_id == tenant.organization_id))
    if c is None:
        raise HTTPException(404, "CERTIFICATE_NOT_FOUND")
    names = user_names(db, tenant.organization_id, [c.prepared_by_user_id, c.issued_by_user_id])
    from app.core.interfaces import approvals
    issued = approvals.latest(approvals.signatures(db, tenant.organization_id, "quality_certificate", [c.id])[c.id], "issue")
    supersedes = db.scalar(select(QualityCertificate.certificate_no).where(QualityCertificate.id == c.supersedes_id)) if c.supersedes_id else None
    day = lambda v: v.strftime("%d / %m / %Y") if v else ""  # noqa: E731
    quantity = f"{_num(c.quantity)} {c.unit_label}".strip() + (f" — {c.package_count} " + tr("عبوة", "packages") if c.package_count else "")
    identification = [
        (tr("رقم الشهادة", "COA No."), c.certificate_no or tr("مسودة", "Draft")),
        (tr("تاريخ الإصدار", "Issue date"), day(c.issued_at) if c.issued_at else "—"),
        (tr("العميل", "Customer"), c.customer_name or "—"),
        (tr("أمر شراء العميل", "Customer PO"), c.customer_po or "—"),
        (tr("المنتج", "Product"), c.product_description),
        (tr("الدرجة", "Grade"), c.grade or "—"),
        (tr("رقم الدفعة", "Batch / Lot No."), c.batch_no),
        (tr("الكمية المشمولة", "Quantity covered"), quantity),
        (tr("تاريخ الإنتاج", "Production date"), day(c.production_date) or "—"),
        (tr("تاريخ الفحص", "Inspection date"), day(c.inspection_date) or "—"),
        (tr("الفاتورة / إشعار التسليم", "Invoice / Delivery note"), c.delivery_ref or "—"),
        (tr("المواصفة الفنية المرجعية", "Reference technical data sheet"),
         f"{c.specification_code} — rev {c.specification_revision}" if c.specification_code else "—"),
    ]
    if supersedes:
        identification.append((tr("تحل محل", "Supersedes"), supersedes))
    rows = []
    for m in c.measurements:
        numeric = m["kind"] == "numeric"
        rows.append(dict(
            name=m["name_ar"] if ar else m["name_en"], unit=m.get("unit") or "—",
            target=(_num(m.get("target")) or "—") if numeric else (m.get("requirement") or "—"),
            acceptance=_limits(m, ar) if numeric else (m.get("acceptance") or "—"),
            result=_result(m, ar), method=m.get("method") or "—",
            status={"pass": "PASS", "recorded": tr("مسجَّل", "RECORDED"), "fail": "FAIL"}.get(m["status"], "—"), passed=m["status"] in ("pass", "recorded")))
    conditional = c.inspection_result == "conditional_accept"
    sampling = [
        (tr("حجم العينة", "Sample size"), c.sample_size or "—"),
        (tr("مرجع خطة أخذ العينات", "Sampling reference"), c.sampling_reference or "—"),
        (tr("عينة محفوظة", "Retained sample"), (tr("نعم", "Yes") + (f" — {c.retention_ref}" if c.retention_ref else "")) if c.retained_sample else tr("لا", "No")),
        (tr("سجل الفحص", "Inspection record"), c.inspection_code),
    ]
    document = dict(
        identification=identification, rows=rows, sampling=sampling,
        overall=tr("بانتظار اعتماد الإفراج", "PENDING RELEASE APPROVAL") if c.status == "draft"
        else tr("مُفرَج عنه — مطابق مع انحراف معتمد", "RELEASED — CONFORMING WITH APPROVED DEVIATION") if conditional
        else tr("مُفرَج عنه — مطابق", "RELEASED / CONFORMING"),
        deviation=c.deviation_note if conditional else None, remarks=c.remarks,
        prepared_by=c.inspector_name or names.get(c.prepared_by_user_id) or "", approved_by=approvals.signed_name(issued, names.get(c.issued_by_user_id), params.lang),
        approved_on=day(c.issued_at) if c.issued_at else "", status=c.status, revoke_reason=c.revoke_reason)
    return ReportData(sections=[], subject=c.certificate_no or "DRAFT", document=document)


def watermark(data, lang):
    status = data.document.get("status")
    if status == "draft":
        return "مسودة — غير صالحة" if lang == "ar" else "DRAFT — NOT VALID"
    if status == "revoked":
        return "ملغاة" if lang == "ar" else "REVOKED"
    return ""


def register_certificate():
    if registry.get(KEY):
        return
    registry.register(ReportDefinition(
        KEY, "quality", "شهادة تحليل", "Certificate of Analysis", CertificateParams, (SectionDefinition("document", "الشهادة", "Certificate"),),
        Q.COA_READ, build, "coa_body.html", watermark=watermark, filename_prefix="COA",
        # The corporate header and footer are the core's shared external variant (DOC-IDENTITY-001).
        layout_templates=("coa_document.html", "header.html", "footer.html"), listed=False, classification="external"))
