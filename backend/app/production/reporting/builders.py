from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.db import Base
from app.core.reporting.contracts import ReportData, TableSection
from app.production.infrastructure.models import (ProductionOrder, ProductionAllocation, ProductionDemand,
    ProductionOrderStatusHistory, ProductionResultEntry, WorkCenter, ShiftDefinition, WasteRecord, DowntimeEvent)
from app.production.infrastructure.execution_models import ProductionRun, ProductionRunMember, ShiftRoster, ShiftRosterMember
from app.production.application.result_service import OrderResultService
from app.production.domain import result_rules

LIMIT = 5000


def shared(name):
    """Another module's table, read through the shared metadata: production never imports its models."""
    return Base.metadata.tables[name].c

LABELS = {
    'order': ('الأمر', 'Order'), 'status': ('الحالة', 'Status'), 'product': ('المنتج', 'Product'), 'customer': ('العميل', 'Customer'),
    'unit': ('الوحدة', 'Unit'), 'planned_qty': ('المخطط', 'Planned'), 'customer_good': ('جيد للعملاء', 'Customer good'),
    'stock_good': ('جيد للمخزون', 'Stock good'), 'good_total': ('إجمالي الجيد', 'Good total'), 'samples_total': ('العينات', 'Samples'),
    'samples_loss': ('عينات محتسبة هالكًا', 'Samples counted as loss'), 'scrap_total': ('الهالك', 'Scrap'), 'rework_total': ('إعادة التشغيل', 'Rework'),
    'loss_total': ('إجمالي الهالك', 'Total loss'), 'total_output': ('إجمالي الناتج', 'Total output'),
    'fulfillment_pct': ('نسبة الإنجاز %', 'Fulfillment %'), 'yield_pct': ('نسبة الجيد %', 'Yield %'), 'loss_pct': ('نسبة الهالك %', 'Loss %'),
    'variance_qty': ('التباين', 'Variance'), 'allocated_qty': ('المخصص', 'Allocated'),
    'draft': ('مسودة', 'Draft'), 'released': ('معتمد', 'Released'), 'in_progress': ('قيد الإنتاج', 'In progress'),
    'completed': ('مكتمل', 'Completed'), 'closed': ('مغلق', 'Closed'), 'cancelled': ('ملغى', 'Cancelled'), 'on_hold': ('معلق', 'On hold'),
    'sample': ('عينات', 'Sample'), 'scrap': ('هالك', 'Scrap'), 'rework': ('إعادة تشغيل', 'Rework'),
    'original': ('أصلي', 'Original'), 'correction': ('تصحيح', 'Correction'),
    'low': ('منخفضة', 'Low'), 'normal': ('عادية', 'Normal'), 'high': ('عالية', 'High'), 'urgent': ('عاجلة', 'Urgent'),
    # Downtime causes and waste types, as named in the application.
    'planned_maintenance': ('صيانة مخططة', 'Planned maintenance'), 'break_meeting': ('استراحة أو اجتماع', 'Break or meeting'),
    'no_orders': ('لا يوجد عمل مجدول', 'No orders scheduled'), 'changeover_setup': ('تغيير المنتج والضبط', 'Changeover and setup'),
    'breakdown': ('عطل', 'Breakdown'), 'material_shortage': ('نقص المواد', 'Material shortage'), 'waiting_labor': ('انتظار المشغّل', 'Waiting for operator'),
    'quality_issue': ('مشكلة جودة', 'Quality issue'), 'utilities': ('المرافق', 'Utilities'), 'other': ('أخرى', 'Other'),
    'planned_stop': ('توقف مخطط', 'Planned stop'), 'availability_loss': ('فقد في التوافر', 'Availability loss'),
    'startup_setup': ('هالك بدء التشغيل والضبط', 'Start-up and setup waste'), 'changeover': ('هالك تغيير المنتج', 'Changeover waste'),
    'process': ('هالك العملية', 'Process waste'), 'material_defect': ('هالك عيب المادة الخام', 'Raw material defect'),
    'machine_fault': ('هالك عطل الماكينة', 'Machine fault waste'), 'handling_damage': ('هالك المناولة والكسر', 'Handling and breakage'),
    'contamination': ('هالك التلوث', 'Contamination'),
    # Quality inspections and rejections on the order (QUAL-REPORT-001), as named in the quality screens.
    'open': ('مفتوح', 'Open'), 'under_inspection': ('قيد الفحص', 'Under inspection'), 'accepted': ('مقبول', 'Accepted'),
    'rejected': ('مرفوض', 'Rejected'), 'conditional_accept': ('قبول مشروط', 'Conditional accept'), 'needs_reinspection': ('يحتاج إعادة فحص', 'Needs reinspection'),
    'in_process_inspection': ('فحص أثناء الإنتاج', 'In-process inspection'), 'finished_product_inspection': ('فحص المنتج النهائي', 'Finished product inspection'),
    'reinspection': ('إعادة فحص', 'Reinspection'), 'issue_triggered': ('بسبب مشكلة', 'Issue triggered'), 'general': ('عام', 'General'),
    'failed_quality_check': ('فشل فحص الجودة', 'Failed quality check'), 'critical_defect': ('عيب حرج', 'Critical defect'),
    'out_of_spec': ('خارج المواصفات', 'Out of specification'), 'dimension_failure': ('فشل الأبعاد', 'Dimension failure'),
    'surface_failure': ('فشل السطح', 'Surface failure'), 'packaging_failure': ('فشل التعبئة', 'Packaging failure'), 'labeling_issue': ('مشكلة في التسمية', 'Labeling issue'),
    'hold': ('حجز (عزل)', 'Hold (quarantine)'), 'return_to_process': ('إعادة إلى العملية', 'Return to process'),
    'use_as_is': ('استخدام كما هو بموافقة', 'Use as is (concession)'), 'pending': ('بانتظار القرار', 'Awaiting decision'),
    'decided': ('مقرَّر', 'Decided'), 'executed': ('منفَّذ', 'Executed'),
}


