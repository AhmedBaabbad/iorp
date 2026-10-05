"""Quality report data (QUAL-REPORT-001): read-only, from quality's own tables.

Production orders and lines are read through the shared metadata (`shared`), never by importing production's models.
Quantities are kept per unit: lots measured in kg and in rolls are never added together.
"""
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.db import Base
from app.core.reporting.contracts import ReportData, ReportLimitError, TableSection
from app.quality.application.support import CommercialReads, history, user_names
from app.quality.domain import rules
from app.quality.infrastructure.models import QualityCheck, QualityCheckMeasurement, QualityDefect, QualityRejection

LIMIT = 5000
HUNDRED = Decimal(100)


def shared(name):
    """Another module's table, read through the shared metadata: quality never imports its models."""
    return Base.metadata.tables[name].c


# (Arabic, English), with the application's terms: «هالك» for scrap.
LABELS = {
    # check status, result and type
    'open': ('مفتوح', 'Open'), 'under_inspection': ('قيد الفحص', 'Under inspection'), 'closed': ('مغلق', 'Closed'), 'cancelled': ('ملغى', 'Cancelled'),
    'accepted': ('مقبول', 'Accepted'), 'rejected': ('مرفوض', 'Rejected'), 'conditional_accept': ('قبول مشروط', 'Conditional accept'),
    'needs_reinspection': ('يحتاج إعادة فحص', 'Needs reinspection'), 'no_result': ('بلا نتيجة', 'No result'),
    'in_process_inspection': ('فحص أثناء الإنتاج', 'In-process inspection'), 'finished_product_inspection': ('فحص المنتج النهائي', 'Finished product inspection'),
    'sample_inspection': ('فحص العينة', 'Sample inspection'), 'reinspection': ('إعادة فحص', 'Reinspection'),
    'issue_triggered': ('بسبب مشكلة', 'Issue triggered'), 'general': ('عام', 'General'),
    # rejection reason, disposition and its status
    'failed_quality_check': ('فشل فحص الجودة', 'Failed quality check'), 'critical_defect': ('عيب حرج', 'Critical defect'),
    'out_of_spec': ('خارج المواصفات', 'Out of specification'), 'dimension_failure': ('فشل الأبعاد', 'Dimension failure'),
    'surface_failure': ('فشل السطح', 'Surface failure'), 'packaging_failure': ('فشل التعبئة', 'Packaging failure'),
    'labeling_issue': ('مشكلة في التسمية', 'Labeling issue'), 'other': ('أخرى', 'Other'),
    'hold': ('حجز (عزل)', 'Hold (quarantine)'), 'scrap': ('هالك (إتلاف)', 'Scrap'), 'rework': ('إعادة تشغيل', 'Rework'),
    'return_to_process': ('إعادة إلى العملية', 'Return to process'), 'use_as_is': ('استخدام كما هو بموافقة', 'Use as is (concession)'),
    'pending': ('بانتظار القرار', 'Awaiting decision'), 'decided': ('مقرَّر', 'Decided'), 'executed': ('منفَّذ', 'Executed'),
    # defect category and severity
    'dimension': ('أبعاد', 'Dimension'), 'thickness': ('السماكة / القياس', 'Thickness / gauge'), 'surface': ('عيب سطحي', 'Surface defect'),
    'color': ('انحراف اللون', 'Color deviation'), 'strength': ('إخفاق في المتانة', 'Strength failure'), 'winding': ('عيب اللف', 'Winding defect'),
    'weight': ('وزن خارج المعيار', 'Weight out of tolerance'), 'packaging': ('عيب التعبئة', 'Packaging defect'),
    'labeling': ('خطأ في التسمية', 'Labeling error'), 'finish': ('نعومة / الملمس', 'Finish / texture'),
    'minor': ('بسيط', 'Minor'), 'major': ('رئيسي', 'Major'), 'critical': ('حرج', 'Critical'),
    # history actions
    'create': ('إنشاء', 'Created'), 'update': ('تعديل', 'Edited'), 'start': ('بدء الفحص', 'Inspection started'),
    'close': ('إغلاق بالنتيجة', 'Closed with result'), 'cancel': ('إلغاء', 'Cancelled'),
    'decide': ('قرار التصرف', 'Disposition decided'), 'execute': ('تنفيذ القرار', 'Disposition executed'),
    'plan': ('تطبيق خطة القياس', 'Measurement plan applied'),
    # measurement verdicts
    'pass': ('مطابق', 'Pass'), 'fail': ('غير مطابق', 'Fail'), 'recorded': ('مسجَّل', 'Recorded'), 'pending_measurement': ('لم يُقَس', 'Not measured'),
    'conforming': ('مطابق', 'Conforming'), 'nonconforming': ('غير مطابق', 'Not conforming'),
    # filters
    'none': ('دون تجميع', 'None'), 'check_type': ('نوع الفحص', 'Check type'), 'result': ('النتيجة', 'Result'), 'product': ('المنتج', 'Product'),
    'month': ('شهر', 'Month'), 'week': ('أسبوع', 'Week'), 'day': ('يوم', 'Day'),
}


