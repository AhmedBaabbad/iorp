from datetime import datetime, timezone
from uuid import uuid4
import os
import pytest
from app.commercial.infrastructure.models import Sample, SampleEvaluation, Customer
from app.commercial.reporting.customers import queries
from tests.commercial.test_customer_reports import env, preview, reports_env, result_env


@pytest.fixture
def samples(env):
    e=env
    s=Sample(customer_id=e.customer.id,sample_code='RFS-REPORT',product_type='Legacy product',
        request_date=datetime(2026,10,6,10,tzinfo=timezone.utc),status='evaluated',sample_decision='pending',
        requested_spec_json={'Legacy width':12,'Nested':{'Color':'Blue'}},is_sample_requested=True,
        requested_sample_quantity=3,unit='roll',notes='PRIVATE SAMPLE NOTE',created_by_user_id=e.user.id)
    e.db.add(s);e.db.flush()
    e.db.add(SampleEvaluation(sample_id=s.id,evaluation_date=datetime(2026,11,1,tzinfo=timezone.utc),
        result_status='needs_modification',next_action='revise_sample',comments='PRIVATE EVALUATION',evaluated_by_user_id=e.user.id))
    e.db.commit();e.sample=s
    return e


def test_profile_and_standalone_include_samples_and_readable_values(samples):
    e=samples
    for key in ['customer_profile','samples_report']:
        r=preview(e,key,lang='en',sections=['samples','sample_properties','sample_evaluations'])
        assert r.status_code==200,r.text
        for text in ['RFS-REPORT','Legacy width','Blue','roll','Needs modification',e.user.full_name,'PRIVATE EVALUATION']:
            assert text in r.text
        assert 'requested_spec_json' not in r.text


def test_sample_filters_and_evaluation_date_semantics(samples):
    e=samples
    r=preview(e,'samples_report',date_from='2026-10-06',date_to='2026-10-06',sample_status='evaluated',sample_decision='pending',product='Legacy product',lang='en')
    assert r.status_code==200 and 'PRIVATE EVALUATION' in r.text
    for filters in [dict(date_to='2026-10-05'),dict(sample_status='requested'),dict(sample_decision='accepted'),dict(product='Other')]:
        r=preview(e,'samples_report',**filters)
        assert r.status_code==200 and 'RFS-REPORT' not in r.text
    assert preview(e,'samples_report',sample_status='invented').status_code==422


def test_customer_copy_omits_evaluations_and_notes(samples):
    r=preview(samples,audience='customer',sections=['samples','sample_properties','sample_evaluations'])
    assert r.status_code==200 and 'RFS-REPORT' in r.text
    assert 'PRIVATE SAMPLE NOTE' not in r.text and 'PRIVATE EVALUATION' not in r.text


def test_permissions_enforced_for_samples_and_evaluations(samples):
    e=samples;e.ctx.auth_user.permissions.remove('commercial:evaluations:read')
    assert preview(e,'samples_report',sections=['sample_evaluations']).status_code==403
    assert preview(e,'samples_report',sections=['samples']).status_code==200
    e.ctx.auth_user.permissions.remove('commercial:samples:read')
    assert preview(e,'samples_report').status_code==403
    assert preview(e,sections=['samples']).status_code==403
    assert e.client.get('/api/v1/reports/customers/lookups/sample_products').status_code==403


def test_sample_lookup_and_foreign_customer_exclusion(samples):
    from app.foundation.infrastructure.models import Organization
    e=samples;other=Organization(name='Other sample org',code='SAMPLE-OTHER',timezone='UTC')
    e.db.add(other);e.db.flush()
    c=Customer(organization_id=other.id,customer_code='FOREIGN',name='Foreign customer')
    e.db.add(c);e.db.flush()
    e.db.add(Sample(customer_id=c.id,sample_code='FOREIGN-SAMPLE',product_type='Foreign product',request_date=datetime.now(timezone.utc),created_by_user_id=e.user.id))
    e.db.commit()
    r=preview(e,'samples_report');assert r.status_code==200 and 'FOREIGN-SAMPLE' not in r.text
    lookup=e.client.get('/api/v1/reports/customers/lookups/sample_products')
    assert lookup.status_code==200 and lookup.json()==[{'id':'Legacy product','label':'Legacy product'}]
    assert preview(e,'samples_report',customer_id=str(c.id)).status_code==404