def bi(value, lang):
    """A bilingual literal 'عربي / English' in the report's language only."""
    if isinstance(value, str) and ' / ' in value:
        ar, en = value.split(' / ', 1)
        return en if lang == 'en' else ar
    return value


def label(key, lang):
    return LABELS.get(str(key), (str(key), str(key)))[lang == 'en']


def text(value, zone=None):
    if value is None:
        return '—'
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
        return value.astimezone(zone or timezone.utc).strftime('%Y-%m-%d %H:%M')
    if isinstance(value, Decimal):
        return format(value, 'f')
    return str(value)


def applied_filters(params):
    names={'date_from':('من','From'),'date_to':('إلى','To'),'date_basis':('أساس التاريخ','Date basis'),
           'status':('الحالة','Status'),'product':('المنتج','Product'),'priority':('الأولوية','Priority'),
           'grouping':('التجميع','Grouping'),'period':('الفترة','Period')}
    values={'planned_start':('البداية المخططة','Planned start'),'completion':('الإكمال','Completion'),
            'none':('دون تجميع','None'),'month':('شهر','Month'),'week':('أسبوع','Week'),'day':('يوم','Day'),
            'low':('منخفضة','Low'),'normal':('عادية','Normal'),'high':('عالية','High'),'urgent':('عاجلة','Urgent')}
    en=params.lang=='en'; parts=[]
    for key,value in params.model_dump(mode='json').items():
        if key not in names or value is None or value==[]: continue
        items=value if isinstance(value,list) else [value]
        shown=', '.join(values[v][en] if v in values else label(v,params.lang) for v in items)
        parts.append(names[key][en]+': '+shown)
    return ' · '.join(parts)


def table(key, ar, en, columns, rows, lang, note=None, layout='table'):
    columns=[c.split(' / ')[lang=='en'] if ' / ' in c else c for c in columns]
    return TableSection(key=key, title=ar if lang == 'ar' else en, columns=columns,
                        rows=[[text(v) for v in row] for row in rows], note=bi(note, lang), layout=layout)


def zone_for(db, tenant):
    orgs = shared('foundation_organizations')
    return ZoneInfo(db.scalar(select(orgs.timezone).where(orgs.id == tenant.organization_id)) or 'UTC')


def scoped(db, model, tenant, *where):
    return db.scalars(select(model).where(model.organization_id == tenant.organization_id, *where)).all()


