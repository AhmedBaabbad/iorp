from io import BytesIO
from uuid import UUID, uuid4
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from PIL import Image
from sqlalchemy import select
from tests.production.test_order_results import env as result_env
from app.core.reporting.service import ReportingService
from app.foundation.application.branding_service import BrandingService
from app.foundation.api.branding_schemas import BrandingUpdate
from app.core.storage import LocalFileStorage, InvalidLogoError
from app.production.reporting import builders
from app.production.reporting.schemas import SummaryParams, AnalysisParams
from app.production.infrastructure.models import ProductionOrder


@pytest.fixture
def env(result_env):
    e=result_env
    e.ctx.user.id=e.user.id
    e.ctx.user.full_name=e.user.full_name
    e.ctx.auth_user.permissions |= {'reports:production:order_full','reports:production:orders_summary','reports:production:results_analysis','organization:branding:read','organization:branding:update'}
    return e


def preview(env,key='order_full',**params):
    return env.client.post('/api/v1/reports/production.'+key+'/preview',json=params)


def test_definitions_permissions_and_conditional_sections(env):
    r=env.client.get('/api/v1/reports/definitions?module=production')
    assert r.status_code==200
    assert len(r.json())==3
    full=next(d for d in r.json() if d['key']=='production.order_full')
    assert not {'execution','workforce','downtime','waste'} & {s['key'] for s in full['sections']}
    env.ctx.auth_user.permissions.remove('reports:production:results_analysis')
    assert not any(d['key']=='production.results_analysis' for d in env.client.get('/api/v1/reports/definitions').json())


@pytest.mark.parametrize('status',['draft','released','in_progress','on_hold','completed','closed','cancelled'])
def test_order_all_statuses_and_result_visibility(env,status):
    po=env.bare('kg',status=status)
    r=preview(env,order_id=po['id'])
    assert r.status_code==200,r.text
    assert ('Interim report' in r.text or 'تقرير مرحلي' in r.text)==(status!='closed')
    assert ('النتيجة النهائية' in r.text)==(status in ('completed','closed'))
    assert 'أعدّه' in r.text and env.user.full_name in r.text  # who prepared it is printed, nothing is stored


def test_sections_escaping_and_permissions(env):
    po=env.bare('kg')
    order=env.db.get(ProductionOrder,UUID(po['id']));order.notes='<script>alert(1)</script>';env.db.commit()
    r=preview(env,order_id=po['id'],sections=['notes'])
    assert r.status_code==200 and '&lt;script&gt;' in r.text and '<script>' not in r.text
    assert 'معلومات الأمر' not in r.text
    assert preview(env,order_id=po['id'],sections=['workforce']).status_code==403
    assert preview(env,order_id=po['id'],sections=['unknown']).status_code==422
    env.ctx.auth_user.permissions.remove('reports:production:order_full')
    assert preview(env,order_id=po['id']).status_code==403


@pytest.mark.parametrize('key,params',[('order_full',{}),('orders_summary',{'date_from':'2026-12-01','date_to':'2026-01-01'}),('results_analysis',{'period':'quarter'})])
def test_invalid_params(env,key,params):
    assert preview(env,key,**params).status_code==422


def test_other_tenant_and_body_org_rejected(env):
    assert preview(env,order_id=str(uuid4())).status_code==404
    po=env.bare('kg')
    assert preview(env,order_id=po['id'],organization_id=str(uuid4())).status_code==422


def test_summary_formulas_and_mixed_units(env):
    po=env.bare('kg','m')
    env.added(po,'stock_good','20',line=0)
    env.added(po,'scrap','5',line=0)
    env.added(po,'sample','5',line=0,counts_as_loss=True)
    env.added(po,'stock_good','12',line=1)
    data=builders.orders_summary(env.db,env.ctx.tenant,SummaryParams(),{'orders','totals'})
    totals=data.sections[-1].rows
    kg=next(r for r in totals if r[0]=='kg');metres=next(r for r in totals if r[0]=='m')
    assert Decimal(kg[2])==20 and Decimal(kg[4])==Decimal('33.33')
    assert Decimal(metres[2])==12 and len(totals)==2
    r=preview(env,order_id=po['id'],sections=['result'],lang='en')
    assert r.status_code==200 and '33.33' in r.text and '20' in r.text
    assert preview(env,'orders_summary',product='not-present').status_code==200


