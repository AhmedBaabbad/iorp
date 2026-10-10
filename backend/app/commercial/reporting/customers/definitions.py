from pathlib import Path
from app.core.reporting.contracts import ReportDefinition, SectionDefinition as Section
from app.core.reporting.registry import registry
from app.core.reporting.service import template_roots
from . import providers, schemas as s
from .builders import build
from .queries import customers
from app.production.domain import permissions as production_permissions

READ='commercial:customers:read'
DEMAND=production_permissions.DEMANDS_READ
ORDER=production_permissions.ORDERS_READ
RESULT=production_permissions.RESULTS_READ
QUOTE='commercial:quotes:read'
INTERNAL='reports:customers:internal_audience'
SAMPLE='commercial:samples:read'
LABELS={
    'customer_profile':('ملف العميل','Customer profile'), 'directory':('دليل العملاء','Customers directory'),
    'activity_summary':('نشاط العملاء وترتيبهم','Customer activity and ranking'),
    'quotations_report':('تقرير عروض الأسعار','Quotations report'),
    'demand_fulfillment':('حالة الطلب والتخصيص','Demand and fulfillment status'),
    'growth_retention':('نمو العملاء والخمول','Customer growth and inactivity'),
    'customer_statement':('كشف حالة طلبات العميل','Customer order status statement'),
    'internal_audience':('الجمهور الداخلي لتقارير العملاء','Internal customer reports audience'),
}
PERMISSIONS=tuple('reports:customers:'+key for key in LABELS)


def available(module, method):
    def check(db, tenant, params):
        if not providers.module_enabled(db,tenant,module):return False
        factory=providers.production_factory if module=='production' else providers.commercial_factory
        if factory is None:return False
        # Without a chosen customer (report center, directory reports) the section is offered: reading every
        # customer's data just to list reports would be slow and could hit the row limit. The report itself
        # shows "no data" for an empty scope. With a customer, only that customer's rows are inspected.
        if not getattr(params,'customer_id',None):return True
        ids=[c.id for c in customers(db,tenant,params)]
        reader=factory(db,tenant)
        if method=='results':
            orders=reader.orders(ids)
            return any(o.status in {'completed','closed'} for o in orders) and bool(reader.results([o.order_id for o in orders if o.status in {'completed','closed'}]))
        return bool(getattr(reader,method)(ids))
    return check


def register_reports():
    if registry.get('customers.customer_profile'):return
    template_roots.append(Path(__file__).parent/'templates')
    info=Section('information','بيانات العميل','Customer information')
    contact=Section('contacts','الاتصال','Contact information')
    sample_sections = (
        Section('samples', 'عينات العملاء', 'Customer samples', requires_permission=SAMPLE),
        Section('sample_properties', 'مواصفات العينات', 'Sample properties', requires_permission=SAMPLE),
        Section('sample_evaluations', 'تقييمات العينات', 'Sample evaluations', internal_only=True,
                permissions=(SAMPLE, 'commercial:evaluations:read')),
    )
    quotes=Section('quotations','عروض الأسعار','Quotations',requires_permission=QUOTE,available=available('commercial','quotations'))
    demands=Section('demands','الطلبات والتخصيص','Demand and allocation',requires_permission=DEMAND,available=available('production','demands'))
    orders=Section('orders','أوامر الإنتاج','Production orders',permissions=(DEMAND,ORDER),available=available('production','orders'))
    results=Section('results','نتائج الأوامر','Order results',permissions=(DEMAND,ORDER,RESULT),available=available('production','results'))
    losses=Section('losses','تفاصيل الفاقد','Loss details',internal_only=True,permissions=(DEMAND,ORDER,RESULT),available=available('production','results'))
    notes=Section('notes','ملاحظات داخلية','Internal notes',internal_only=True)
    activity=Section('activity','سجل التفاعلات','Interaction timeline',internal_only=True,requires_permission='commercial:interactions:read')
    followups=Section('followups','المتابعات الداخلية','Internal follow-ups',internal_only=True,requires_permission='commercial:follow_ups:read')
    last=Section('last_activity','آخر نشاط','Last activity',permissions=(QUOTE,DEMAND,ORDER),
        available=lambda db,t,p:providers.module_enabled(db,t,'production') and providers.module_enabled(db,t,'commercial'))
    for key,schema,sections,audiences in [
        ('customer_profile',s.ProfileParams,(info,contact,*sample_sections,quotes,demands,orders,results,losses,notes,activity,followups,last),('internal','customer')),
        ('directory',s.DirectoryParams,(Section('directory','دليل العملاء','Customers directory'),orders,last),('internal',)),
        ('activity_summary',s.ActivityParams,(quotes,demands,orders,last),('internal',)),
        ('quotations_report',s.QuotesParams,(quotes,),('internal',)),
        ('demand_fulfillment',s.FulfillmentParams,(demands,orders,results,losses),('internal','customer')),
        ('growth_retention',s.GrowthParams,(Section('growth','العملاء الجدد','New customers'),quotes,
            Section('inactivity','الخمول','Inactivity',permissions=(QUOTE,DEMAND,ORDER),available=lambda db,t,p:providers.module_enabled(db,t,'production') and providers.module_enabled(db,t,'commercial'))),('internal',)),
        ('customer_statement',s.StatementParams,(info,demands,orders,results),('internal','customer')),
    ]:
        ar,en=LABELS[key]
        required=(READ,QUOTE) if key=='quotations_report' else (READ,)
        registry.register(ReportDefinition('customers.'+key,'customers',ar,en,schema,sections,
            'reports:customers:'+key,lambda db,t,p,selected,k=key:build(k,db,t,p,selected),'customers_body.html',
            default_orientation='portrait' if key in {'customer_profile','customer_statement'} else 'landscape',
            audiences=audiences,internal_permission=INTERNAL,required_permissions=required,
            department=('العملاء','Customers'),context_fields=('customer_id',),filename_prefix='customers.'+key,
            parameter_permissions=lambda params:(DEMAND,ORDER) if getattr(params,'has_active_orders',False) else ()))
    # Same customer dossier access, with mandatory sample-read and internal-audience permissions.
    registry.register(ReportDefinition('customers.samples_report', 'customers', 'تقرير عينات العملاء', 'Customer samples report',
        s.SamplesParams, sample_sections, 'reports:customers:customer_profile',
        lambda db,t,p,selected: build('samples_report',db,t,p,selected), 'customers_body.html',
        default_orientation='landscape', audiences=('internal',), internal_permission=INTERNAL,
        required_permissions=(READ,SAMPLE), context_fields=('customer_id',),
        department=('العملاء','Customers'), filename_prefix='customers.samples_report'))