def has_data(model, order_field=None):
    def check(db, tenant, params=None):
        query = select(model.id).where(model.organization_id == tenant.organization_id)
        order_id = getattr(params, 'order_id', None)
        if order_id and order_field:
            query = query.where(getattr(model, order_field) == order_id)
        if model is ProductionRunMember and order_id:
            query = query.join(ProductionRun, ProductionRun.id == ProductionRunMember.production_run_id).where(
                ProductionRun.organization_id == tenant.organization_id, ProductionRun.production_order_id == order_id)
        return db.scalar(query.limit(1)) is not None
    return check


def quality_rows(name):
    """Whether the order (or the organization) has quality records of this kind, read through the shared metadata."""
    def check(db, tenant, params=None):
        table_ = shared(name)
        query = select(table_.id).where(table_.organization_id == tenant.organization_id)
        if getattr(params, 'order_id', None):
            query = query.where(table_.production_order_id == params.order_id)
        return db.scalar(query.limit(1)) is not None
    return check


def result_available(db, tenant, params=None):
    order_id = getattr(params, 'order_id', None)
    if not order_id:
        return True
    return db.scalar(select(ProductionOrder.id).where(ProductionOrder.organization_id == tenant.organization_id,
                     ProductionOrder.id == order_id, ProductionOrder.status.in_(['completed', 'closed']))) is not None


def allocation_rows(db, tenant, order_ids):
    """(allocation, demand, customer name) for the orders' active allocations."""
    customers = shared('commercial_customers')
    return db.execute(select(ProductionAllocation, ProductionDemand, customers.name).join(ProductionDemand, ProductionDemand.id == ProductionAllocation.production_demand_id)
        .join(customers.id.table, customers.id == ProductionDemand.customer_id).where(ProductionAllocation.organization_id == tenant.organization_id,
        ProductionDemand.organization_id == tenant.organization_id, customers.organization_id == tenant.organization_id,
        ProductionAllocation.production_order_id.in_(order_ids), ProductionAllocation.status == 'active')).all()


