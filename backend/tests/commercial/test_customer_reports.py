from dataclasses import replace
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4
from types import SimpleNamespace
import pytest
from sqlalchemy import select
from tests.production.test_production_reports import env as reports_env
from tests.production.test_order_results import env as result_env
from app.commercial.infrastructure.models import Customer, Quote, FollowUp
from app.commercial.reporting.customers.definitions import PERMISSIONS
from app.commercial.reporting.customers import providers, builders, queries
from app.core.interfaces.customer_reporting import ResultRead
from app.production.infrastructure.models import ProductionAllocation, ProductionDemand, ProductionDemandItem
from app.foundation.infrastructure.models import Organization, Permission, Role, RolePermission, UserRole


@pytest.fixture
def env(reports_env):
    e=reports_env
    e.ctx.auth_user.permissions.update(PERMISSIONS)
    e.ctx.auth_user.permissions.update({'commercial:customers:read','commercial:quotes:read','commercial:interactions:read',
        'production:demands:read','production:production_orders:read','production:results:read'})
    e.ctx.tenant=replace(e.ctx.tenant,is_organization_root=True)
    e.customer=e.db.scalars(select(Customer)).first()
    e.customer.notes='SECRET INTERNAL NOTE'
    e.customer.name='عميل <script>bad()</script>'
    e.customer.sales_owner_user_id=e.user.id
    e.db.commit()
    return e


def preview(e,key='customer_profile',**params):
    if key in {'customer_profile','customer_statement'}:params.setdefault('customer_id',str(e.customer.id))
    return e.client.post('/api/v1/reports/customers.'+key+'/preview',json=params)


def quote(e,status='accepted',currency='SAR',total='120',when=None):
    row=Quote(organization_id=e.org.id,customer_id=e.customer.id,quote_number='Q-'+uuid4().hex[:8],
        issue_date=when or datetime.now(timezone.utc),valid_until=datetime.now(timezone.utc)+timedelta(days=30),status=status,currency=currency,subtotal_amount=Decimal(total),
        discount_amount=0,tax_amount=0,total_amount=Decimal(total),created_by_user_id=e.user.id)
    e.db.add(row);e.db.commit();return row


def test_definitions_permissions_and_internal_audience(env):
    ds=env.client.get('/api/v1/reports/definitions?module=customers').json()
    assert len(ds)==7
    env.ctx.auth_user.permissions.remove('reports:customers:internal_audience')
    ds=env.client.get('/api/v1/reports/definitions?module=customers').json()
    assert {d['key'] for d in ds}=={'customers.customer_profile','customers.customer_statement','customers.demand_fulfillment'}
    assert all(d['audiences']==['customer'] for d in ds)
    assert all('notes' not in {s['key'] for s in d['sections']} for d in ds)
    assert preview(env).status_code==403
    assert preview(env,audience='customer').status_code==200


def test_customer_audience_strips_explicit_internal_sections_and_escapes(env):
    r=preview(env,audience='customer',sections=['information','notes','losses','activity'],lang='en')
    assert r.status_code==200,r.text
    assert 'SECRET INTERNAL NOTE' not in r.text and 'Loss details' not in r.text
    assert '<script>bad()' not in r.text and '&lt;script&gt;' in r.text
    assert env.user.full_name not in r.text
    assert '<th>Prepared for</th>' in r.text
    r=preview(env,sections=['notes']);assert r.status_code==200 and 'SECRET INTERNAL NOTE' in r.text


@pytest.mark.parametrize('key', ['customer_profile','directory','activity_summary','quotations_report','demand_fulfillment','growth_retention','customer_statement'])
def test_every_report_renders_and_validates_dates(env,key):
    r=preview(env,key);assert r.status_code==200,r.text
    assert preview(env,key,date_from='2026-12-01',date_to='2026-01-01').status_code==422


def test_module_disabled_and_no_permission_hide_sections(env,monkeypatch):
    quote(env)
    monkeypatch.setattr(providers,'module_enabled',lambda db,t,module:False)
    ds=env.client.get('/api/v1/reports/definitions?module=customers').json()
    profile=next(d for d in ds if d['key']=='customers.customer_profile')
    assert 'quotations' not in {s['key'] for s in profile['sections']}
    env.ctx.auth_user.permissions.remove('commercial:quotes:read')
    assert preview(env,sections=['quotations']).status_code==403