def label(key, lang):
    key = key.value if isinstance(key, Enum) else key
    return LABELS.get(str(key), (str(key), str(key)))[lang == 'en']


def bi(value, lang):
    """A bilingual literal 'عربي / English' in the report's language only."""
    if isinstance(value, str) and ' / ' in value:
        ar, en = value.split(' / ', 1)
        return en if lang == 'en' else ar
    return value


def text(value, zone=None):
    if value is None or value == '':
        return '—'
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
        return value.astimezone(zone or timezone.utc).strftime('%Y-%m-%d %H:%M')
    if isinstance(value, Decimal):
        return format(value.normalize(), 'f')
    return str(value)


def pct(part, whole):
    """A percentage with two decimals ("94.67"); quantities, unlike percentages, drop trailing zeros."""
    return format((Decimal(part) * HUNDRED / Decimal(whole)).quantize(Decimal('0.01')), 'f') if whole else None


def table(key, ar, en, columns, rows, lang, note=None, layout='table'):
    return TableSection(key=key, title=ar if lang == 'ar' else en, columns=[bi(c, lang) for c in columns],
                        rows=[[text(v) for v in row] for row in rows], note=bi(note, lang), layout=layout)


def zone_for(db, tenant):
    orgs = shared('foundation_organizations')
    return ZoneInfo(db.scalar(select(orgs.timezone).where(orgs.id == tenant.organization_id)) or 'UTC')


def local_day(value, zone):
    value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return value.astimezone(zone).date()


def period_of(day: date, period):
    return str(day) if period == 'day' else str(day - timedelta(days=day.weekday())) if period == 'week' else day.strftime('%Y-%m')


def applied_filters(params):
    names = {'date_from': ('من', 'From'), 'date_to': ('إلى', 'To'), 'product': ('المنتج', 'Product'), 'check_type': ('نوع الفحص', 'Check type'),
             'status': ('الحالة', 'Status'), 'result': ('النتيجة', 'Result'), 'grouping': ('التجميع', 'Grouping'), 'reason': ('السبب', 'Reason'),
             'disposition': ('القرار', 'Disposition'), 'disposition_status': ('حالة القرار', 'Decision status'), 'period': ('الفترة', 'Period'),
             'category': ('التصنيف', 'Category'), 'severity': ('الخطورة', 'Severity')}
    en, parts = params.lang == 'en', []
    for key, value in params.model_dump(mode='json').items():
        if key not in names or value in (None, [], 'none'):
            continue
        parts.append(names[key][en] + ': ' + ', '.join(label(v, params.lang) for v in (value if isinstance(value, list) else [value])))
    return ' · '.join(parts)


def order_facts(db, tenant, order_ids):
    """{order_id: (number, product)} and {item_id: (line_no, spec)} through the shared production tables."""
    order_ids = {i for i in order_ids if i}
    if not order_ids:
        return {}, {}
    orders, items = shared('production_orders'), shared('production_order_items')
    numbers = {i: (n, p) for i, n, p in db.execute(select(orders.id, orders.production_order_number, orders.product_type).where(
        orders.organization_id == tenant.organization_id, orders.id.in_(order_ids)))}
    lines = {i: (n, s) for i, n, s in db.execute(select(items.id, items.line_no, items.target_spec_json).where(
        items.production_order_id.in_(list(numbers))))} if numbers else {}
    return numbers, lines