def order_full(db, tenant, params, selected):
    order = db.scalar(select(ProductionOrder).where(ProductionOrder.organization_id == tenant.organization_id, ProductionOrder.id == params.order_id))
    if order is None:
        raise HTTPException(404, 'PRODUCTION_ORDER_NOT_FOUND')
    lang, zone, sections = params.lang, zone_for(db, tenant), []
    if 'information' in selected:
        users = shared('foundation_users')
        creator = db.scalar(select(users.full_name).where(users.id == order.created_by_user_id, users.organization_id == tenant.organization_id))
        rows = [('رقم الأمر / Order', order.production_order_number), ('الحالة / Status', label(text(order.status), lang)),
                ('الأولوية / Priority', label(text(order.priority), lang)), ('المنتج / Product', order.product_type),
                ('البداية المخططة / Planned start', order.planned_start_date), ('النهاية المخططة / Planned end', order.planned_end_date),
                ('البداية الفعلية / Actual start', text(order.actual_start_at, zone)), ('الإكمال / Completion', text(order.actual_end_at, zone)),
                ('المنشئ / Created by', creator)]
        rows = [(bi(field, lang), value) for field, value in rows]
        sections.append(table('information', 'معلومات الأمر', 'Order information', ['الحقل / Field', 'القيمة / Value'], rows, lang, layout='fields'))
    if 'items' in selected:
        sections.append(table('items', 'البنود والمواصفات', 'Items and specifications', ['#', label('product', lang), 'المواصفات / Specifications', label('planned_qty', lang), label('unit', lang)],
            [(i.line_no, order.product_type, ' · '.join(f'{k}: {v}' for k,v in (i.target_spec_json or {}).items()), i.planned_quantity, i.unit) for i in order.items], lang))
    if 'allocations' in selected:
        # The order's status when each quantity was allocated: "in progress" / "on hold" marks what was added after start.
        sections.append(table('allocations', 'طلبات العملاء والتخصيصات', 'Customer demand and allocations', [label('customer',lang),'الطلب / Demand',label('allocated_qty',lang),label('unit',lang),
            'حالة الأمر عند التخصيص / Order status when allocated'],
            [(customer, d.demand_number, a.allocated_quantity, a.unit, label(a.order_status_at_allocation, lang)) for a,d,customer in allocation_rows(db, tenant, [order.id])], lang))
    if 'history' in selected:
        users = shared('foundation_users')
        rows = db.execute(select(ProductionOrderStatusHistory, users.full_name).outerjoin(users.id.table, (users.id == ProductionOrderStatusHistory.actor_user_id) & (users.organization_id == tenant.organization_id))
            .where(ProductionOrderStatusHistory.organization_id == tenant.organization_id, ProductionOrderStatusHistory.production_order_id == order.id).order_by(ProductionOrderStatusHistory.created_at)).all()
        sections.append(table('history', 'تاريخ الحالة', 'Status timeline', ['التاريخ / Date','من / From','إلى / To','بواسطة / By','السبب / Reason'],
            [(text(h.created_at, zone), label(h.from_status,lang), label(h.to_status,lang), actor, h.reason) for h,actor in rows], lang))
    runs = scoped(db, ProductionRun, tenant, ProductionRun.production_order_id == order.id) if {'execution','workforce'} & selected else []
    centers = {r.id:r.name for r in scoped(db, WorkCenter, tenant)} if runs else {}
    shifts = {r.id:r.name for r in scoped(db, ShiftDefinition, tenant)} if runs else {}
    if 'execution' in selected and runs:
        sections.append(table('execution','التشغيل','Execution',['المركز / Center','الوردية / Shift','البداية / Start','النهاية / End','المدة بالساعات / Elapsed hours'],
            [(centers.get(r.work_center_id),shifts.get(r.shift_definition_id),text(r.started_at,zone),text(r.ended_at,zone),
              round((r.ended_at-r.started_at).total_seconds()/3600,2) if r.started_at and r.ended_at else None) for r in runs],lang))
    if 'workforce' in selected and runs:
        people = shared('workforce_members')
        members = db.execute(select(ProductionRunMember, people.full_name).join(people.id.table, people.id == ProductionRunMember.workforce_member_id)
            .where(ProductionRunMember.organization_id == tenant.organization_id, people.organization_id == tenant.organization_id,
                   ProductionRunMember.production_run_id.in_([r.id for r in runs]))).all()
        sections.append(table('workforce','فريق التشغيل','Execution team',['الاسم / Name','الدور / Role','البداية / Start','النهاية / End','الساعات المسجلة / Recorded hours'],
            [(name,m.role_code,text(m.started_at,zone),text(m.ended_at,zone),round((m.ended_at-m.started_at).total_seconds()/3600,2) if m.started_at and m.ended_at else None) for m,name in members],lang))
    if 'downtime' in selected:
        rows=scoped(db,DowntimeEvent,tenant,DowntimeEvent.production_order_id==order.id)
        if rows: sections.append(table('downtime','التوقفات','Downtime',['البداية / Start','النهاية / End','دقائق / Minutes','السبب / Cause','النوع / Type','رمز السبب / Reason code'],
            [(text(r.start_time,zone),text(r.end_time,zone),r.duration_minutes,label(r.category,lang),label('planned_stop' if r.planned else 'availability_loss',lang),r.reason_code)
             for r in sorted(rows,key=lambda r:r.start_time)],lang))
    if 'waste' in selected:
        rows=scoped(db,WasteRecord,tenant,WasteRecord.production_order_id==order.id)
        if rows: sections.append(table('waste','الهدر التشغيلي','Operational waste',['التاريخ / Date','النوع / Type','الكمية / Quantity',label('unit',lang),'رمز السبب / Reason code'],
            [(r.waste_date,label(r.waste_category,lang),r.quantity_wasted,r.unit,r.reason_code) for r in sorted(rows,key=lambda r:r.waste_date)],lang,
            'لا يُضاف إلى هالك النتيجة النهائية / Not added to the final result\'s scrap'))
    if 'result' in selected and text(order.status) in ('completed','closed'):
        result=OrderResultService(db,tenant).result(order.id,lambda _:False)
        if not result['entries']:
            sections.append(table('result','النتيجة النهائية','Final result',[],[],lang, 'لم تسجل نتيجة / No result recorded'))
        else:
            metrics=['planned_qty','customer_good','stock_good','samples_total','samples_loss','scrap_total','rework_total','good_total','loss_total','total_output','fulfillment_pct','yield_pct','loss_pct','variance_qty']
            sections.append(table('result','ملخص النتيجة','Result summary',['المؤشر / Metric',* [t['unit'] for t in result['totals']]],[[label(k,lang),*[t[k] for t in result['totals']]] for k in metrics],lang))
            sections[-1].cards=[(label(k,lang)+' · '+total['unit'],text(total[k])) for total in result['totals'] for k in ('planned_qty','good_total','loss_total','yield_pct')]
            rows=[]
            for original in result['entries']:
                for e in [original,*original['corrections']]:
                    rows.append([e['line_no'],label(e['disposition'],lang),e['quantity'],e['unit'],label(e['entry_type'],lang),e['secondary_quantity'],e['secondary_unit'],e['reason_code'] or e['correction_reason'],e['created_by_name'],text(e['created_at'],zone)])
            sections.append(table('result_entries','تفاصيل النتيجة والتصحيحات','Entries and corrections',['#','التصنيف / Disposition','الكمية / Quantity',label('unit',lang),'النوع / Type','ثانوي / Secondary','الوحدة / Unit','السبب / Reason','بواسطة / By','التاريخ / Date'],rows,lang))
    if {'quality_checks','quality_rejections'} & selected:
        lines={i.id:i.line_no for i in order.items}
    if 'quality_checks' in selected:
        # Quality's tables through the shared metadata: production never imports quality.
        checks=shared('quality_checks')
        rows=db.execute(select(checks.inspection_code,checks.check_type,checks.production_order_item_id,checks.qty_inspected,checks.qty_accepted,checks.qty_rejected,
            checks.unit,checks.status,checks.result,checks.check_datetime).where(checks.organization_id==tenant.organization_id,checks.production_order_id==order.id)
            .order_by(checks.check_datetime)).all()
        closed=lambda r: text(r.status)=='closed'  # noqa: E731
        sections.append(table('quality_checks','فحوصات الجودة','Quality checks',['الرمز / Code','الوقت / Time','النوع / Type','البند / Line','المفحوص / Inspected',
            'المقبول / Accepted','المرفوض / Rejected',label('unit',lang),'الحالة / Status','النتيجة / Result'],
            [(r.inspection_code,text(r.check_datetime,zone),label(text(r.check_type),lang),lines.get(r.production_order_item_id),r.qty_inspected,
              r.qty_accepted if closed(r) else None,r.qty_rejected if closed(r) else None,r.unit,label(text(r.status),lang),label(text(r.result),lang) if r.result else None) for r in rows],lang,
            'الكميات المقبولة والمرفوضة تُسجَّل عند إغلاق الفحص / Accepted and rejected quantities are recorded when a check closes'))
    if 'quality_rejections' in selected:
        rejections=shared('quality_rejections')
        rows=db.execute(select(rejections.rejection_code,rejections.rejection_date,rejections.production_order_item_id,rejections.quantity_rejected,rejections.unit,
            rejections.rejection_reason,rejections.disposition,rejections.disposition_status).where(rejections.organization_id==tenant.organization_id,
            rejections.production_order_id==order.id).order_by(rejections.rejection_date,rejections.rejection_code)).all()
        sections.append(table('quality_rejections','حالات رفض الجودة','Quality rejections',['الرمز / Code','التاريخ / Date','البند / Line','الكمية / Quantity',label('unit',lang),
            'السبب / Reason','القرار / Disposition','الحالة / Status'],
            [(r.rejection_code,r.rejection_date,lines.get(r.production_order_item_id),r.quantity_rejected,r.unit,label(text(r.rejection_reason),lang),
              label(text(r.disposition),lang) if r.disposition else None,label(text(r.disposition_status),lang)) for r in rows],lang))
    if 'notes' in selected:
        sections.append(table('notes','الملاحظات','Notes',['الملاحظات / Notes'],[[order.notes]] if order.notes else [],lang))
    if 'signatures' in selected:
        sections.append(table('signatures','التوقيعات','Signatures',['إعداد / Prepared','مدير الإنتاج / Production manager','الجودة / Quality'],[['________________','________________','________________']],lang))
    return ReportData(sections=sections,provisional=text(order.status)!='closed',subject=order.production_order_number,applied_filters=applied_filters(params))