def test_quotation_conversion_currencies_and_ranking(env):
    quote(env);quote(env,'rejected');quote(env,'expired','USD','90')
    assert builders.conversion(providers.commercial_factory(env.db,env.ctx.tenant).quotations([env.customer.id]))==Decimal('33.33')
    assert builders.conversion([])==0
    r=preview(env,'activity_summary',sections=['quotations'],lang='en');assert r.status_code==200,r.text
    assert 'SAR' in r.text and 'USD' in r.text and '240' in r.text and '90' in r.text
    assert 'class="bar"' in r.text and '330' not in r.text.split('<main>')[-1]


def test_single_shared_order_results_and_signed_correction(env):
    po=env.planned(quantity='100')
    env.added(po,'customer_good','60')
    env.added(po,'scrap','5')
    r=preview(env,sections=['orders','results','losses'],lang='en');assert r.status_code==200,r.text
    assert 'Single customer' in r.text and '60' in r.text and 'Loss, samples' in r.text
    other=Customer(organization_id=env.org.id,customer_code='OTHER',name='Other customer')
    env.db.add(other);env.db.flush()
    d=ProductionDemand(organization_id=env.org.id,demand_number='OTHER-D',customer_id=other.id)
    d.items=[ProductionDemandItem(line_no=1,product_type='film',required_quantity=200,unit='kg')]
    env.db.add(d);env.db.flush()
    env.db.add(ProductionAllocation(organization_id=env.org.id,production_order_id=UUID(po['id']),production_demand_id=d.id,
        production_demand_item_id=d.items[0].id,allocated_quantity=100,unit='kg'))
    env.db.commit()
    r=preview(env,audience='customer',sections=['orders','results','losses'],lang='en')
    assert r.status_code==200,r.text
    assert 'Shared order' in r.text and 'Other customer' not in r.text and 'Loss, samples' not in r.text
    # The customer sees its own allocation only: neither the order's total (200) nor its order-level output (60).
    assert '100.000 kg' in r.text and '200' not in r.text and 'Total allocated' not in r.text
    assert 'Not shown for a shared order' in r.text and '60.000' not in r.text and 'Stock good' not in r.text
    internal=preview(env,audience='internal',sections=['orders','results'],lang='en').text
    assert '200.000 kg' in internal and '60.000' in internal and 'Stock good' in internal
    read=providers.production_factory(env.db,env.ctx.tenant).results([UUID(po['id'])])[0]
    assert type(read) is ResultRead and not hasattr(read,'scrap')


def test_scope_shortcut_lookups_and_cross_tenant(env):
    p=Permission(organization_id=env.org.id,code='commercial:customers:read',name='Read',description='Read customers',module_name='commercial',resource_name='customers',action_name='read')
    role=Role(organization_id=env.org.id,name='Own',code='own')
    env.db.add_all([p,role]);env.db.flush()
    env.db.add_all([RolePermission(role_id=role.id,permission_id=p.id,scope='own'),UserRole(user_id=env.user.id,role_id=role.id)])
    other=Customer(organization_id=env.org.id,customer_code='HIDDEN',name='Hidden customer')
    org=Organization(name='Other org',code='OTHERORG',timezone='UTC')
    env.db.add_all([other,org]);env.db.flush()
    foreign=Customer(organization_id=org.id,customer_code='FOREIGN',name='Foreign customer')
    env.db.add(foreign);env.db.commit()
    env.ctx.tenant=replace(env.ctx.tenant,is_organization_root=False)
    for cid in [other.id,foreign.id,uuid4()]:
        assert preview(env,customer_id=str(cid)).status_code==404
        assert env.client.get(f'/api/v1/customers/{cid}/report.pdf').status_code==404
    rows=env.client.get('/api/v1/reports/customers/lookups/customers').json()
    assert [r['id'] for r in rows]==[str(env.customer.id)]
    assert preview(env,'directory').status_code==200
    env.ctx.auth_user.permissions.remove('commercial:customers:read')
    assert env.client.get('/api/v1/reports/customers/lookups/customers').status_code==403


def test_fulfillment_and_limits(env,monkeypatch):
    env.planned(quantity='100')
    rows=providers.production_factory(env.db,env.ctx.tenant).demands([env.customer.id])
    assert rows[0].quantity==1000 and rows[0].allocated==100 and rows[0].unallocated==900
    monkeypatch.setattr(queries,'LIMIT',0)
    assert preview(env,'directory').status_code==422