def with_scope(query, model, tenant, params, date_column, zone, order_column, is_datetime=False):
    """Organization, order, product and date range (the date in the organization's calendar)."""
    query = query.where(model.organization_id == tenant.organization_id)
    if params.order_id:
        query = query.where(order_column == params.order_id)
    if params.product:
        orders = shared('production_orders')
        query = query.where(order_column.in_(select(orders.id).where(orders.organization_id == tenant.organization_id, orders.product_type == params.product)))
    if params.date_from:
        query = query.where(date_column >= (datetime.combine(params.date_from, time.min, zone).astimezone(timezone.utc) if is_datetime else params.date_from))
    if params.date_to:
        end = params.date_to + timedelta(days=1)
        query = query.where(date_column < (datetime.combine(end, time.min, zone).astimezone(timezone.utc) if is_datetime else end))
    return query


def fetch(db, query):
    rows = db.scalars(query.limit(LIMIT + 1)).all()
    if len(rows) > LIMIT:
        raise ReportLimitError()
    return rows


# Specification keys as the planning screens name them; other keys are shown as written.
SPEC_LABELS = {
    'width_mm': ('العرض (مم)', 'Width (mm)'), 'thickness_mm': ('السماكة (مم)', 'Thickness (mm)'),
    'thickness_micron': ('السماكة (ميكرون)', 'Thickness (µm)'), 'color': ('اللون', 'Color'),
    'roll_weight_kg': ('وزن الرول (كجم)', 'Roll weight (kg)'), 'weight_kg': ('الوزن (كجم)', 'Weight (kg)'), 'length_m': ('الطول (م)', 'Length (m)'),
}


def spec_text(spec, lang):
    return ' · '.join(f'{SPEC_LABELS.get(k, (k, k))[lang == "en"]}: {v}' for k, v in (spec or {}).items()) or None


# ── Q1: one inspection ──────────────────────────────────────────────────────────────────────────

