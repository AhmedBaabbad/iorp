"""Corrective actions report (QUAL-CAPA-001): how the corrective actions of the period's non-conformance reports are
followed up — open, late and done on time by owner, the problems that keep coming back, and the effectiveness reviews.
Read-only, from quality's own tables; nothing is stored."""
from collections import Counter, defaultdict
from datetime import datetime

from sqlalchemy import select

from app.core.reporting.contracts import ReportData, ReportLimitError
from app.quality.application.support import user_names
from app.quality.domain import ncr as N
from app.quality.infrastructure.models import NCRAction, NonConformanceItem, NonConformanceReport
from app.quality.reporting.builders import LIMIT, bi, label, local_day, pct, table, text, zone_for  # noqa: F401

LABELS = {
    'open': ('مفتوح', 'Open'), 'investigation': ('تحقيق', 'Investigation'), 'action': ('إجراءات', 'Actions'),
    'verification': ('تحقق', 'Verification'), 'closed': ('مغلق', 'Closed'), 'cancelled': ('ملغى', 'Cancelled'),
    'done': ('منجز', 'Done'), 'correction': ('تصحيح فوري', 'Correction'), 'corrective': ('إجراء تصحيحي', 'Corrective'),
    'preventive': ('إجراء وقائي', 'Preventive'), 'effective': ('فعّال', 'Effective'), 'not_effective': ('غير فعّال', 'Not effective'),
    'pending': ('مستحقة لاحقًا', 'Scheduled'), 'due': ('مستحقة الآن', 'Due now'),
    'man': ('الإنسان', 'Man'), 'machine': ('الآلة', 'Machine'), 'material': ('المواد', 'Material'), 'method': ('الطريقة', 'Method'),
    'measurement': ('القياس', 'Measurement'), 'environment': ('البيئة', 'Environment'),
    'supplier': ('المورد', 'Supplier'), 'item': ('الصنف المتأثر', 'Affected item'), 'cause': ('السبب (6M)', 'Cause (6M)'),
    'material_non_conformance': ('عدم مطابقة مواد', 'Material'), 'product_non_conformance': ('عدم مطابقة منتج', 'Product'),
    'process_non_conformance': ('عدم مطابقة عملية', 'Process'), 'packaging_non_conformance': ('عدم مطابقة تعبئة', 'Packaging'),
    'documentation_non_conformance': ('عدم مطابقة وثائق', 'Documentation'), 'other': ('أخرى', 'Other'),
}


def word(key, lang):
    return LABELS[key][lang == 'en'] if key in LABELS else label(key, lang)