def filtered_orders(db,tenant,params):
    query=select(ProductionOrder).where(ProductionOrder.organization_id==tenant.organization_id)
    if params.status: query=query.where(ProductionOrder.status.in_(params.status))
    if params.product: query=query.where(ProductionOrder.product_type==params.product)
    if params.priority: query=query.where(ProductionOrder.priority==params.priority)
    if params.customer_id:
        query=query.where(ProductionOrder.id.in_(select(ProductionAllocation.production_order_id).join(ProductionDemand,ProductionDemand.id==ProductionAllocation.production_demand_id).where(
            ProductionAllocation.organization_id==tenant.organization_id,ProductionDemand.organization_id==tenant.organization_id,ProductionDemand.customer_id==params.customer_id,ProductionAllocation.status=='active')))
    if params.work_center_id:
        query=query.where(ProductionOrder.id.in_(select(ProductionRun.production_order_id).where(ProductionRun.organization_id==tenant.organization_id,ProductionRun.work_center_id==params.work_center_id)))
    zone=zone_for(db,tenant)
    date_col=ProductionOrder.planned_start_date if params.date_basis=='planned_start' else ProductionOrder.actual_end_at
    if params.date_from:
        start=params.date_from if params.date_basis=='planned_start' else datetime.combine(params.date_from,time.min,zone).astimezone(timezone.utc)
        query=query.where(date_col>=start)
    if params.date_to:
        end=params.date_to+timedelta(days=1)
        end=end if params.date_basis=='planned_start' else datetime.combine(end,time.min,zone).astimezone(timezone.utc)
        query=query.where(date_col<end)
    order_by=ProductionOrder.production_order_number if params.sort=='number' else date_col.asc() if params.sort=='date_asc' else date_col.desc()
    orders=db.scalars(query.options(selectinload(ProductionOrder.items)).order_by(order_by,ProductionOrder.id).limit(LIMIT+1)).all()
    if len(orders)>LIMIT: raise HTTPException(422,'REPORT_ROW_LIMIT_NARROW_FILTERS')
    return orders


