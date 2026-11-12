"""Customer reports: typed table DTOs, no ORM imports from another module.

Conversion = accepted / (accepted + rejected + expired) * 100, using current statuses
of quotations issued in the chosen period. Production quantities come from the owning
module, which excludes released allocations and reuses the signed result summary.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from app.core.interfaces.reference_lists import names as list_names
from app.core.reporting.contracts import ReportData, TableSection
from . import providers
from .queries import customers, activities, followups, bounded
from app.core.location_fields import city_text


def value(v):
    return str(getattr(v, 'value', v)) if v is not None else '—'


AR_STATUSES = {'active':'نشط','inactive':'غير نشط','on_hold':'معلق','archived':'مؤرشف','blacklisted':'محظور',
    'draft':'مسودة','issued':'صادر','accepted':'مقبول','rejected':'مرفوض','expired':'منتهي',
    'ready_for_planning':'جاهز للتخطيط','partially_planned':'مخطط جزئيًا','planned':'مخطط','cancelled':'ملغى',
    'released':'معتمد','in_progress':'قيد التنفيذ','completed':'مكتمل','closed':'مغلق','pending':'قيد الانتظار'}


def status_label(code, ar):
    return AR_STATUSES.get(code, code) if ar else code.replace('_', ' ').capitalize()


def conversion(quotes):
    decided = sum(q.status in {'accepted', 'rejected', 'expired'} for q in quotes)
    return (Decimal(sum(q.status == 'accepted' for q in quotes)) * 100 / decided).quantize(Decimal('.01')) if decided else Decimal(0)


def zone(db, tenant):
    return ZoneInfo(providers.identity_factory(db, tenant).timezone())


def build(key, db, tenant, p, selected):
    ar = p.lang == 'ar'
    tr = lambda a, e: a if ar else e
    tz = zone(db, tenant)
    today = datetime.now(tz).date()
    def day(v):
        if isinstance(v, datetime):
            return (v if v.tzinfo else v.replace(tzinfo=timezone.utc)).astimezone(tz).date()
        return v
    def within(v):
        return v is not None and (not p.date_from or day(v) >= p.date_from) and (not p.date_to or day(v) <= p.date_to)
    cs = customers(db, tenant, p)
    if p.audience == 'customer' and not p.customer_id:
        raise HTTPException(422, 'CUSTOMER_REQUIRED')
    if key == 'directory':
        cs = [c for c in cs if within(c.created_at)]
    ids = [c.id for c in cs]
    names = {c.id: c.name for c in cs}
    quotes = providers.commercial_factory(db, tenant).quotations(ids) if {'quotations','inactivity','last_activity'} & selected else []
    active_filter=getattr(p,'has_active_orders',False)
    if active_filter and not providers.module_enabled(db,tenant,'production'):
        raise HTTPException(403,'SECTION_PERMISSION_DENIED')
    prod = providers.production_factory(db, tenant) if active_filter or {'demands', 'orders', 'results', 'losses', 'inactivity','last_activity'} & selected else None
    demands = prod.demands(ids) if prod and ({'demands', 'inactivity','last_activity'} & selected or key=='demand_fulfillment') else []
    orders = prod.orders(ids) if prod and (active_filter or {'orders', 'results', 'losses', 'inactivity','last_activity'} & selected) else []
    if getattr(p, 'has_active_orders', False):
        active_ids = {o.customer_id for o in orders if o.status not in {'completed', 'closed', 'cancelled'}}
        cs = [c for c in cs if c.id in active_ids]
        ids = [c.id for c in cs]
        names = {c.id: c.name for c in cs}
        quotes = [q for q in quotes if q.customer_id in ids]
        demands = [d for d in demands if d.customer_id in ids]
        orders = [o for o in orders if o.customer_id in ids]
    sections = []
    shared_label = lambda o: tr('أمر مشترك','Shared order') if o.shared else tr('عميل واحد','Single customer')  # noqa: E731
    def table(k, a, e, columns, rows, note=None, bars=None):
        if k in selected:
            cells=[[status_label(value(x),ar) if columns[index][1]=='Status' else value(x)
                    for index,x in enumerate(r)] for r in bounded(rows)]
            titles=[tr(*c) for c in columns]
            if p.customer_id and k in {'information','contacts'} and len(cells)==1:
                # One customer's details read as a labelled panel, not a one-row table.
                pairs=[list(pair) for pair in zip(titles, cells[0]) if not (k=='contacts' and pair[0]==tr(*customer_col))]
                sections.append(TableSection(key=k, title=tr(a, e), columns=titles, rows=pairs, note=note, layout='fields'))
                return
            sections.append(TableSection(key=k, title=tr(a, e), columns=titles, rows=cells, note=note, bars=bars or []))
    customer_col = ('العميل', 'Customer')
    # A customer-audience report is sent outside the company: no internal classification, sales KPI,
    # draft quotation, stock decision or other customers' quantities (shared orders) appear in it.
    external = p.audience == 'customer'
    if {'samples', 'sample_properties', 'sample_evaluations'} & selected:
        from .sample_sections import build_sample_sections
        sections.extend(build_sample_sections(db, tenant, p, selected, cs, tz))
    # MD-002: a sector or city is printed by its name in the report's language (a text written before the lists, as written).
    printed = {f: list_names(db, tenant.organization_id, f, [getattr(c, f) for c in cs], p.lang) for f in ('sector', 'city')}
    listed = lambda c, f: (city_text(c.city, c.city_other) if f == 'city' and c.city and c.city.endswith('_other') and c.city_other
                          else printed[f].get(getattr(c, f), getattr(c, f)))  # noqa: E731
    if 'information' in selected:
        if external:
            table('information', 'بيانات العميل', 'Customer information', [('الرمز','Code'),customer_col,('القطاع','Sector'),('المدينة','City')],
                [(c.customer_code,c.name,listed(c,'sector'),listed(c,'city')) for c in cs])
        else:
            table('information', 'بيانات العميل', 'Customer information', [('الرمز','Code'),customer_col,('الحالة','Status'),('القطاع','Sector'),('المدينة','City'),('الإنشاء','Created')],
                [(c.customer_code,c.name,value(c.status),listed(c,'sector'),listed(c,'city'),day(c.created_at)) for c in cs])
    table('contacts','بيانات الاتصال','Contact information',[customer_col,('الهاتف','Phone'),('البريد','Email')],[(c.name,c.effective_phone,c.effective_email) for c in cs])
    if 'directory' in selected:
        owner_names = providers.identity_factory(db,tenant).user_names([c.sales_owner_user_id for c in cs if c.sales_owner_user_id])
        grouping = getattr(p, 'grouping', 'none')
        group = lambda c: value(owner_names.get(c.sales_owner_user_id)) if grouping == 'sales_owner' else value(listed(c, grouping) if grouping in ('sector', 'city') else getattr(c, grouping, ''))
        cs.sort(key=lambda c: (group(c), day(c.created_at).isoformat() if p.sort == 'created' else c.name, str(c.id)))
        table('directory','دليل العملاء','Customers directory',[('المجموعة','Group'),('الرمز','Code'),customer_col,('القطاع','Sector'),('المدينة','City'),('الهاتف','Phone'),('الحالة','Status'),('الإنشاء','Created')],
            [(group(c) if grouping!='none' else '—',c.customer_code,c.name,listed(c,'sector'),listed(c,'city'),c.effective_phone,value(c.status),day(c.created_at)) for c in cs])
    quote_period = [q for q in quotes if within(q.issued) and (not getattr(p,'quote_status',None) or q.status == p.quote_status)
                    and not (external and q.status == 'draft')]
    if 'quotations' in selected:
        note = tr('التحويل = المقبول ÷ (المقبول + المرفوض + المنتهي) × 100؛ حالات حالية حسب تاريخ إصدار العرض.',
                  'Conversion = accepted / (accepted + rejected + expired) × 100; current status, filtered by issue date.')
        if key == 'activity_summary':
            groups = defaultdict(list)
            for q in quote_period: groups[q.customer_id,q.currency].append(q)
            ranked = sorted(groups.items(),key=lambda pair:(pair[0][1],-sum(q.total for q in pair[1]),str(pair[0][0])))
            rows, bars, counts = [], [], defaultdict(int)
            for (cid,currency), qs in ranked:
                counts[currency] += 1
                if counts[currency] > p.top_n: continue
                total = sum((q.total for q in qs),Decimal(0))
                rows.append((names[cid],currency,len(qs),total,conversion(qs)))
                if p.rank_by == 'quotation_value':
                    maximum = max((sum(x.total for x in group) for (_,cur),group in groups.items() if cur==currency),default=Decimal(0))
                    bars.append((f'{names[cid]} ({currency})',float(total/maximum*400) if maximum else 0))
            table('quotations','نشاط عروض الأسعار','Quotation activity',[customer_col,('العملة','Currency'),('العدد','Count'),('القيمة','Value'),('التحويل %','Conversion %')],rows,note,bars)
        else:
            totals=defaultdict(Decimal)
            for q in quote_period: totals[q.currency,q.status]+=q.total
            rows=[(names[q.customer_id],q.number,day(q.issued),q.status,q.currency,q.total) for q in quote_period]
            rows += [(tr('الإجمالي','Total'),'—','—',status,cur,total) for (cur,status),total in sorted(totals.items())]
            table('quotations','عروض الأسعار','Quotations',[customer_col,('الرقم','Number'),('التاريخ','Date'),('الحالة','Status'),('العملة','Currency'),('القيمة','Value')],rows,
                  None if external else note + f' {conversion(quote_period)}%')
    filtered_demands = [d for d in demands if within(d.requested) and (not getattr(p,'product',None) or d.product==p.product)
        and (not getattr(p,'demand_status',None) or d.status==p.demand_status)]
    if key == 'customer_statement':
        filtered_demands=[d for d in filtered_demands if d.status!='cancelled']
        orders=[o for o in orders if o.status not in {'cancelled','completed','closed'} or
                (o.status in {'completed','closed'} and o.actual_end and day(o.actual_end)>=today-timedelta(days=p.recent_days))]
    if 'demands' in selected:
        if key == 'activity_summary':
            groups=defaultdict(lambda:[set(),Decimal(0),Decimal(0)])
            for d in filtered_demands:
                g=groups[d.customer_id,d.unit];g[0].add(d.demand_id);g[1]+=d.quantity;g[2]+=d.allocated
            ranked=sorted(groups.items(),key=lambda pair:(pair[0][1],-pair[1][1],str(pair[0][0])))
            counts=defaultdict(int);rows=[];bars=[]
            for (cid,unit),(dids,qty,alloc) in ranked:
                counts[unit]+=1
                if counts[unit]>p.top_n:continue
                rows.append((names[cid],unit,len(dids),qty,alloc))
                if p.rank_by=='demanded_quantity':
                    maximum=max(g[1] for (_,u),g in groups.items() if u==unit)
                    bars.append((f'{names[cid]} ({unit})',float(qty/maximum*400) if maximum else 0))
            table('demands','نشاط الطلبات','Demand activity',[customer_col,('الوحدة','Unit'),('عدد الطلبات','Demand count'),('المطلوب','Demanded'),('المخصص','Allocated')],rows,bars=bars)
        else:
            table('demands','الطلبات والتخصيص','Demand and allocation',[customer_col,('الطلب','Demand'),('المنتج','Product'),('الوحدة','Unit'),('المطلوب','Demanded'),('المخصص','Allocated'),('غير المخصص','Unallocated'),('الحالة','Status'),('التاريخ المطلوب','Requested delivery')],
                [(names[d.customer_id],d.number,d.product,d.unit,d.quantity,d.allocated,d.unallocated,d.status,d.expected) for d in filtered_demands])
    filtered_orders=[o for o in orders if within(o.created)]
    if key == 'demand_fulfillment':
        # Filters refer to demand request dates, not order creation dates.
        matching={d.demand_id for d in filtered_demands}
        filtered_orders=[o for o in orders if matching.intersection(o.demand_ids)]
    if 'orders' in selected and key=='activity_summary':
        grouped=defaultdict(list)
        for o in filtered_orders:grouped[o.customer_id].append(o)
        table('orders','نشاط أوامر الإنتاج','Production order activity',[customer_col,('عدد الأوامر','Orders'),('أوامر مكتملة','Completed orders'),('آخر أمر','Last order')],
            [(names[cid],len({o.order_id for o in os}),len({o.order_id for o in os if o.status in {'completed','closed'}}),max(day(o.created) for o in os)) for cid,os in grouped.items()])
    elif 'orders' in selected:
        if external:  # the order's total would reveal other customers' quantities
            columns=[('الأمر','Order'),('المنتج','Product'),('الحالة','Status'),('للعميل','Customer allocation'),('النوع','Type'),('النهاية المخططة / الفعلية','Planned / actual end')]
            rows=[(o.number,o.product,o.status,f'{o.allocated} {o.unit}',shared_label(o),f'{o.planned_end}\n{day(o.actual_end) or "—"}') for o in filtered_orders]
        else:
            columns=[('الأمر','Order'),('المنتج','Product'),('الحالة','Status'),('للعميل','Customer allocation'),('إجمالي التخصيص','Total allocated'),('النوع','Type'),('النهاية المخططة / الفعلية','Planned / actual end')]
            rows=[(o.number,o.product,o.status,f'{o.allocated} {o.unit}',f'{o.total_allocated} {o.unit}',
                shared_label(o),f'{o.planned_end}\n{day(o.actual_end) or "—"}') for o in filtered_orders]
        if not p.customer_id:
            columns=[customer_col,*columns]
            rows=[(names[o.customer_id],*r) for o,r in zip(filtered_orders,rows)]
        table('orders','أوامر الإنتاج','Production orders',columns,rows,
            tr('التخصيصات الفعالة فقط؛ نتائج الإنتاج ليست إثبات تسليم.','Active allocations only; production results are not evidence of delivery.'))
    if {'results','losses'} & selected:
        results=prod.results([o.order_id for o in filtered_orders],internal='losses' in selected and p.audience=='internal')
        linked={o.order_id:o for o in filtered_orders}
        if external:
            # Order-level output of a shared order includes other customers' goods; stock good is an internal decision.
            table('results','نتائج الأوامر','Order results',[('الأمر','Order'),('النوع','Type'),('الوحدة','Unit'),('جيد للعملاء','Customer good')],
                [(linked[r.order_id].number,shared_label(linked[r.order_id]),r.unit,
                  tr('غير معروضة لأمر مشترك','Not shown for a shared order') if linked[r.order_id].shared else r.customer_good)
                 for r in results if r.order_id in linked],
                tr('نتائج الإنتاج ليست إثبات تسليم. الأمر المشترك يخدم أكثر من عميل، فلا تُعرض نتيجته الإجمالية.',
                   'Production results are not evidence of delivery. A shared order serves several customers, so its total output is not shown.'))
        else:
            table('results','نتائج الأوامر','Order results',[('الأمر','Order'),('النوع','Type'),('الوحدة','Unit'),('جيد للعملاء','Customer good'),('جيد للمخزون','Stock good')],
                [(linked[r.order_id].number,shared_label(linked[r.order_id]),r.unit,r.customer_good,r.stock_good) for r in results if r.order_id in linked],
                tr('نتائج على مستوى الأمر، دون توزيع نسبي على العملاء أو إثبات تسليم.','Order-level results; no proportional customer attribution or delivery claim.'))
        if 'losses' in selected and p.audience=='internal':
            table('losses','الفاقد والعينات وإعادة التشغيل','Loss, samples and rework',[('الأمر','Order'),('الوحدة','Unit'),('العينات','Samples'),('الهالك','Scrap'),('إعادة التشغيل','Rework'),('الفاقد','Loss')],
                [(linked[r.order_id].number,r.unit,r.sample,r.scrap,r.rework,r.loss_total) for r in results if r.order_id in linked])
    if 'notes' in selected:
        table('notes','ملاحظات داخلية','Internal notes',[customer_col,('الملاحظات','Notes')],[(c.name,c.notes) for c in cs if c.notes])
    if 'activity' in selected:
        events=activities(db,tenant,ids)
        table('activity','سجل التفاعلات','Interaction timeline',[customer_col,('التاريخ','Date'),('الموضوع','Subject'),('الملخص','Summary')],
            [(names[a.customer_id],day(a.interaction_date),a.subject,a.summary) for a in events if within(a.interaction_date)])
    if 'followups' in selected:
        table('followups','المتابعات الداخلية','Internal follow-ups',[customer_col,('الموعد','Due date'),('الحالة','Status'),('السبب','Reason'),('ملاحظات','Notes')],
            [(names[f.customer_id],day(f.due_date),f.status,f.reason,f.notes) for f in followups(db,tenant,ids) if within(f.created_at)])
    if 'growth' in selected:
        counts=defaultdict(int)
        for c in cs:
            if within(c.created_at):
                d=day(c.created_at);period=f'{d.year}-Q{(d.month-1)//3+1}' if p.period=='quarter' else d.strftime('%Y-%m')
                counts[period]+=1
        table('growth','العملاء الجدد','New customers',[('الفترة','Period'),('العدد','Count')],sorted(counts.items()),
            tr('تغيرات الحالة وإعادة التنشيط غير متاحة لغياب سجل تاريخي.','Status changes and reactivation are unavailable: no historical lifecycle records.'))
    if key in {'customer_profile','activity_summary'}:
        for section in sections:
            if section.key=='quotations':
                section.cards=[(tr('عدد العروض','Quotation count'),str(len(quote_period)))]
                if not external:
                    section.cards.append((tr('التحويل %','Conversion %'),str(conversion(quote_period))))
            elif section.key=='demands':
                section.cards=[(tr('عدد الطلبات','Demand count'),str(len({d.demand_id for d in filtered_demands})))]
                totals=defaultdict(Decimal)
                for d in filtered_demands:totals[d.unit]+=d.quantity
                section.cards += [(tr('إجمالي المطلوب','Total demanded')+' ('+unit+')',str(qty)) for unit,qty in sorted(totals.items())]
            elif section.key=='orders':
                section.cards=[(tr('أوامر نشطة','Active orders'),str(len({o.order_id for o in filtered_orders if o.status not in {'completed','closed','cancelled'}}))),
                    (tr('أوامر مكتملة','Completed orders'),str(len({o.order_id for o in filtered_orders if o.status in {'completed','closed'}})))]
    if {'inactivity','last_activity'} & selected:
        last={c.id:None for c in cs}
        for cid,date in [(q.customer_id,day(q.issued)) for q in quotes]+[(d.customer_id,d.requested) for d in demands]+[(o.customer_id,day(o.created)) for o in orders]:
            if date<=today:last[cid]=max(last[cid] or date,date)
        table('last_activity','آخر نشاط','Last activity',[customer_col,('آخر عرض أو طلب أو أمر إنتاج','Last quotation, demand or production order')],[(c.name,last[c.id]) for c in cs])
        if 'inactivity' in selected:
            cutoff=today-timedelta(days=p.inactive_days)
            table('inactivity','العملاء غير النشطين','Inactive customers',[customer_col,('آخر نشاط تجاري أو إنتاجي','Last commercial or production activity'),('الإنشاء','Created')],
                [(c.name,last[c.id],day(c.created_at)) for c in cs if (last[c.id] is None or last[c.id]<cutoff) and day(c.created_at)<cutoff],
                tr(f'لا عرض أو طلب أو أمر خلال آخر {p.inactive_days} يومًا؛ العملاء الجدد مستبعدون.',f'No quotation, demand or order in the last {p.inactive_days} days; newer customers excluded.'))
    filters = [f'{p.date_from or "—"} → {p.date_to or "—"}'] if p.date_from or p.date_to else []
    if key == 'samples_report':
        from .sample_sections import LABELS as sample_labels
        for field, title in [('product',tr('المنتج','Product')),('sample_status',tr('حالة العينة','Sample status')),('sample_decision',tr('قرار العينة','Sample decision'))]:
            selected_value = getattr(p,field,None)
            if selected_value:
                printed_value = (sample_labels.get(selected_value,selected_value) if ar else selected_value.replace('_',' ').capitalize()) if field != 'product' else selected_value
                filters.append(f'{title}: {printed_value}')
        if p.customer_id and cs: filters.insert(0, tr('العميل','Customer')+': '+cs[0].name)
    return ReportData(sections=sections,subject=cs[0].customer_code if p.customer_id and cs else '',
        prepared_for=cs[0].name if external and cs else '',
        applied_filters=' | '.join(filters))