def test_analysis_completion_period_and_zero_denominator(env):
    po=env.bare('kg');env.added(po,'scrap','5',reason_code='damaged')
    order=env.db.get(ProductionOrder,UUID(po['id']));order.actual_end_at=datetime(2026,10,1,tzinfo=timezone.utc);env.db.commit()
    data=builders.results_analysis(env.db,env.ctx.tenant,AnalysisParams(period='month'),{'analysis','reasons','trend'})
    assert data.sections[0].rows[0][1]=='2026-10'
    assert Decimal(data.sections[0].rows[0][9])==0
    assert 'damaged' in str(data.sections[1].rows)
    assert preview(env,'results_analysis',date_from='2027-01-01').status_code==200


def test_row_limit(env,monkeypatch):
    env.bare('kg');env.bare('kg');monkeypatch.setattr(builders,'LIMIT',1)
    r=preview(env,'orders_summary')
    assert r.status_code==422 and 'NARROW_FILTERS' in r.text


def test_pdf_response_headers_and_render_failure(env,monkeypatch, caplog):
    po=env.bare('kg')
    from app.core.reporting.renderers import GotenbergRenderer,RenderError
    monkeypatch.setattr(GotenbergRenderer,'render',lambda *a,**k:(b'%PDF-1.7\nfixture',1))
    r=env.client.post('/api/v1/reports/production.order_full/pdf',json={'order_id':po['id']})
    assert r.status_code==200 and r.content.startswith(b'%PDF-')
    assert "filename*=UTF-8''" in r.headers['content-disposition']
    def fail(*args,**kwargs): raise RenderError('test')
    monkeypatch.setattr(GotenbergRenderer,'render',fail)
    assert env.client.post('/api/v1/reports/production.order_full/pdf',json={'order_id':po['id']}).status_code==503
    assert any('production.order_full failed' in m and 'REPORT_GENERATION_FAILED' in m for m in caplog.messages)  # server log, no table


def test_branding_tenant_scoped_placeholder_and_validation(env,tmp_path):
    service=BrandingService(env.db,LocalFileStorage(str(tmp_path)))
    data=service.get_branding(env.org.id)
    assert data['logo_data_uri'].startswith('data:image/png;base64,')
    service.update(env.org.id,BrandingUpdate(legal_name_ar='شركة الاختبار',vat_number='300000000000003'),env.user.id)
    assert service.get_branding(env.org.id)['vat_number']=='300000000000003'
    for content in [b'<svg/>',b'not-image',b'\x89PNG\r\n\x1a\nfake',b'x'*(2*1024*1024+1)]:
        with pytest.raises(InvalidLogoError): service.upload(env.org.id,content,env.user.id)
    im=Image.new('RGB',(10,10));buffer=BytesIO();im.save(buffer,'PNG')
    uploaded=service.upload(env.org.id,buffer.getvalue(),env.user.id)
    assert uploaded['logo_asset_id'] is not None
    assert service.remove(env.org.id,env.user.id)['logo_asset_id'] is None
    assert env.client.put('/api/v1/organization/branding',json={'organization_id':str(uuid4())}).status_code==422
    env.ctx.auth_user.permissions.remove('organization:branding:update')
    assert env.client.put('/api/v1/organization/branding',json={}).status_code==403


# ---- review fixes (PROD-REPORT-001) ---------------------------------------------------------------

import ast
import os
from pathlib import Path
from urllib.parse import unquote
from sqlalchemy.exc import OperationalError
from app.core.reporting import providers
from app.core.reporting.registry import registry
from app.production.infrastructure.models import DowntimeEvent, WasteRecord, WasteRecordCategory
from tests.test_production_allocation_lifecycle import other_org_demand

APP = Path(__file__).resolve().parents[2] / 'app'
FORBIDDEN_IN_CORE = (['app', 'foundation'], ['app', 'production'], ['app', 'commercial'], ['app', 'workforce'], ['app', 'quality'])
FORBIDDEN_IN_PRODUCTION = (['app', 'foundation'], ['app', 'commercial'], ['app', 'workforce'])


def _imports(folder):
    found = set()
    for file in (APP / folder).rglob('*.py'):
        for node in ast.walk(ast.parse(file.read_text(encoding='utf-8'))):
            if isinstance(node, ast.ImportFrom) and node.module:
                found.add((file.name, node.module))
            elif isinstance(node, ast.Import):
                found.update((file.name, alias.name) for alias in node.names)
    return found