def check_full(db, tenant, params, selected):
    check = db.scalar(select(QualityCheck).where(QualityCheck.organization_id == tenant.organization_id, QualityCheck.id == params.check_id))
    if check is None:
        raise HTTPException(404, 'QUALITY_CHECK_NOT_FOUND')
    lang, zone, sections = params.lang, zone_for(db, tenant), []
    orders, lines = order_facts(db, tenant, [check.production_order_id])
    number, product = orders.get(check.production_order_id, (None, None))
    line_no, spec = lines.get(check.production_order_item_id, (None, None))
    names = user_names(db, tenant.organization_id, [check.checked_by_user_id, check.closed_by_user_id])
    unit, closed = check.unit or '', text(check.status) == 'closed'
    if 'information' in selected:
        sample = CommercialReads(db, tenant.organization_id).sample_codes([check.sample_id]).get(check.sample_id) if check.sample_id else None
        rows = [('رمز الفحص / Check code', check.inspection_code), ('نوع الفحص / Check type', label(check.check_type, lang)),
                ('الحالة / Status', label(check.status, lang)), ('النتيجة / Result', label(check.result, lang) if check.result else '—'),
                ('وقت الفحص / Inspected at', text(check.check_datetime, zone)), ('الفاحص / Inspector', names.get(check.checked_by_user_id))]
        if check.sample_id:
            rows.append(('العينة / Sample', sample))
        else:
            rows += [('أمر الإنتاج / Production order', number), ('المنتج / Product', product),
                     ('البند / Line', line_no if line_no else ('الأمر كله / Whole order' if number else None)), ('المواصفات / Specification', spec_text(spec, lang))]
        if check.specification_code:
            rows.append(('المواصفة المرجعية / Reference specification', f'{check.specification_code} — rev {check.specification_revision}'))
        if check.lot_values:
            rows.append(('قيم الدفعة التي أدخلها الفاحص / Lot values entered by the inspector', spec_text(check.lot_values, lang)))
        rows += [('بدأ في / Started at', text(check.started_at, zone)),
                 ('أُغلق في / Closed at', f'{text(check.closed_at, zone)} — {names.get(check.closed_by_user_id) or ""}'.strip(' —') if check.closed_at else None)]
        if check.cancel_reason:
            rows.append(('سبب الإلغاء / Cancellation reason', check.cancel_reason))
        sections.append(table('information', 'معلومات الفحص', 'Inspection information', ['الحقل / Field', 'القيمة / Value'],
                              [(bi(k, lang), bi(v, lang) if isinstance(v, str) else v) for k, v in rows], lang, layout='fields'))
    if 'quantities' in selected:
        figures = [('الكمية المفحوصة / Inspected', check.qty_inspected), ('الكمية المقبولة / Accepted', check.qty_accepted if closed else None),
                   ('الكمية المرفوضة / Rejected', check.qty_rejected if closed else None),
                   ('نسبة القبول % / Acceptance %', pct(check.qty_accepted, check.qty_inspected) if closed else None)]
        section = table('quantities', 'الكميات', 'Quantities', [], [], lang,
                        None if closed else 'تُسجَّل الكميات المقبولة والمرفوضة عند إغلاق الفحص / Accepted and rejected quantities are recorded when the check closes')
        section.cards = [(bi(k, lang), f'{text(v)} {unit if "%" not in k else "%"}'.strip()) for k, v in figures if v is not None]
        sections.append(section)
    if 'measurements' in selected:
        sections.append(measurements_section(db, tenant, check, lang))
    if 'defects' in selected:
        defects = db.scalars(select(QualityDefect).where(QualityDefect.organization_id == tenant.organization_id,
                                                         QualityDefect.quality_check_id == check.id).order_by(QualityDefect.defect_date, QualityDefect.created_at)).all()
        sections.append(table('defects', 'العيوب المكتشفة', 'Defects found',
                              ['التاريخ / Date', 'التصنيف / Category', 'الخطورة / Severity', 'العدد / Count', 'الوصف / Description'],
                              [(d.defect_date, label(d.defect_category, lang), label(d.severity, lang), d.defect_count, d.description) for d in defects], lang))
    if 'rejections' in selected:
        rejections = db.scalars(select(QualityRejection).where(QualityRejection.organization_id == tenant.organization_id,
                                                               QualityRejection.quality_check_id == check.id).order_by(QualityRejection.created_at)).all()
        people = user_names(db, tenant.organization_id, [r.decided_by_user_id for r in rejections])
        sections.append(table('rejections', 'حالات الرفض والقرارات', 'Rejections and dispositions',
                              ['الرمز / Code', 'الكمية / Quantity', 'الوحدة / Unit', 'السبب / Reason', 'القرار / Disposition', 'الحالة / Status',
                               'صاحب القرار / Decided by', 'الموافق على الاستثناء / Concession approved by'],
                              [(r.rejection_code, r.quantity_rejected, r.unit, label(r.rejection_reason, lang), label(r.disposition, lang) if r.disposition else '—',
                                label(r.disposition_status, lang), people.get(r.decided_by_user_id), r.concession_approved_by) for r in rejections], lang))
    if 'history' in selected:
        sections.append(table('history', 'سجل الحالة', 'Status history', ['التاريخ / Date', 'الإجراء / Action', 'من / From', 'إلى / To', 'بواسطة / By', 'السبب / Reason'],
                              [(text(h['at'], zone), label(h['action'], lang), label(h['from_status'], lang) if h['from_status'] else '—',
                                label(h['to_status'], lang), h['actor_name'], h['reason']) for h in history(db, tenant.organization_id, 'check', check.id)], lang))
    if 'notes' in selected:
        sections.append(table('notes', 'الملاحظات', 'Notes', ['الملاحظات / Notes'], [[check.notes]] if check.notes else [], lang))
    if 'signatures' in selected:
        sections.append(table('signatures', 'التوقيعات', 'Signatures', ['الفاحص / Inspector', 'مدير الجودة / Quality manager', 'الإنتاج / Production'],
                              [['________________'] * 3], lang))
    final = text(check.status) in ('closed', 'cancelled')
    return ReportData(sections=sections, provisional=not final, subject=check.inspection_code,
                      document={'cancelled': text(check.status) == 'cancelled'})