def load_facts(db,tenant,orders):
    entries=defaultdict(list); allocations=defaultdict(lambda:defaultdict(lambda:Decimal(0))); customers=defaultdict(set)
    ids=[o.id for o in orders]
    if not ids: return entries,allocations,customers
    for e in scoped(db,ProductionResultEntry,tenant,ProductionResultEntry.production_order_id.in_(ids)):
        entries[e.production_order_id].append(e)
    for a,d,customer in allocation_rows(db,tenant,ids):
        allocations[a.production_order_id][a.unit]+=a.allocated_quantity
        customers[a.production_order_id].add(customer)
    return entries,allocations,customers


def summary_for(entries,planned,allocated):
    return result_rules.summarize([result_rules.Entry(e.production_order_item_id,e.disposition,e.quantity,e.unit,e.counts_as_loss,e.secondary_quantity,e.secondary_unit) for e in entries],planned,allocated)


def orders_summary(db,tenant,params,selected):
    orders=filtered_orders(db,tenant,params); entries,allocations,customers=load_facts(db,tenant,orders)
    groups=defaultdict(list); totals=defaultdict(lambda:dict(entries=[],planned=Decimal(0),allocated=Decimal(0)))
    zone=zone_for(db,tenant)
    for o in orders:
        planned=defaultdict(lambda:Decimal(0))
        for i in o.items: planned[i.unit]+=i.planned_quantity
        if not o.items: planned[o.unit]+=o.planned_quantity
        # A shared order appears once in a customer-set group: never duplicate its actual production per customer.
        customer=' / '.join(sorted(customers[o.id])) or '—'
        month=text(o.actual_end_at,zone)[:7] if params.date_basis=='completion' else str(o.planned_start_date)[:7]
        group={'none':'', 'status':label(text(o.status),params.lang),'product':o.product_type,'customer':customer,'month':month}[params.grouping]
        for unit,p in planned.items():
            own=[e for e in entries[o.id] if e.unit==unit]; s=summary_for(own,p,allocations[o.id].get(unit))
            present=bool(entries[o.id])
            groups[group].append([o.production_order_number,o.product_type,customer,label(text(o.status),params.lang),unit,p,
                s['good_total'] if present else None,s['scrap_total'] if present else None,s['loss_pct'] if present else None,s['yield_pct'] if present else None,
                o.planned_start_date,o.planned_end_date,text(o.actual_start_at,zone),text(o.actual_end_at,zone)])
            totals[unit]['entries'].extend(own); totals[unit]['planned']+=p; totals[unit]['allocated']+=allocations[o.id].get(unit,Decimal(0))
    sections=[]
    columns=[label(k,params.lang) for k in ['order','product','customer','status','unit','planned_qty','good_total','scrap_total','loss_pct','yield_pct']]+['البداية المخططة / Planned start','النهاية المخططة / Planned end','البداية / Start','الإكمال / Completion']
    if 'orders' in selected:
        for group,rows in groups.items(): sections.append(table('orders','الأوامر '+group,'Orders '+group,columns,rows,params.lang))
        if not groups: sections.append(table('orders','الأوامر','Orders',columns,[],params.lang))
    if 'totals' in selected:
        rows=[]
        for unit,f in totals.items():
            s=summary_for(f['entries'],f['planned'],f['allocated'] or None)
            rows.append([unit,s['planned_qty'],s['good_total'] if f['entries'] else None,s['scrap_total'] if f['entries'] else None,s['loss_pct'],s['yield_pct']])
        sections.append(table('totals','الإجماليات حسب الوحدة','Totals by unit',[label(k,params.lang) for k in ['unit','planned_qty','good_total','scrap_total','loss_pct','yield_pct']],rows,params.lang,
            '— تعني أن النتيجة لم تسجل. الأوامر المشتركة تعرض مرة واحدة. / — means no recorded result. Shared orders appear once.'))
    return ReportData(sections=sections,applied_filters=applied_filters(params))