def corrective_actions(db, tenant, params, selected):
    lang, zone, org = params.lang, zone_for(db, tenant), tenant.organization_id
    today = datetime.now(zone).date()
    query = select(NonConformanceReport).where(NonConformanceReport.organization_id == org, NonConformanceReport.status != N.CANCELLED)
    if params.date_from:
        query = query.where(NonConformanceReport.report_date >= params.date_from)
    if params.date_to:
        query = query.where(NonConformanceReport.report_date <= params.date_to)
    if params.source_type:
        query = query.where(NonConformanceReport.source_type.in_(params.source_type))
    if params.severity:
        query = query.where(NonConformanceReport.severity.in_(params.severity))
    reports = db.scalars(query.order_by(NonConformanceReport.report_date).limit(LIMIT + 1)).all()
    if len(reports) > LIMIT:
        raise ReportLimitError()
    by_id = {r.id: r for r in reports}
    actions = db.scalars(select(NCRAction).where(NCRAction.organization_id == org, NCRAction.ncr_id.in_(list(by_id)))
                         .order_by(NCRAction.due_date)).all() if by_id else []
    names = user_names(db, org, [a.owner_user_id for a in actions])
    owner = lambda a: names.get(a.owner_user_id) or a.owner_name or bi('بلا مسؤول / Unassigned', lang)  # noqa: E731
    live = [a for a in actions if a.status != N.ACTION_CANCELLED]
    done = [a for a in live if a.status == N.ACTION_DONE]
    on_time = lambda a: a.due_date is None or local_day(a.completed_at, zone) <= a.due_date  # noqa: E731
    overdue = [a for a in live if N.is_overdue(a, today)]
    closing_days = [(local_day(a.completed_at, zone) - local_day(a.created_at, zone)).days for a in done if a.completed_at]
    sections = []

    if 'kpis' in selected:
        reviewed = Counter(r.effectiveness_result for r in reports if r.effectiveness_result)
        rows = [('تقارير عدم المطابقة / Non-conformance reports', len(reports)),
                ('مغلقة / Closed', sum(1 for r in reports if r.status == N.CLOSED)),
                ('الإجراءات / Actions', len(live)), ('مفتوحة / Open', sum(1 for a in live if a.status == N.ACTION_OPEN)),
                ('متأخرة / Overdue', len(overdue)), ('منجزة / Done', len(done)),
                ('أُنجزت في موعدها % / Done on time %', pct(sum(1 for a in done if on_time(a)), len(done)) or '—'),
                ('متوسط أيام الإنجاز / Average days to complete', round(sum(closing_days) / len(closing_days), 1) if closing_days else '—'),
                ('مراجعات فعّالة / Reviews effective', reviewed[N.EFFECTIVE]), ('مراجعات غير فعّالة / Reviews not effective', reviewed[N.NOT_EFFECTIVE]),
                ('مراجعات مستحقة / Reviews due', sum(1 for r in reports if N.review_due(r, today)))]
        section = table('kpis', 'المؤشرات الرئيسية', 'Key figures', [], [(bi(k, lang), v) for k, v in rows], lang, layout='fields')
        section.cards = [(bi(k, lang), text(v)) for k, v in (rows[2], rows[4], rows[6])]
        sections.append(section)

    if 'owners' in selected:
        per = defaultdict(lambda: [0, 0, 0, 0])  # open, overdue, done, done on time
        for a in live:
            cell = per[owner(a)]
            cell[0] += a.status == N.ACTION_OPEN
            cell[1] += N.is_overdue(a, today)
            cell[2] += a.status == N.ACTION_DONE
            cell[3] += a.status == N.ACTION_DONE and on_time(a)
        rows = [(name, o, late, d, t, pct(t, d) or '—') for name, (o, late, d, t) in sorted(per.items(), key=lambda item: (-item[1][1], -item[1][0]))]
        sections.append(table('owners', 'الإجراءات حسب المسؤول', 'Actions by owner',
                              ['المسؤول / Owner', 'مفتوحة / Open', 'متأخرة / Overdue', 'منجزة / Done', 'في موعدها / On time', 'في موعدها % / On time %'], rows, lang))

    if 'overdue' in selected:
        rows = [(by_id[a.ncr_id].report_number, word(a.kind, lang), a.description, owner(a), a.due_date, (today - a.due_date).days)
                for a in sorted(overdue, key=lambda a: a.due_date)]
        sections.append(table('overdue', 'الإجراءات المتأخرة', 'Overdue actions',
                              ['التقرير / Report', 'النوع / Kind', 'الإجراء / Action', 'المسؤول / Owner', 'الموعد / Due', 'أيام التأخير / Days late'], rows, lang))

    if 'recurrence' in selected:
        # The same keys as a report's recurrence (domain/ncr.py): supplier, affected item by name, kind with its 6M cause.
        groups, shown = defaultdict(set), {}
        for r in reports:
            if r.supplier_id or r.supplier_name:
                key = ('supplier', str(r.supplier_id or r.supplier_name.strip().casefold()))
                groups[key].add(r.id); shown[key] = r.supplier_name or '—'
            if r.root_cause_category:
                key = ('cause', f'{r.root_cause_category}:{text(r.report_type)}')
                groups[key].add(r.id); shown[key] = f'{word(r.root_cause_category, lang)} · {word(text(r.report_type), lang)}'
        if by_id:
            for report_id, name in db.execute(select(NonConformanceItem.non_conformance_report_id, NonConformanceItem.item_name).where(
                    NonConformanceItem.non_conformance_report_id.in_(list(by_id)))).all():
                if name and name.strip():
                    key = ('item', name.strip().casefold())
                    groups[key].add(report_id); shown.setdefault(key, name.strip())
        rows = []
        for key, ids in groups.items():
            if len(ids) >= 2:
                found = sorted((by_id[i] for i in ids), key=lambda r: r.report_date)
                rows.append((word(key[0], lang), shown[key], len(ids), found[0].report_date, found[-1].report_date,
                             ', '.join(r.report_number for r in found[-5:])))
        rows.sort(key=lambda row: -row[2])
        sections.append(table('recurrence', 'المشكلات المتكررة', 'Recurring problems',
                              ['حسب / By', 'القيمة / Value', 'التقارير / Reports', 'الأول / First', 'الأخير / Last', 'آخر التقارير / Latest reports'], rows, lang,
                              'تقريران أو أكثر في الفترة لنفس المورد أو الصنف أو السبب؛ ثلاثة خلال 180 يومًا تجعل المشكلة متكررة لا تُغلق دون إجراء / Two or more reports in the period about the same supplier, item or cause; three within 180 days make a problem recurring, not closed without an action'))

    if 'effectiveness' in selected:
        followed = [r for r in reports if r.effectiveness_due_date or r.effectiveness_result]
        rows = []
        for r in sorted(followed, key=lambda r: r.effectiveness_due_date or r.report_date):
            standing = r.effectiveness_result or ('due' if N.review_due(r, today) else 'pending')
            rows.append((r.report_number, r.title, local_day(r.closed_at, zone) if r.closed_at else '—', r.effectiveness_due_date, word(standing, lang),
                         r.effectiveness_notes))
        sections.append(table('effectiveness', 'مراجعات الفعالية بعد الإغلاق', 'Effectiveness reviews after closing',
                              ['التقرير / Report', 'العنوان / Title', 'أُغلق / Closed', 'موعد المراجعة / Review due', 'النتيجة / Result', 'الملاحظات / Notes'], rows, lang,
                              'غير الفعّال يعيد فتح التقرير إلى الإجراءات / Not effective reopens the report to its actions'))

    filters = []
    if params.date_from:
        filters.append(bi('من / From', lang) + ': ' + str(params.date_from))
    if params.date_to:
        filters.append(bi('إلى / To', lang) + ': ' + str(params.date_to))
    return ReportData(sections=sections, applied_filters=' · '.join(filters))