def limits_text(m):
    if m.lower_limit is not None and m.upper_limit is not None:
        return f'{text(m.lower_limit)} – {text(m.upper_limit)}'
    if m.lower_limit is not None:
        return f'≥ {text(m.lower_limit)}'
    if m.upper_limit is not None:
        return f'≤ {text(m.upper_limit)}'
    return None


def measurements_section(db, tenant, check, lang):
    """The plan copied into the inspection and what was measured: one row per parameter, its limits and verdict."""
    rows = []
    for m in db.scalars(select(QualityCheckMeasurement).where(QualityCheckMeasurement.organization_id == tenant.organization_id,
                                                              QualityCheckMeasurement.quality_check_id == check.id).order_by(QualityCheckMeasurement.position)):
        name = m.name_en if lang == 'en' else m.name_ar
        verdict = label('pending_measurement' if m.status == 'pending' else m.status, lang)
        if m.kind == 'attribute':
            result = label(m.attribute_result, lang) if m.attribute_result else None
            rows.append((name, None, m.requirement, m.acceptance, ' — '.join(p for p in (result, m.observation) if p) or None, None, verdict, m.method))
        else:
            spread = f'{text(m.minimum)} – {text(m.maximum)} (n={m.reading_count})' if m.reading_count else None
            rows.append((name, m.unit, m.target, limits_text(m), m.mean, spread, verdict, m.method))
    return table('measurements', 'نتائج القياس', 'Measurement results',
                 ['الخاصية / Parameter', 'الوحدة / Unit', 'المستهدف / Target', 'حدود القبول / Acceptance', 'المتوسط أو النتيجة / Mean or result',
                  'المدى (العدد) / Range (n)', 'الحكم / Verdict', 'الطريقة / Method'], rows, lang,
                 'يُحكم بالمطابقة إذا وقعت كل القراءات ضمن حدود القبول / A parameter passes when every reading lies within its limits')


# ── Q2: checks summary ──────────────────────────────────────────────────────────────────────────

