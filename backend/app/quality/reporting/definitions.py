"""The quality report center (QUAL-REPORT-001), registered through the shared reporting contract."""
from pathlib import Path

from app.core.reporting.contracts import ReportDefinition, SectionDefinition as Section
from app.core.reporting.registry import registry
from app.core.reporting.service import template_roots
from app.quality.domain import permissions as Q
from app.quality.domain import report_permissions as R
from app.quality.infrastructure.models import QualityCheckMeasurement, QualityDefect, QualityRejection
from app.quality.reporting import builders as b
from app.quality.reporting.capa_report import corrective_actions
from app.quality.reporting.certificate import register_certificate
from app.quality.reporting.ncr_document import register_ncr_document
from app.quality.reporting.schemas import CheckParams, ChecksSummaryParams, CorrectiveActionsParams, DefectsParams, RejectionsParams


def watermark(data, lang):
    if data.document.get('cancelled'):
        return 'فحص ملغى' if lang == 'ar' else 'Cancelled inspection'
    if data.provisional:
        return 'تقرير مرحلي — الفحص لم يُغلق' if lang == 'ar' else 'Interim report — inspection not closed'
    return ''


def register_reports():
    if registry.get('quality.check_full'):
        return
    template_roots.append(Path(__file__).parent / 'templates')
    check_sections = (
        Section('information', 'معلومات الفحص', 'Inspection information'), Section('quantities', 'الكميات', 'Quantities'),
        Section('measurements', 'نتائج القياس', 'Measurement results', available=b.has_rows(QualityCheckMeasurement, 'quality_check_id')),
        Section('defects', 'العيوب المكتشفة', 'Defects found', requires_permission=Q.DEFECTS_READ, available=b.has_rows(QualityDefect, 'quality_check_id')),
        Section('rejections', 'حالات الرفض والقرارات', 'Rejections and dispositions', requires_permission=Q.REJECTIONS_READ,
                available=b.has_rows(QualityRejection, 'quality_check_id')),
        Section('history', 'سجل الحالة', 'Status history'), Section('notes', 'الملاحظات', 'Notes'), Section('signatures', 'التوقيعات', 'Signatures'))
    reports = [
        ('check_full', 'تقرير فحص الجودة', 'Quality check report', CheckParams, check_sections, b.check_full, 'portrait', (Q.CHECKS_READ,), ('check_id',)),
        ('checks_summary', 'ملخص فحوصات الجودة', 'Quality checks summary', ChecksSummaryParams,
         (Section('kpis', 'المؤشرات الرئيسية', 'Key figures'), Section('checks', 'الفحوصات', 'Checks'),
          Section('totals', 'الإجماليات حسب الوحدة', 'Totals by unit'), Section('results', 'توزيع النتائج', 'Results distribution')),
         b.checks_summary, 'landscape', (Q.CHECKS_READ,), ()),
        ('rejections_analysis', 'تحليل الرفض والقرارات', 'Rejections and dispositions analysis', RejectionsParams,
         (Section('summary', 'ملخص الرفض', 'Rejections summary'), Section('reasons', 'أسباب الرفض', 'Rejection reasons'),
          Section('dispositions', 'القرارات', 'Dispositions'), Section('open', 'حالات بلا قرار نهائي', 'Cases without a final decision'),
          Section('trend', 'الاتجاه', 'Trend')),
         b.rejections_analysis, 'landscape', (Q.REJECTIONS_READ,), ()),
        ('defects_analysis', 'تحليل العيوب', 'Defects analysis', DefectsParams,
         (Section('pareto', 'العيوب الأكثر تكرارًا', 'Most frequent defects'), Section('severity', 'العيوب حسب الخطورة', 'Defects by severity'),
          Section('serious', 'العيوب الرئيسية والحرجة', 'Major and critical defects')),
         b.defects_analysis, 'landscape', (Q.DEFECTS_READ,), ()),
        ('corrective_actions', 'متابعة الإجراءات التصحيحية', 'Corrective actions follow-up', CorrectiveActionsParams,
         (Section('kpis', 'المؤشرات الرئيسية', 'Key figures'), Section('owners', 'الإجراءات حسب المسؤول', 'Actions by owner'),
          Section('overdue', 'الإجراءات المتأخرة', 'Overdue actions'), Section('recurrence', 'المشكلات المتكررة', 'Recurring problems'),
          Section('effectiveness', 'مراجعات الفعالية', 'Effectiveness reviews')),
         corrective_actions, 'landscape', (Q.NCR_READ,), ()),
    ]
    for key, ar, en, schema, sections, builder, orientation, required, context in reports:
        registry.register(ReportDefinition('quality.' + key, 'quality', ar, en, schema, sections, 'reports:quality:' + key, builder, 'quality_body.html',
                                           orientation, required_permissions=required, context_fields=context,
                                           watermark=watermark if key == 'check_full' else None,
                                           classification='internal', department=('الجودة', 'Quality')))
    assert {d.permission for d in registry.definitions.values() if d.module == 'quality' and d.listed} == set(R.ALL)
    register_certificate()  # QUAL-COA-001: a document opened from its record, not listed in the center
    register_ncr_document()  # QUAL-NCR-002: opened from the report, not listed in the center