def _disposition_filename(response):
    return unquote(response.headers['content-disposition'].split("UTF-8''")[1])


def test_reporting_core_imports_no_business_module():
    assert {(f, m) for f, m in _imports('core/reporting') if m.split('.')[:2] in FORBIDDEN_IN_CORE} == set()


def test_production_reports_never_import_other_modules_models():
    assert {(f, m) for f, m in _imports('production/reporting') if m.split('.')[:2] in FORBIDDEN_IN_PRODUCTION} == set()


def test_arabic_values_keep_their_direction(env):
    po = env.bare('kg')
    r = preview(env, order_id=po['id'], sections=['information'])
    assert '<td><bdi>' in r.text and '<bdi dir="ltr">' in r.text


def test_labels_and_terms_follow_the_report_language(env):
    po = env.bare('kg')
    env.added(po, 'scrap', '5')
    env.added(po, 'stock_good', '20')
    ar_text = preview(env, order_id=po['id'], sections=['information', 'result']).text
    assert 'عادية' in ar_text and 'نسبة الهالك' in ar_text and 'نسبة الجيد' in ar_text
    assert 'خسارة' not in ar_text and '/ Order' not in ar_text and '>normal<' not in ar_text
    en_text = preview(env, order_id=po['id'], sections=['information'], lang='en').text
    assert '>Order<' in en_text and 'رقم الأمر' not in en_text and 'Normal' in en_text


def test_downtime_and_waste_sections_show_cause_and_type(env):
    po = env.bare('kg', status='in_progress')
    order_id = UUID(po['id'])
    env.db.add(DowntimeEvent(organization_id=env.org.id, work_center_id=env.center.id, production_order_id=order_id,
                             start_time=datetime(2026, 9, 29, 8, tzinfo=timezone.utc), end_time=datetime(2026, 9, 29, 8, 30, tzinfo=timezone.utc),
                             duration_minutes=Decimal('30'), category='breakdown', planned=False, status='closed', created_by_user_id=env.user.id))
    env.db.add(WasteRecord(organization_id=env.org.id, production_order_id=order_id, work_center_id=env.center.id, waste_date=datetime(2026, 9, 29).date(),
                           quantity_wasted=Decimal('3'), unit='kg', created_by_user_id=env.user.id,
                           categories=[WasteRecordCategory(organization_id=env.org.id, category='process', quantity=Decimal('3'))]))
    env.db.commit()
    body = preview(env, order_id=po['id'], sections=['downtime', 'waste']).text
    assert 'عطل' in body and 'فقد في التوافر' in body and 'هالك العملية' in body and 'لا يُضاف إلى هالك النتيجة النهائية' in body


def test_customer_lookup_needs_customer_permission(env):
    assert env.client.get('/api/v1/reports/production/lookups/customers').status_code == 403
    env.ctx.auth_user.permissions.add('commercial:customers:read')
    assert [c['label'] for c in env.client.get('/api/v1/reports/production/lookups/customers').json()] == ['Result Customer']


def test_lookups_are_tenant_scoped(env):
    other_org_demand(env.db)
    env.ctx.auth_user.permissions |= {'production:work_centers:read'}
    assert [c['label'] for c in env.client.get('/api/v1/reports/production/lookups/centers').json()] == ['Line 1']
    assert env.client.get('/api/v1/reports/production/lookups/unknown').status_code == 404


def test_lookups_need_the_entity_read_permission(env):
    # PROD-RBAC-001: a lookup lists one entity, so it needs that entity's read permission too.
    r = env.client.get('/api/v1/reports/production/lookups/centers')
    assert r.status_code == 403 and r.json()['detail'] == 'LOOKUP_FORBIDDEN'
    assert env.client.get('/api/v1/reports/production/lookups/orders').status_code == 200
    env.ctx.auth_user.permissions -= {'production:production_orders:read'}
    assert env.client.get('/api/v1/reports/production/lookups/orders').status_code == 403
    assert env.client.get('/api/v1/reports/production/lookups/products').status_code == 403


def test_reports_are_not_stored_and_carry_no_reference(env):
    # Generated from current data on each request: no audit table, no RPT- reference, no history API.
    from app.core.db import Base
    po = env.bare('kg')
    text = preview(env, order_id=po['id']).text
    assert 'RPT-' not in text and 'رقم المرجع' not in text and 'تاريخ الإصدار' in text
    assert not {'report_exports', 'report_counters'} & set(Base.metadata.tables)
    assert env.client.get('/api/v1/reports/exports').status_code in (404, 405)