def checks_summary(db, tenant, params, selected):
    lang, zone = params.lang, zone_for(db, tenant)
    query = with_scope(select(QualityCheck), QualityCheck, tenant, params, QualityCheck.check_datetime, zone, QualityCheck.production_order_id, is_datetime=True)
    for column, values in ((QualityCheck.check_type, params.check_type), (QualityCheck.status, params.status), (QualityCheck.result, params.result)):
        if values:
            query = query.where(column.in_(values))
    order_by = {'code': QualityCheck.inspection_code, 'date_asc': QualityCheck.check_datetime.asc()}.get(params.sort, QualityCheck.check_datetime.desc())
    checks = fetch(db, query.order_by(order_by, QualityCheck.id))
    orders, lines = order_facts(db, tenant, [c.production_order_id for c in checks])
    names = user_names(db, tenant.organization_id, [c.checked_by_user_id for c in checks])
    groups, totals, results = defaultdict(list), defaultdict(lambda: [0, Decimal(0), Decimal(0), Decimal(0)]), defaultdict(int)
    for c in checks:
        number, product = orders.get(c.production_order_id, (None, None))
        closed, unit = text(c.status) == 'closed', c.unit or '—'
        group = {'none': '', 'check_type': label(c.check_type, lang), 'result': label(c.result, lang) if c.result else label('no_result', lang),
                 'product': product or '—', 'month': local_day(c.check_datetime, zone).strftime('%Y-%m')}[params.grouping]
        groups[group].append([c.inspection_code, text(c.check_datetime, zone), label(c.check_type, lang), number, lines.get(c.production_order_item_id, (None,))[0],
                              product, c.qty_inspected, c.qty_accepted if closed else None, c.qty_rejected if closed else None, unit,
                              pct(c.qty_accepted, c.qty_inspected) if closed else None, label(c.status, lang),
                              label(c.result, lang) if c.result else '—', names.get(c.checked_by_user_id)])
        if closed:
            total = totals[unit]
            total[0] += 1; total[1] += c.qty_inspected; total[2] += c.qty_accepted; total[3] += c.qty_rejected
            results[label(c.result, lang) if c.result else label('no_result', lang)] += 1
    sections = []
    if 'kpis' in selected:
        closed_count = sum(t[0] for t in totals.values())
        section = table('kpis', 'المؤشرات الرئيسية', 'Key figures', [], [], lang)
        section.cards = [(bi('عدد الفحوصات / Checks', lang), str(len(checks))), (bi('فحوصات مغلقة / Closed checks', lang), str(closed_count)),
                         (bi('مفتوحة أو قيد الفحص / Open or in inspection', lang), str(sum(1 for c in checks if c.status in rules.ACTIVE)))]
        section.cards += [(bi('نسبة القبول / Acceptance', lang) + ' · ' + unit, f'{text(pct(t[2], t[1]))} %') for unit, t in totals.items()]
        sections.append(section)
    if 'checks' in selected:
        columns = ['الرمز / Code', 'الوقت / Time', 'النوع / Type', 'الأمر / Order', 'البند / Line', 'المنتج / Product', 'المفحوص / Inspected',
                   'المقبول / Accepted', 'المرفوض / Rejected', 'الوحدة / Unit', 'القبول % / Acceptance %', 'الحالة / Status', 'النتيجة / Result', 'الفاحص / Inspector']
        for group, rows in groups.items():
            sections.append(table('checks', ('الفحوصات ' + group).strip(), ('Checks ' + group).strip(), columns, rows, lang))
        if not groups:
            sections.append(table('checks', 'الفحوصات', 'Checks', columns, [], lang))
    if 'totals' in selected:
        sections.append(table('totals', 'الإجماليات حسب الوحدة', 'Totals by unit',
                              ['الوحدة / Unit', 'فحوصات مغلقة / Closed checks', 'المفحوص / Inspected', 'المقبول / Accepted', 'المرفوض / Rejected',
                               'القبول % / Acceptance %', 'الرفض % / Rejection %'],
                              [(u, t[0], t[1], t[2], t[3], pct(t[2], t[1]), pct(t[3], t[1])) for u, t in sorted(totals.items())], lang,
                              'تُحسب الكميات من الفحوصات المغلقة فقط / Quantities count closed checks only'))
    if 'results' in selected:
        section = table('results', 'توزيع النتائج', 'Results distribution', ['النتيجة / Result', 'العدد / Checks'], sorted(results.items(), key=lambda i: -i[1]), lang)
        section.bars = [(k, float(v)) for k, v in sorted(results.items(), key=lambda i: -i[1])]
        sections.append(section)
    filters = applied_filters(params)
    return ReportData(sections=sections, applied_filters=with_order(db, tenant, params, filters))


def with_order(db, tenant, params, filters):
    if not params.order_id:
        return filters
    number, _ = order_facts(db, tenant, [params.order_id])[0].get(params.order_id, ('—', None))
    return ' · '.join(p for p in (bi('الأمر / Order', params.lang) + ': ' + number, filters) if p)


# ── Q3: rejections and dispositions ─────────────────────────────────────────────────────────────