def results_analysis(db,tenant,params,selected):
    orders=filtered_orders(db,tenant,params); entries,allocations,_=load_facts(db,tenant,orders)
    groups=defaultdict(lambda:dict(entries=[],planned=Decimal(0),allocated=Decimal(0))); reasons=defaultdict(lambda:Decimal(0)); zone=zone_for(db,tenant)
    for o in orders:
        if text(o.status) not in ('completed','closed') or not o.actual_end_at or not entries[o.id]: continue
        day=o.actual_end_at.replace(tzinfo=timezone.utc).astimezone(zone).date() if o.actual_end_at.tzinfo is None else o.actual_end_at.astimezone(zone).date()
        period=str(day) if params.period=='day' else str(day-timedelta(days=day.weekday())) if params.period=='week' else day.strftime('%Y-%m')
        planned=defaultdict(lambda:Decimal(0))
        for i in o.items: planned[i.unit]+=i.planned_quantity
        if not o.items: planned[o.unit]+=o.planned_quantity
        for unit,p in planned.items():
            f=groups[(o.product_type,period,unit)]; f['planned']+=p; f['allocated']+=allocations[o.id].get(unit,Decimal(0)); f['entries'].extend(e for e in entries[o.id] if e.unit==unit)
        for e in entries[o.id]:
            if e.disposition in ('scrap','sample'): reasons[(e.unit,e.disposition,e.reason_code or '—')]+=e.quantity
    metrics=['customer_good','stock_good','samples_total','samples_loss','scrap_total','rework_total','yield_pct','loss_pct']
    rows=[]; charts=defaultdict(list)
    for (product,period,unit),f in sorted(groups.items()):
        s=summary_for(f['entries'],f['planned'],f['allocated'] or None)
        rows.append([product,period,unit,*[s[k] for k in metrics],s['samples_total']-s['samples_loss']])
        charts[unit].append((product+' '+period,float(s['loss_total'])))
    sections=[]
    if 'analysis' in selected: sections.append(table('analysis','تحليل النتائج','Results analysis',[label('product',params.lang),'الفترة / Period',label('unit',params.lang),*[label(k,params.lang) for k in metrics],'عينات لا تُحتسب هالكًا / Samples not counted as loss'],rows,params.lang))
    if 'reasons' in selected: sections.append(table('reasons','أسباب الهالك والعينات','Scrap and sample reasons',['الوحدة / Unit','التصنيف / Disposition','السبب / Reason','الكمية / Quantity'],
        [[u,label(d,params.lang),r,q] for (u,d,r),q in sorted(reasons.items(),key=lambda item:(item[0][0],-item[1]))[:50]],params.lang))
    if 'trend' in selected:
        for unit,points in charts.items():
            maximum=max([v for _,v in points]+[1])
            section=table('trend','اتجاه الهالك '+unit,'Loss trend '+unit,['الفترة / Period','الكمية / Quantity'],points,params.lang)
            section.bars=[(k,max(0,v)/maximum*440) for k,v in points[:24]]; sections.append(section)
    return ReportData(sections=sections,applied_filters=applied_filters(params))