def test_master_data_labels_choices_and_separate_unit_totals(samples):
    from app.masterdata.infrastructure.models import Product, ProductProperty
    e=samples
    p=Product(organization_id=e.org.id,code='REPORT-P',key='report_product',name_ar='منتج تقارير',name_en='Report product',created_by_user_id=e.user.id)
    p.properties=[ProductProperty(line_no=1,key='finish',name_ar='التشطيب',name_en='Surface finish',kind='choice',
        options=[{'value':'smooth','label_ar':'ناعم','label_en':'Smooth finish'}])]
    e.db.add(p)
    e.sample.product_type=p.key;e.sample.requested_spec_json={'finish':'smooth'}
    e.db.add(Sample(customer_id=e.customer.id,sample_code='RFS-KG',product_type=p.key,request_date=e.sample.request_date,
        created_by_user_id=e.user.id,is_sample_requested=True,requested_sample_quantity=7,unit='kg'))
    e.db.commit()
    from app.commercial.reporting.customers.schemas import SamplesParams
    from app.commercial.reporting.customers.builders import build
    data=build('samples_report',e.db,e.ctx.tenant,SamplesParams(lang='en'),{'samples','sample_properties'})
    cards=data.sections[0].cards
    assert ('Requested quantity (roll)','3.00') in cards
    assert ('Requested quantity (kg)','7.00') in cards
    assert len(data.sections[1].rows)==2
    assert any('Surface finish: Smooth finish' in row[2] for row in data.sections[1].rows)


def test_properties_have_one_row_per_sample(samples):
    from app.commercial.reporting.customers.schemas import SamplesParams
    from app.commercial.reporting.customers.builders import build
    e=samples
    for lang in ['ar','en']:
        data=build('samples_report',e.db,e.ctx.tenant,SamplesParams(lang=lang),{'sample_properties'})
        section=data.sections[0]
        assert len(section.rows)==1
        row=section.rows[0]
        assert row[:2]==[e.customer.name,'RFS-REPORT']
        assert len(row)==3
        assert 'Legacy width: 12' in row[2] and 'Color: Blue' in row[2]


def test_sample_report_honors_customer_ownership(samples,monkeypatch):
    from dataclasses import replace
    from app.core.interfaces.authorization_policy import AccessScope
    e=samples
    e.ctx.tenant=replace(e.ctx.tenant,is_organization_root=False)
    monkeypatch.setattr(queries,'resolve_effective_scope',lambda *args,**kwargs:AccessScope.OWN)
    e.customer.sales_owner_user_id=None;e.db.commit()
    r=preview(e,'samples_report')
    assert r.status_code==200 and 'RFS-REPORT' not in r.text
    assert e.client.get('/api/v1/reports/customers/lookups/sample_products').json()==[]


@pytest.mark.skipif(os.environ.get('RUN_RENDERER_TESTS')!='1',reason='Real Chromium opt-in')
def test_samples_pdf_real_renderer(samples):
    import pymupdf
    for lang in ['ar','en']:
        r=samples.client.post('/api/v1/reports/customers.samples_report/pdf',json={'lang':lang})
        assert r.status_code==200,r.text[:200]
        assert r.content.startswith(b'%PDF-')
        doc=pymupdf.open(stream=r.content,filetype='pdf')
        text=''.join(p.get_text() for p in doc)
        assert 'RFS-REPORT' in text and 'PRIVATE EVALUATION' in text
        from pathlib import Path
        out=Path('artifacts/customer-sample-reports');out.mkdir(parents=True,exist_ok=True)
        (out/f'samples-{lang}.pdf').write_bytes(r.content)
        doc[0].get_pixmap(matrix=pymupdf.Matrix(1,1)).save(str(out/f'samples-{lang}.png'))
