"""Read-only commercial sample sections, bounded by the report's authorized customer set."""
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, or_
from app.commercial.infrastructure.models import Customer, Sample, SampleEvaluation
from app.core.interfaces.product_catalog import products
from app.core.reporting.contracts import TableSection
from app.core.units import SYMBOLS
from . import providers
from .queries import LIMIT, bounded


LABELS = {
    'requested': 'مطلوبة', 'in_preparation': 'قيد التحضير', 'delivered': 'تم التسليم',
    'evaluated': 'تم التقييم', 'cancelled': 'ملغاة', 'pending': 'قيد الانتظار',
    'accepted': 'مقبولة', 'rejected': 'مرفوضة', 'needs_modification': 'يحتاج تعديل',
    'proceed_to_quote': 'الانتقال لعرض سعر', 'revise_sample': 'مراجعة العينة',
    'close_request': 'إغلاق الطلب', 'further_review': 'مراجعة إضافية',
}


def build_sample_sections(db, tenant, params, selected, customers, tz):
    ar = params.lang == 'ar'
    tr = lambda a, e: a if ar else e
    code = lambda v: str(getattr(v, 'value', v)) if v is not None else ''
    label = lambda v: LABELS.get(code(v), code(v)) if ar else code(v).replace('_', ' ').capitalize()
    unit = lambda v: SYMBOLS.get(v, (v or '—', v or '—'))[0 if ar else 1]
    def day(v):
        return (v if v.tzinfo else v.replace(tzinfo=timezone.utc)).astimezone(tz).date().isoformat()
    def readable(v):
        if v is None: return '—'
        if isinstance(v, bool): return tr('نعم', 'Yes') if v else tr('لا', 'No')
        if isinstance(v, dict): return '\n'.join(f'{k}: {readable(x)}' for k,x in v.items())
        if isinstance(v, list): return '\n'.join(readable(x) for x in v)
        return str(v)

    names = {c.id: c.name for c in customers}
    query = select(Sample).join(Customer, Sample.customer_id == Customer.id).where(
        Customer.organization_id == tenant.organization_id, Sample.customer_id.in_(names))
    if params.date_from:
        query = query.where(Sample.request_date >= datetime.combine(params.date_from, time.min, tzinfo=tz).astimezone(timezone.utc))
    if params.date_to:
        query = query.where(Sample.request_date < datetime.combine(params.date_to + timedelta(days=1), time.min, tzinfo=tz).astimezone(timezone.utc))
    if getattr(params, 'product', None): query = query.where(Sample.product_type == params.product)
    if getattr(params, 'sample_status', None): query = query.where(Sample.status == params.sample_status)
    if getattr(params, 'sample_decision', None):
        query = query.where(or_(Sample.sample_decision == 'pending', Sample.sample_decision.is_(None))
            if params.sample_decision == 'pending' else Sample.sample_decision == params.sample_decision)
    samples = bounded(db.scalars(query.order_by(Sample.request_date, Sample.id).limit(LIMIT + 1)))
    definitions = products(db, tenant.organization_id, {s.product_type for s in samples})
    sections = []
    def table(key, title, columns, rows, note=None, cards=None):
        if key in selected:
            sections.append(TableSection(key=key, title=tr(*title), columns=[tr(*c) for c in columns],
                rows=[[readable(v) for v in row] for row in bounded(rows)], note=note, cards=cards or []))
    customer = ('العميل','Customer')
    sample_col = ('العينة','Sample')
    counts = Counter(code(s.status) for s in samples)
    totals = defaultdict(Decimal)
    for s in samples:
        if s.is_sample_requested and s.requested_sample_quantity is not None:
            totals[s.unit] += s.requested_sample_quantity
    cards = [(tr('عدد العينات','Sample count'), str(len(samples)))]
    cards += [(label(k), str(v)) for k,v in sorted(counts.items())]
    cards += [(tr('الكمية المطلوبة','Requested quantity')+' ('+unit(k)+')', str(v)) for k,v in sorted(totals.items(), key=lambda x:x[0] or '')]
    table('samples', ('عينات العملاء','Customer samples'),
        [customer,sample_col,('المنتج','Product'),('تاريخ الطلب','Request date'),('الحالة','Status'),('القرار','Decision'),('الكمية المطلوبة','Requested quantity'),('الوحدة','Unit')],
        [(names[s.customer_id],s.sample_code,definitions[s.product_type].name(params.lang) if s.product_type in definitions else s.product_type,
          day(s.request_date),label(s.status),label(s.sample_decision or 'pending'),
          s.requested_sample_quantity if s.is_sample_requested else None,unit(s.unit) if s.is_sample_requested else '—') for s in samples],
        tr('النطاق حسب تاريخ طلب العينة. الحالات والقرارات حالية ومستقلة. الكميات المطلوبة تشمل الملغاة وليست كميات مسلّمة؛ لا تجمع الوحدات المختلفة.',
           'Period uses sample request date. Status and decision are current and independent. Requested quantities include cancelled samples and are not delivered quantities; different units are never combined.'), cards)
    if 'sample_properties' in selected:
        rows = []
        for s in samples:
            specifications = []
            definition = definitions.get(s.product_type)
            props = {p.key:p for p in definition.properties} if definition else {}
            for k,v in (s.requested_spec_json or {}).items():
                prop = props.get(k)
                title = (prop.name_ar if ar else prop.name_en) if prop else k
                if prop and prop.unit: title += ' ('+unit(prop.unit)+')'
                options = {o[0]:o[1 if ar else 2] for o in prop.options} if prop else {}
                rendered = options.get(v, readable(v)) if isinstance(v, str) else readable(v)
                specifications.append(f'{title}: {rendered}')
            if params.audience == 'internal' and s.notes:
                specifications.append(tr('ملاحظات داخلية','Internal notes')+': '+s.notes)
            specification_text = (' ؛ ' if ar else '; ').join(specifications) or '—'
            rows.append((names[s.customer_id],s.sample_code,specification_text))
        table('sample_properties',('مواصفات العينات','Sample properties'),[customer,sample_col,('المواصفات','Specifications')],rows)
    if 'sample_evaluations' in selected and params.audience == 'internal':
        by_id = {s.id:s for s in samples}
        evaluations = bounded(db.scalars(select(SampleEvaluation).join(Sample, Sample.id == SampleEvaluation.sample_id)
            .join(Customer, Customer.id == Sample.customer_id).where(Customer.organization_id == tenant.organization_id,
                SampleEvaluation.sample_id.in_(by_id)).order_by(SampleEvaluation.evaluation_date, SampleEvaluation.id).limit(LIMIT + 1)))
        users = providers.identity_factory(db,tenant).user_names([e.evaluated_by_user_id for e in evaluations])
        table('sample_evaluations',('تقييمات العينات','Sample evaluations'),
            [customer,sample_col,('تاريخ التقييم','Evaluation date'),('النتيجة','Result'),('الإجراء التالي','Next action'),('قُيّمت بواسطة','Evaluated by'),('التعليقات','Comments')],
            [(names[by_id[e.sample_id].customer_id],by_id[e.sample_id].sample_code,day(e.evaluation_date),label(e.result_status),label(e.next_action),users.get(e.evaluated_by_user_id),e.comments) for e in evaluations],
            tr('جميع تقييمات العينات المطابقة لنطاق تاريخ الطلب، حتى لو كان تاريخ التقييم خارج الفترة.',
               'All evaluations of samples matching the request-date period, including evaluations outside that period.'))
    return sections
