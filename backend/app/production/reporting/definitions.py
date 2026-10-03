from pathlib import Path
from app.core.reporting.contracts import ReportDefinition, SectionDefinition as Section
from app.core.reporting.registry import registry
from app.core.reporting.service import template_roots
from app.production.reporting import builders as b
from app.production.reporting.schemas import OrderParams, SummaryParams, AnalysisParams, WorkforceParams


def register_reports():
    if registry.get('production.order_full'):
        return
    template_roots.append(Path(__file__).parent / 'templates')
    order_sections=(
        Section('information','معلومات الأمر','Order information'), Section('items','البنود والمواصفات','Items and specifications'),
        Section('allocations','طلبات العملاء والتخصيصات','Customer demand and allocations'), Section('history','تاريخ الحالة','Status history'),
        Section('execution','التشغيل','Execution',available=b.has_data(b.ProductionRun,'production_order_id')),
        Section('workforce','فريق التشغيل','Execution team',requires_permission='workforce:members:read',available=b.has_data(b.ProductionRunMember)),
        Section('downtime','التوقفات','Downtime',available=b.has_data(b.DowntimeEvent,'production_order_id')),
        Section('waste','الهدر التشغيلي','Operational waste',available=b.has_data(b.WasteRecord,'production_order_id')),
        Section('result','النتيجة النهائية','Final result',available=b.result_available),
        # Quality's inspections and rejections of the order, for users who may read them (QUAL-REPORT-001).
        Section('quality_checks','فحوصات الجودة','Quality checks',requires_permission='quality:quality_checks:read',available=b.quality_rows('quality_checks')),
        Section('quality_rejections','حالات رفض الجودة','Quality rejections',requires_permission='quality:rejections:read',available=b.quality_rows('quality_rejections')),
        Section('notes','الملاحظات','Notes'),Section('signatures','التوقيعات','Signatures'))
    for key,ar,en,schema,sections,builder,orientation,available in [
        ('order_full','تقرير أمر الإنتاج','Production order report',OrderParams,order_sections,b.order_full,'portrait',None),
        ('orders_summary','ملخص أوامر الإنتاج','Production orders summary',SummaryParams,(Section('orders','الأوامر','Orders'),Section('totals','الإجماليات','Totals')),b.orders_summary,'landscape',None),
        ('results_analysis','تحليل نتائج الإنتاج','Production results analysis',AnalysisParams,(Section('analysis','التحليل','Analysis'),Section('reasons','الأسباب','Reasons'),Section('trend','الاتجاه','Trend')),b.results_analysis,'landscape',None),
        ('shift_workforce','الورديات والقوى العاملة','Shift workforce',WorkforceParams,(Section('rosters','تشكيلات الورديات','Shift rosters',requires_permission='workforce:members:read'),Section('participation','المشاركة الفعلية','Recorded participation',requires_permission='workforce:members:read',available=b.has_data(b.ProductionRunMember))),b.shift_workforce,'landscape',b.has_data(b.ShiftRoster))]:
        registry.register(ReportDefinition('production.'+key,'production',ar,en,schema,sections,'reports:production:'+key,builder,'production_body.html',orientation,available,
            watermark=lambda data, lang: ('تقرير مرحلي — غير نهائي' if lang == 'ar' else 'Interim report — not final') if data.provisional else '',
            context_fields=('order_id',), classification='internal', department=('الإنتاج', 'Production')))