def test_growth_inactivity_days(env):
    env.customer.created_at=datetime.now(timezone.utc)-timedelta(days=150);env.db.commit()
    quote(env,when=datetime.now(timezone.utc)-timedelta(days=100))
    r=preview(env,'growth_retention',sections=['inactivity'],inactive_days=90,lang='en')
    assert r.status_code==200 and '&lt;script&gt;' in r.text
    r=preview(env,'growth_retention',sections=['inactivity'],inactive_days=120,lang='en')
    assert r.status_code==200 and '&lt;script&gt;' not in r.text
    assert preview(env,organization_id=str(env.org.id)).status_code==422


def test_architecture():
    root=Path(__file__).parents[2]/'app'
    for path in (root/'core/reporting').glob('*.py'):
        assert 'from app.production' not in path.read_text(encoding='utf-8')
    for path in (root/'commercial/reporting/customers').glob('*.py'):
        source=path.read_text(encoding='utf-8')
        assert 'production.infrastructure' not in source and 'production.application' not in source


def test_customer_shortcut_route_declares_policy():
    from app.main import app
    from tests.production.test_production_rbac import _policies
    route=next(r for r in app.routes if getattr(r,'path','')=='/api/v1/customers/{customer_id}/report.pdf')
    assert list(_policies(route.dependant))


def test_customer_statement_and_audience_validation(env):
    assert preview(env,'customer_statement',audience='customer').status_code==200
    assert preview(env,'directory',audience='customer').status_code==422
    assert preview(env,'demand_fulfillment',audience='customer').status_code==422
    assert preview(env,audience='outside').status_code==422
    assert preview(env,sections=['not-a-section']).status_code==422
    assert preview(env,'directory',has_active_orders=True,sections=['directory']).status_code==200
    env.ctx.auth_user.permissions.remove('production:production_orders:read')
    assert preview(env,'directory',has_active_orders=True,sections=['directory']).status_code==403


def test_followup_activity_is_internal_and_permission_checked(env):
    env.db.add(FollowUp(customer_id=env.customer.id,assigned_user_id=env.user.id,created_by_user_id=env.user.id,
        due_date=datetime.now(timezone.utc),reason='PRIVATE FOLLOWUP'))
    env.db.commit()
    assert preview(env,sections=['followups']).status_code==403
    env.ctx.auth_user.permissions.add('commercial:follow_ups:read')
    assert 'PRIVATE FOLLOWUP' in preview(env,sections=['followups']).text
    r=preview(env,audience='customer',sections=['followups'])
    assert r.status_code==200 and 'PRIVATE FOLLOWUP' not in r.text


def test_released_allocations_excluded_and_corrections_signed(env):
    po=env.planned(quantity='100')
    env.added(po,'customer_good','60')
    original=env.result(po)['entries'][0]
    env.close(po)
    r=env.client.post(f"/api/v1/production/production-orders/{po['id']}/result/entries/{original['id']}/corrections",
        json={'quantity':'-10','correction_reason':'Measured adjustment'})
    assert r.status_code==201,r.text
    totals=providers.production_factory(env.db,env.ctx.tenant).results([UUID(po['id'])])
    assert totals[0].customer_good==50


def test_shared_layout_audiences_and_labelled_details():
    from app.core.reporting.contracts import ReportData, TableSection
    from app.core.reporting.layout import render_layout
    from app.core.reporting.service import template_roots
    from app.core.reporting.registry import registry
    for lang in ['ar', 'en']:
        for audience in ['internal', 'customer']:
            data = ReportData(sections=[TableSection(key='information', title='Info', layout='fields', rows=[['Order', 'PO-TEST']]),
                                        TableSection(key='t', title='T', columns=['Qty'], rows=[['400.000']])],
                              provisional=True, subject='PO-TEST', prepared_for='Acme <b>')
            context = dict(data=data, lang=lang, branding=dict(name='Test', primary_color='#123456'), title='Title',
                           generated_at='2026-10-01', generated_by='Actor', filters='', body_template='production_body.html', audience=audience,
                           watermark=registry.get('production.order_full').watermark(data, lang))
            html = render_layout(context, template_roots)[0]
            assert ('تاريخ الإصدار' if lang == 'ar' else 'Issued') in html and 'RPT-' not in html
            assert '<dl class="fields"><div class="field"><dt>Order</dt>' in html and 'class="num"' in html
            assert '--brand: #123456' in html and 'class="watermark"' in html
            assert ('Actor' in html) == (audience == 'internal')
            assert ('Acme &lt;b&gt;' in html) == (audience == 'customer') and 'Acme <b>' not in html