def rejections_analysis(db, tenant, params, selected):
    lang, zone = params.lang, zone_for(db, tenant)
    query = with_scope(select(QualityRejection), QualityRejection, tenant, params, QualityRejection.rejection_date, zone, QualityRejection.production_order_id)
    for column, values in ((QualityRejection.rejection_reason, params.reason), (QualityRejection.disposition, params.disposition),
                           (QualityRejection.disposition_status, params.disposition_status)):
        if values:
            query = query.where(column.in_(values))
    rejections = fetch(db, query.order_by(QualityRejection.rejection_date, QualityRejection.created_at))
    orders, _ = order_facts(db, tenant, [r.production_order_id for r in rejections])
    today = datetime.now(zone).date()
    per_unit = defaultdict(lambda: defaultdict(lambda: [0, Decimal(0)]))   # unit -> outcome -> [count, quantity]
    reasons = defaultdict(lambda: [0, Decimal(0)])                         # (unit, reason)
    trend = defaultdict(lambda: defaultdict(Decimal))                       # unit -> period -> quantity
    for r in rejections:
        outcome = text(r.disposition) if r.disposition and text(r.disposition_status) != 'pending' else 'pending'
        for key in (outcome, 'all'):
            per_unit[r.unit][key][0] += 1; per_unit[r.unit][key][1] += r.quantity_rejected
        reasons[(r.unit, text(r.rejection_reason))][0] += 1; reasons[(r.unit, text(r.rejection_reason))][1] += r.quantity_rejected
        trend[r.unit][period_of(r.rejection_date, params.period)] += r.quantity_rejected
    outcomes = ['pending', 'hold', 'scrap', 'rework', 'return_to_process', 'use_as_is']
    sections = []
    if 'summary' in selected:
        rows = [[unit, f['all'][0], f['all'][1], *[f[o][1] for o in outcomes]] for unit, f in sorted(per_unit.items())]
        section = table('summary', 'ملخص الرفض حسب الوحدة', 'Rejections by unit',
                        ['الوحدة / Unit', 'الحالات / Cases', 'الكمية المرفوضة / Rejected', *[label(o, lang) for o in outcomes]], rows, lang,
                        '«الحجز» وحالات «بانتظار القرار» تمنع إغلاق أمر الإنتاج / Hold and awaiting-decision cases keep the production order from closing')
        section.cards = [(bi('الكمية المرفوضة / Rejected', lang) + ' · ' + unit, text(f['all'][1])) for unit, f in sorted(per_unit.items())]
        section.cards += [(bi('هالك / Scrap', lang) + ' · ' + unit, text(f['scrap'][1])) for unit, f in sorted(per_unit.items()) if f['scrap'][1]]
        sections.append(section)
    if 'reasons' in selected:
        rows = sorted(reasons.items(), key=lambda item: (item[0][0], -item[1][1]))
        sections.append(table('reasons', 'أسباب الرفض', 'Rejection reasons', ['الوحدة / Unit', 'السبب / Reason', 'الحالات / Cases', 'الكمية / Quantity', 'النسبة % / Share %'],
                              [(u, label(reason, lang), c, q, pct(q, per_unit[u]['all'][1])) for (u, reason), (c, q) in rows], lang))
    if 'dispositions' in selected:
        rows = [(u, label(o, lang), f[o][0], f[o][1], pct(f[o][1], f['all'][1])) for u, f in sorted(per_unit.items()) for o in outcomes if f[o][0]]
        sections.append(table('dispositions', 'القرارات', 'Dispositions', ['الوحدة / Unit', 'القرار / Disposition', 'الحالات / Cases', 'الكمية / Quantity', 'النسبة % / Share %'], rows, lang))
    if 'open' in selected:
        unresolved = [r for r in rejections if rules.is_unresolved(r.disposition_status, r.disposition)]
        sections.append(table('open', 'حالات بلا قرار نهائي', 'Cases without a final decision',
                              ['الرمز / Code', 'التاريخ / Date', 'الأمر / Order', 'الكمية / Quantity', 'الوحدة / Unit', 'السبب / Reason', 'الوضع / Standing', 'العمر بالأيام / Age (days)'],
                              [(r.rejection_code, r.rejection_date, orders.get(r.production_order_id, ('—',))[0], r.quantity_rejected, r.unit, label(r.rejection_reason, lang),
                                label(r.disposition, lang) if r.disposition else label('pending', lang), (today - r.rejection_date).days)
                               for r in sorted(unresolved, key=lambda r: r.rejection_date)], lang))
    if 'trend' in selected:
        for unit, points in sorted(trend.items()):
            rows = sorted(points.items())
            section = table('trend', 'اتجاه الكمية المرفوضة ' + unit, 'Rejected quantity trend ' + unit, ['الفترة / Period', 'الكمية / Quantity'], rows, lang)
            section.bars = [(k, float(v)) for k, v in rows[-24:]]
            sections.append(section)
        if not trend:
            sections.append(table('trend', 'اتجاه الكمية المرفوضة', 'Rejected quantity trend', [], [], lang))
    filters = applied_filters(params)
    return ReportData(sections=sections, applied_filters=with_order(db, tenant, params, filters))