def test_pdf_filename_is_in_the_report_language(env, monkeypatch):
    po = env.bare('kg')
    from app.core.reporting.renderers import GotenbergRenderer
    monkeypatch.setattr(GotenbergRenderer, 'render', lambda *a, **k: (b'%PDF-1.7\nfixture', 1))
    ar_name = _disposition_filename(env.client.post('/api/v1/reports/production.order_full/pdf', json={'order_id': po['id']}))
    en_name = _disposition_filename(env.client.post('/api/v1/reports/production.order_full/pdf', json={'order_id': po['id'], 'lang': 'en'}))
    assert ar_name.startswith('تقرير_أمر_الإنتاج_PO-') and ar_name.endswith('.pdf')
    assert en_name.startswith('Production_order_report_PO-')


def test_branding_comes_through_the_provider_seam(env, monkeypatch):
    po = env.bare('kg')
    real = providers.branding_provider
    monkeypatch.setattr(providers, 'branding_provider', lambda db, org: {**real(db, org), 'legal_name_ar': 'هوية من المزوّد'})
    assert 'هوية من المزوّد' in preview(env, order_id=po['id']).text


def test_slow_report_fails_clearly(env, monkeypatch):
    definition = registry.get('production.orders_summary')
    def slow(*args, **kwargs):
        raise OperationalError('SELECT', {}, Exception('canceling statement due to statement timeout'))
    monkeypatch.setitem(registry.definitions, 'production.orders_summary', type(definition)(**{**definition.__dict__, 'builder': slow}))
    r = preview(env, 'orders_summary')
    assert r.status_code == 504 and r.json()['detail'] == 'REPORT_TIMEOUT_NARROW_FILTERS'


@pytest.mark.skipif(os.environ.get('REPORT_RENDERER_TESTS') != '1', reason='Needs the report renderer (docker compose up report-renderer report-gateway)')
def test_real_pdf_arabic_header_footer_and_pages(env):
    import pymupdf
    po = env.planned({'width_mm': 10}, {'width_mm': 20}, to='in_progress')
    r = env.client.post('/api/v1/reports/production.order_full/pdf', json={'order_id': po['id']})
    assert r.status_code == 200 and r.content.startswith(b'%PDF-')
    pages = list(pymupdf.open(stream=r.content, filetype='pdf'))
    assert pages
    for n, page in enumerate(pages, 1):
        body = page.get_text()
        assert ('صفحة' in body or 'ةحفص' in body) and str(n) in body and str(len(pages)) in body
    assert any('الإنتاج' in p.get_text() or 'جاتنإلا' in p.get_text() for p in pages)


@pytest.mark.skipif(not os.environ.get('REPORT_SAMPLES_DIR'), reason='Writes review samples: REPORT_SAMPLES_DIR=<folder> with the renderer running')
def test_write_review_samples(env):
    """R1 in progress, R1 closed (Arabic and English), R2 and R3, through the real renderer, for visual review."""
    out = Path(os.environ['REPORT_SAMPLES_DIR']); out.mkdir(parents=True, exist_ok=True)
    def save(key, name, **params):
        r = env.client.post(f'/api/v1/reports/production.{key}/pdf', json=params)
        assert r.status_code == 200, r.text
        (out / name).write_bytes(r.content)
    BrandingService(env.db).update(env.org.id, BrandingUpdate(legal_name_ar='شركة مثال للصناعة', legal_name_en='Example Manufacturing Co.',
        commercial_registration_no='1010000000', vat_number='300000000000003', address_ar='المدينة الصناعية', address_en='Industrial City'), env.user.id)
    running = env.planned({'width_mm': 10, 'color': 'أزرق'}, {'width_mm': 20, 'color': 'Red'}, to='in_progress')
    save('order_full', 'R1-in-progress.pdf', order_id=running['id'])
    done = env.planned({'width_mm': 30}, quantity='400')
    env.added(done, 'customer_good', '300'); env.added(done, 'stock_good', '50'); env.added(done, 'scrap', '20', reason_code='EDGE')
    env.added(done, 'sample', '5', counts_as_loss=True)
    env.close(done)
    save('order_full', 'R1-closed.pdf', order_id=done['id'])
    save('order_full', 'R1-closed-en.pdf', order_id=done['id'], lang='en')
    save('orders_summary', 'R2.pdf')
    save('results_analysis', 'R3.pdf')