@pytest.mark.skipif(__import__('os').environ.get('RUN_RENDERER_TESTS')!='1',reason='Real Chromium opt-in')
def test_real_customer_pdf_samples(env):
    import pymupdf
    env.customer.name='عميل تجريبي للتقارير'
    env.customer.phone='0500000000'
    env.db.commit()
    quote(env)
    po=env.planned(quantity='100')
    env.added(po,'customer_good','60');env.added(po,'scrap','5')
    from tests.report_samples import samples_dir
    output=samples_dir('customer-reports')
    output.mkdir(parents=True,exist_ok=True)
    samples=[('C1-internal','customer_profile','internal'),('C1-customer','customer_profile','customer'),
        ('C2','directory','internal'),('C3','activity_summary','internal'),('C5','demand_fulfillment','customer'),
        ('C7','customer_statement','customer'),('C1-customer-en','customer_profile','customer')]
    for name,key,audience in samples:
        params=dict(lang='en' if name.endswith('-en') else 'ar',audience=audience,customer_id=str(env.customer.id))
        if key in {'directory','activity_summary'}:params['orientation']='landscape'
        html=preview(env,key,**params)
        assert html.status_code==200,html.text
        (output/f'{name}.html').write_text(html.text,encoding='utf-8')
        pdf=env.client.post('/api/v1/reports/customers.'+key+'/pdf',json=params)
        assert pdf.status_code==200,pdf.text[:200] if pdf.status_code!=200 else ''
        assert pdf.content.startswith(b'%PDF-') and "filename*=UTF-8''" in pdf.headers['content-disposition']
        (output/f'{name}.pdf').write_bytes(pdf.content)
        doc=pymupdf.open(stream=pdf.content,filetype='pdf')
        extracted=''.join(page.get_text() for page in doc)
        assert ('ملف العميل' in extracted or 'Customer profile' in extracted or 'كشف' in extracted or 'دليل' in extracted or 'نشاط' in extracted
                or 'حالة' in extracted) and any('\u0600'<=c<='\u06ff' for c in extracted)
        if audience=='customer':assert 'SECRET INTERNAL NOTE' not in extracted
        doc[0].get_pixmap(matrix=pymupdf.Matrix(1,1)).save(str(output/f'{name}.png'))


def test_customer_audience_hides_internal_classification_kpis_and_drafts(env):
    quote(env, status='accepted', total='120'); quote(env, status='draft', total='4321.77')
    env.customer.status = 'on_hold'; env.db.commit()
    text = preview(env, audience='customer', sections=['information', 'quotations'], lang='en').text
    assert 'Conversion' not in text and '4321.77' not in text and '120' in text
    assert 'On hold' not in text and '>Status<' not in text.split('Quotations')[0]
    internal = preview(env, audience='internal', sections=['information', 'quotations'], lang='en').text
    assert 'Conversion' in internal and '4321.77' in internal and 'On hold' in internal  # readable English status


def test_report_list_does_not_read_every_customer(env, monkeypatch):
    env.db.add_all([Customer(organization_id=env.org.id, customer_code=f'BULK{i}', name=f'Bulk {i}') for i in range(3)]); env.db.commit()
    monkeypatch.setattr(queries, 'LIMIT', 2)
    r = env.client.get('/api/v1/reports/definitions?module=customers')
    assert r.status_code == 200 and r.json()
    # The report itself still refuses clearly, through the read API's limit error.
    r = preview(env, 'directory', audience='internal')
    assert r.status_code == 422 and r.json()['detail'] == 'REPORT_ROW_LIMIT_NARROW_FILTERS'


def test_export_history_screen_and_permission_are_gone(env):
    from app.foundation.domain.permission_catalog import ALL_PERMISSION_CODES
    from app.foundation.domain.system_roles import SYSTEM_ROLES
    assert env.client.get('/api/v1/reports/exports').status_code in (404, 405)
    assert 'reports:exports:read' not in ALL_PERMISSION_CODES
    assert not [r['code'] for r in SYSTEM_ROLES if 'reports:exports:read' in r['permissions']]


def test_read_apis_raise_a_limit_error_not_http():
    import inspect
    from app.commercial.application import report_queries
    from app.production.application import customer_report_queries
    for module in (report_queries, customer_report_queries):
        assert 'HTTPException' not in inspect.getsource(module)