# ── Q4: defects ─────────────────────────────────────────────────────────────────────────────────

def defects_analysis(db, tenant, params, selected):
    lang, zone = params.lang, zone_for(db, tenant)
    query = with_scope(select(QualityDefect, QualityCheck.inspection_code, QualityCheck.production_order_id)
                       .join(QualityCheck, QualityCheck.id == QualityDefect.quality_check_id), QualityDefect, tenant, params,
                       QualityDefect.defect_date, zone, QualityCheck.production_order_id).where(QualityCheck.organization_id == tenant.organization_id)
    if params.category:
        query = query.where(QualityDefect.defect_category.in_(params.category))
    if params.severity:
        query = query.where(QualityDefect.severity.in_(params.severity))
    rows = db.execute(query.order_by(QualityDefect.defect_date, QualityDefect.created_at).limit(LIMIT + 1)).all()
    if len(rows) > LIMIT:
        raise ReportLimitError()
    orders, _ = order_facts(db, tenant, [order_id for _, _, order_id in rows])
    severities = ['minor', 'major', 'critical']
    by_category = defaultdict(lambda: dict(records=0, units=0, minor=0, major=0, critical=0))
    for d, _, _ in rows:
        cell = by_category[text(d.defect_category)]
        cell['records'] += 1; cell['units'] += d.defect_count; cell[text(d.severity)] += d.defect_count
    total_units = sum(c['units'] for c in by_category.values())
    ranked = sorted(by_category.items(), key=lambda item: -item[1]['units'])
    sections = []
    if 'pareto' in selected:
        running, table_rows = 0, []
        for category, c in ranked:
            running += c['units']
            table_rows.append((label(category, lang), c['records'], c['units'], pct(c['units'], total_units), pct(running, total_units)))
        section = table('pareto', 'العيوب الأكثر تكرارًا (باريتو)', 'Most frequent defects (Pareto)',
                        ['التصنيف / Category', 'السجلات / Records', 'الوحدات المعيبة / Defective units', 'النسبة % / Share %', 'التراكمي % / Cumulative %'], table_rows, lang,
                        'التصنيفات التي يبلغ تراكمها 80% هي الأولى بالمعالجة / Categories within the first 80% are the first to address')
        section.bars = [(label(category, lang), float(c['units'])) for category, c in ranked[:15]]
        sections.append(section)
    if 'severity' in selected:
        section = table('severity', 'العيوب حسب الخطورة', 'Defects by severity',
                        ['التصنيف / Category', *[label(s, lang) for s in severities], 'الإجمالي / Total'],
                        [(label(category, lang), *[c[s] for s in severities], c['units']) for category, c in ranked], lang)
        section.cards = [(label(s, lang), text(sum(c[s] for c in by_category.values()))) for s in severities]
        sections.append(section)
    if 'serious' in selected:
        serious = [(d, code, order_id) for d, code, order_id in rows if text(d.severity) in ('major', 'critical')]
        sections.append(table('serious', 'العيوب الرئيسية والحرجة', 'Major and critical defects',
                              ['التاريخ / Date', 'الفحص / Check', 'الأمر / Order', 'التصنيف / Category', 'الخطورة / Severity', 'العدد / Count', 'الوصف / Description'],
                              [(d.defect_date, code, orders.get(order_id, ('—',))[0], label(d.defect_category, lang), label(d.severity, lang), d.defect_count, d.description)
                               for d, code, order_id in sorted(serious, key=lambda row: (text(row[0].severity) != 'critical', row[0].defect_date))], lang))
    filters = applied_filters(params)
    return ReportData(sections=sections, applied_filters=with_order(db, tenant, params, filters))


# ── availability ────────────────────────────────────────────────────────────────────────────────

def has_rows(model, check_field=None):
    """Whether the organization (or the chosen check) has rows of this kind; a section without data is not offered."""
    def check(db, tenant, params=None):
        query = select(func.count()).select_from(model).where(model.organization_id == tenant.organization_id)
        check_id = getattr(params, 'check_id', None)
        if check_id and check_field:
            query = query.where(getattr(model, check_field) == check_id)
        return bool(db.scalar(query))
    return check