def shift_workforce(db,tenant,params,selected):
    query=select(ShiftRoster,ShiftDefinition.name).join(ShiftDefinition,ShiftDefinition.id==ShiftRoster.shift_definition_id).where(ShiftRoster.organization_id==tenant.organization_id,ShiftDefinition.organization_id==tenant.organization_id)
    if params.date_from: query=query.where((ShiftRoster.effective_to==None)|(ShiftRoster.effective_to>=params.date_from))
    if params.date_to: query=query.where(ShiftRoster.effective_from<=params.date_to)
    rosters=db.execute(query.order_by(ShiftRoster.effective_from.desc() if params.sort=='date_desc' else ShiftRoster.effective_from.asc()).limit(LIMIT+1)).all()
    if len(rosters)>LIMIT: raise HTTPException(422,'REPORT_ROW_LIMIT_NARROW_FILTERS')
    rows=[]
    ids=[r.id for r,_ in rosters]
    members=defaultdict(list)
    if ids:
        people=shared('workforce_members')
        for m,name in db.execute(select(ShiftRosterMember,people.full_name).join(people.id.table,people.id==ShiftRosterMember.workforce_member_id).where(
            ShiftRosterMember.organization_id==tenant.organization_id,people.organization_id==tenant.organization_id,ShiftRosterMember.shift_roster_id.in_(ids))): members[m.shift_roster_id].append((m,name))
    for r,shift in rosters:
        for m,name in members[r.id]: rows.append([shift,r.name,r.effective_from,r.effective_to,name,m.role_note,bi('قائد / Lead' if m.is_shift_lead else 'عضو / Member',params.lang)])
    if len(rows)>LIMIT: raise HTTPException(422,'REPORT_ROW_LIMIT_NARROW_FILTERS')
    sections=[table('rosters','تشكيلات الورديات','Shift rosters',['الوردية / Shift','الفريق / Team','من / From','إلى / To','الاسم / Name','الدور / Role','المسؤولية / Responsibility'],rows,params.lang,
        'تشكيل الفريق لا يثبت الحضور أو ساعات العمل / Roster membership does not establish attendance or worked hours')] if 'rosters' in selected else []
    if 'participation' in selected:
        people=shared('workforce_members')
        query=select(ProductionRunMember,people.full_name,ProductionRun.run_date).join(ProductionRun,ProductionRun.id==ProductionRunMember.production_run_id).join(people.id.table,people.id==ProductionRunMember.workforce_member_id).where(
            ProductionRunMember.organization_id==tenant.organization_id,ProductionRun.organization_id==tenant.organization_id,people.organization_id==tenant.organization_id)
        if params.date_from: query=query.where(ProductionRun.run_date>=params.date_from)
        if params.date_to: query=query.where(ProductionRun.run_date<=params.date_to)
        members=db.execute(query.order_by(ProductionRun.run_date).limit(LIMIT+1)).all()
        if len(members)>LIMIT: raise HTTPException(422,'REPORT_ROW_LIMIT_NARROW_FILTERS')
        zone=zone_for(db,tenant)
        sections.append(table('participation','المشاركة الفعلية','Recorded participation',['التاريخ / Date','الاسم / Name','الدور / Role','البداية / Start','النهاية / End','الساعات / Hours'],
            [(day,name,m.role_code,text(m.started_at,zone),text(m.ended_at,zone),round((m.ended_at-m.started_at).total_seconds()/3600,2) if m.started_at and m.ended_at else None) for m,name,day in members],params.lang))
    return ReportData(sections=sections,applied_filters=applied_filters(params))
