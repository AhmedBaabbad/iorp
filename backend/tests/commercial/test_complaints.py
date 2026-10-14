from types import SimpleNamespace
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select
from app.main import app
from app.dependencies import get_current_user, get_current_tenant
from app.core.auth import AuthenticatedUser
from app.core.tenancy import TenantContext
from app.commercial.infrastructure.models import Customer
from app.commercial.infrastructure.complaint_models import Complaint, ComplaintEvent

PATH='/api/v1/commercial/complaints'

@pytest.fixture
def setup(client,db,test_org,test_user):
    test_user.is_organization_root=True
    customer=Customer(organization_id=test_org.id,customer_code='CC-TEST',name='Complaint customer',sales_owner_user_id=test_user.id)
    db.add(customer);db.commit()
    tenant=TenantContext(user_id=test_user.id,organization_id=test_org.id,is_organization_root=True)
    current=SimpleNamespace(user=test_user,tenant=tenant,auth_user=AuthenticatedUser(test_user.id,test_org.id,'complaints@example.test'))
    app.dependency_overrides[get_current_user]=lambda:current
    app.dependency_overrides[get_current_tenant]=lambda:tenant
    return customer,test_user,tenant

def make(client,setup,**extra):
    customer,_,_=setup
    response=client.post(PATH,json=dict(customer_id=str(customer.id),title='Delivery concern',statement='Customer statement',received_date='2026-10-11',category='delivery',**extra))
    assert response.status_code==201,response.text
    return response.json()

def change(client,row,operation,**extra):
    response=client.post(f"{PATH}/{row['id']}/{operation}",json=dict(version=row['version'],**extra))
    assert response.status_code==200,response.text
    return response.json()

def processing(client,setup,**extra):
    row=make(client,setup,**extra)
    row=change(client,row,'assign',owner_user_id=str(setup[1].id),department='shipping',due_date='2026-10-20',reason='Dispatch review')
    assert row['status']=='processing'  # the first assignment starts the processing
    return row

def ready(client,setup,**extra):
    row=processing(client,setup,**extra)
    row=change(client,row,'investigate',finding='verified',investigation='Evidence checked',containment='Shipment held')
    return change(client,row,'resolve',resolution='Replacement',implementation_evidence='Delivered replacement',customer_response='Accepted on 12 October')

def test_lifecycle_persisted_history_and_lock(client,db,setup):
    row=ready(client,setup)
    row=change(client,row,'transitions',action='request_close',reason='Resolved')
    row=change(client,row,'transitions',action='approve_close',reason='Approved')
    assert row['status']=='closed' and row['closed_by_name']==setup[1].full_name
    response=client.post(f"{PATH}/{row['id']}/communications",json=dict(version=row['version'],notes='late edit'))
    assert response.status_code==409
    persisted=db.get(Complaint,UUID(row['id']))
    assert persisted.closed_at is not None and persisted.customer_response=='Accepted on 12 October'
    assert all(e['actor_name'] for e in row['events'])
    row=change(client,row,'transitions',action='reopen',reason='Issue recurred')
    assert row['status']=='processing' and row['closed_at'] is None

def test_stale_version_no_partial_write(client,db,setup):
    row=make(client,setup)
    change(client,row,'communications',notes='first')
    response=client.post(f"{PATH}/{row['id']}/communications",json=dict(version=row['version'],notes='stale'))
    assert response.status_code==409
    assert not db.scalar(select(ComplaintEvent.id).where(ComplaintEvent.notes=='stale'))

def test_quality_referral_atomic_link_and_duplicate_guard(client,db,setup):
    row=make(client,setup)
    row=change(client,row,'refer-quality',notes='Investigate technical findings')
    assert len(row['links'])==1 and row['links'][0]['kind']=='ncr'
    from app.quality.infrastructure.models import NonConformanceReport
    ncr=db.get(NonConformanceReport,UUID(row['links'][0]['record_id']))
    assert ncr.customer_id==setup[0].id and ncr.organization_id==setup[2].organization_id
    assert ncr.status=='open' and row['number'] in ncr.description
    response=client.post(f"{PATH}/{row['id']}/refer-quality",json=dict(version=row['version'],notes='Duplicate'))
    assert response.status_code==409
    assert len(client.get(f"{PATH}/{row['id']}").json()['links'])==1

def test_investigation_history_preserves_overwritten_fields(client,setup):
    row=make(client,setup)
    row=change(client,row,'investigate',finding='inconclusive',investigation='First',containment='Held all goods')
    row=change(client,row,'investigate',finding='not_verified',investigation='Second',containment='Released goods')
    assert row['containment']=='Released goods'
    last=row['events'][-1]
    assert last['details']['previous']['containment']=='Held all goods' and last['details']['finding']=='not_verified' and last['notes']==''

def test_closure_requires_evidence(client,setup):
    row=processing(client,setup)
    response=client.post(f"{PATH}/{row['id']}/transitions",json=dict(version=row['version'],action='request_close',reason='Done'))
    assert response.status_code==422 and response.json()['detail']=='CLOSURE_EVIDENCE_REQUIRED'

def test_critical_needs_independent_approver(client,setup):
    row=ready(client,setup,priority='critical')
    row=change(client,row,'transitions',action='request_close',reason='Done')
    response=client.post(f"{PATH}/{row['id']}/transitions",json=dict(version=row['version'],action='approve_close',reason='Approved'))
    assert response.status_code==422 and response.json()['detail']=='INDEPENDENT_APPROVAL_REQUIRED'

def test_unknown_product_and_spoofed_tenant_rejected(client,setup):
    base=dict(customer_id=str(setup[0].id),title='Test',statement='Claim',received_date='2026-10-11',category='quality')
    assert client.post(PATH,json={**base,'organization_id':str(uuid4())}).status_code==422
    response=client.post(PATH,json={**base,'items':[dict(product_key='unknown',unit='kg',delivered_quantity='10',reported_quantity='2')]})
    assert response.status_code==422 and response.json()['detail']=='PRODUCT_NOT_AVAILABLE'
    response=client.post(PATH,json={**base,'items':[dict(product_key='unknown',unit='kg',delivered_quantity='10',reported_quantity='20')]})
    assert response.status_code==422

def test_cross_tenant_record_and_customer_invisible(client,setup):
    row=make(client,setup)
    other=TenantContext(user_id=uuid4(),organization_id=uuid4(),is_organization_root=True)
    app.dependency_overrides[get_current_tenant]=lambda:other
    assert client.get(f"{PATH}/{row['id']}").status_code==404
    assert client.get(PATH).json()['total']==0
    response=client.post(PATH,json=dict(customer_id=str(setup[0].id),title='Bad',statement='Bad',received_date='2026-10-11',category='other'))
    assert response.status_code==404

def test_unqualified_assignee_rejected(client,setup):
    row=make(client,setup)
    response=client.post(f"{PATH}/{row['id']}/assign",json=dict(version=row['version'],owner_user_id=str(uuid4()),department='quality',due_date='2026-10-20',reason='assign'))
    assert response.status_code==422

def test_pagination_and_cap(client,setup):
    ids={make(client,setup)['id'] for _ in range(3)}
    pages=[client.get(PATH+f'?page={p}&page_size=2').json() for p in (1,2)]
    assert pages[0]['total']==3 and pages[0]['pages']==2
    assert {r['id'] for p in pages for r in p['items']}==ids
    assert client.get(PATH+'?page_size=101').status_code==422

def test_own_scope_does_not_widen(client,db,setup):
    make(client,setup)
    other_user=uuid4()
    tenant=TenantContext(user_id=other_user,organization_id=setup[2].organization_id)
    # No read scope grant must fall back to own, not organization, at the service layer.
    from app.commercial.application.complaint_service import ComplaintService
    assert list(db.scalars(ComplaintService(db,tenant).query()))==[]

def test_report_builder_uses_full_scope(client,db,setup):
    row=ready(client,setup)
    from app.commercial.reporting.complaints import Params,build
    result=build(db,setup[2],Params(complaint_id=UUID(row['id'])),{'register','investigation'})
    assert result.subject==row['number']
    assert any('Delivered replacement' in str(s.rows) for s in result.sections)

def test_summary_tracks_first_reply_and_scope(client,setup):
    row=make(client,setup,response_due_date='2026-10-11',due_date='2026-10-11')
    summary=client.get(PATH+'/summary').json()
    assert summary['total']==1 and summary['active']==1
    change(client,row,'communications',notes='Internal check only')
    assert [e['action'] for e in client.get(f"{PATH}/{row['id']}").json()['events']][-1]=='note'  # an internal follow-up is not a reply
    change(client,client.get(f"{PATH}/{row['id']}").json(),'communications',notes='Acknowledged by phone',to_customer=True)
    assert client.get(PATH+'/summary').json()['response_overdue']==0
    assert client.get(PATH+'/summary?customer_id='+str(uuid4())).json()['total']==0

def test_report_context_and_preview_escape(client,setup):
    row=make(client,setup)
    definitions=client.get('/api/v1/reports/definitions?module=customers&complaint_id='+row['id'])
    assert definitions.status_code==200,definitions.text
    definition=next(d for d in definitions.json() if d['key']=='customers.complaints')
    assert {s['key'] for s in definition['sections']}=={'register','investigation'}
    response=client.post('/api/v1/reports/customers.complaints/preview',json={'complaint_id':row['id'],'lang':'ar'})
    assert response.status_code==200,response.text
    assert row['number'] in response.text and 'Customer statement' in response.text
    assert client.post('/api/v1/reports/customers.complaints/preview',json={'date_from':'2026-12-01','date_to':'2026-01-01'}).status_code==422

def test_read_only_user_cannot_mutate(client,setup):
    row=make(client,setup)
    user,tenant=setup[1],setup[2]
    current=SimpleNamespace(user=SimpleNamespace(id=user.id,is_organization_root=False,full_name=user.full_name),
        tenant=TenantContext(user_id=user.id,organization_id=tenant.organization_id),
        auth_user=AuthenticatedUser(user.id,tenant.organization_id,'reader@example.test',permissions={'commercial:complaints:read'}))
    app.dependency_overrides[get_current_user]=lambda:current
    app.dependency_overrides[get_current_tenant]=lambda:current.tenant
    assert client.get(f"{PATH}/{row['id']}").status_code==200
    for operation,body in [('communications',{'notes':'no'}),('transitions',{'action':'cancel','reason':'no'}),('refer-quality',{'notes':'no'})]:
        assert client.post(f"{PATH}/{row['id']}/{operation}",json={'version':row['version'],**body}).status_code==403

def test_reference_customer_boundary(client,db,setup):
    row=make(client,setup)
    from app.quality.application.ncr_service import NCRService
    other=Customer(organization_id=setup[2].organization_id,customer_code='OTHER-COMPLAINT',name='Other')
    db.add(other);db.flush()
    report=NCRService(db,setup[2]).open_report(source_type='other',report_type='other',title='Other customer',description='Private',customer_id=other.id)
    db.commit()
    response=client.post(f"{PATH}/{row['id']}/links",json={'version':row['version'],'kind':'ncr','record_id':str(report.id)})
    assert response.status_code==404
    assert client.get(f"{PATH}/{row['id']}/references?kind=ncr").json()==[]


# ── COMPLAINTS-001 second step: readable history, numbering, specifications, measurements, roles ─────────────

from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import event as sa_event
from app.commercial.infrastructure.models import CommercialOrder, CommercialOrderItem, Sample
from app.commercial.domain.complaint_wording import describe


@pytest.fixture
def product(db,test_org,test_user):
    from app.masterdata.infrastructure.models import Product, ProductProperty
    row=Product(organization_id=test_org.id,code='PRD-CC',key='film',name_ar='فيلم',name_en='Film',created_by_user_id=test_user.id)
    row.properties=[ProductProperty(line_no=1,key='thickness',name_ar='السماكة',name_en='Thickness',kind='number',unit='mic'),
                    ProductProperty(line_no=2,key='width',name_ar='العرض',name_en='Width',kind='number',unit='mm')]
    db.add(row);db.commit()
    return row


def order_line(db,setup,spec):
    customer,user,tenant=setup
    order=CommercialOrder(organization_id=tenant.organization_id,customer_id=customer.id,order_number='RFS-2026-0007',
                          order_date=datetime(2026,10,1,tzinfo=timezone.utc),status='confirmed',created_by_user_id=user.id)
    order.items=[CommercialOrderItem(line_no=2,product_type='film',requested_spec_json=spec,quantity=Decimal('500'),unit='kg')]
    db.add(order);db.commit()
    return order.items[0]


def line(**extra):
    return {**dict(product_key='film',unit='kg',delivered_quantity='500',reported_quantity='120'),**extra}


def detail(client,row):
    return client.get(f"{PATH}/{row['id']}").json()


def test_history_names_people_and_holds_no_ids(client,setup):
    row=detail(client,processing(client,setup))
    assign=next(e for e in row['events'] if e['action']=='assign')
    assert assign['details']['owner_name']==setup[1].full_name and 'owner_user_id' not in assign['details']
    assert assign['details']['department']=='shipping' and assign['details']['due_date']=='2026-10-20' and assign['notes']=='Dispatch review'
    text=describe('assign',assign['details'],assign['notes'],'ar')
    assert setup[1].full_name in text and 'الشحن والتسليم' in text and '20/10/2026' in text and 'سبب الإسناد: Dispatch review' in text
    assert str(setup[1].id) not in str(row['events']) and 'shipping;' not in str(row['events'])
    assert assign['details']['from_status']=='new' and assign['details']['to_status']=='processing'
    assert 'من «جديدة» إلى «قيد المعالجة»' in text and not any(e['action'] in ('assess','start') for e in row['events'])


def test_numbers_are_sequential_per_year(client,setup):
    numbers=[make(client,setup)['number'] for _ in range(3)]
    year=numbers[0].split('-')[1]
    assert numbers==[f'CC-{year}-0001',f'CC-{year}-0002',f'CC-{year}-0003']


def test_line_takes_the_agreed_specification_from_the_order(client,db,setup,product):
    source=order_line(db,setup,{'thickness':40,'width':1200})
    sources=client.get(PATH+f'/sources?customer_id={setup[0].id}').json()
    assert [s['label'] for s in sources]==['RFS-2026-0007 / 2'] and sources[0]['spec']=={'thickness':'40','width':'1200'}
    row=make(client,setup,items=[line(source_kind='order',source_id=str(source.id),properties=[dict(key='thickness',reported='34',expected='ignored')])])
    item=detail(client,row)['items'][0]
    assert item['source_label']=='RFS-2026-0007 / 2' and item['source_kind']=='order'
    assert [(p['key'],p['expected'],p['reported']) for p in item['properties']]==[('thickness','40','34'),('width','1200','')]


def test_source_of_another_customer_or_product_rejected(client,db,setup,product):
    source=order_line(db,setup,{'thickness':40})
    other=Customer(organization_id=setup[2].organization_id,customer_code='CC-OTHER',name='Other customer')
    db.add(other);db.commit()
    sample=Sample(customer_id=other.id,sample_code='SMP-9',product_type='film',request_date=datetime.now(timezone.utc),created_by_user_id=setup[1].id)
    db.add(sample);db.commit()
    base=dict(customer_id=str(setup[0].id),title='T',statement='S',received_date='2026-10-11',category='quality')
    r=client.post(PATH,json={**base,'items':[line(source_kind='sample',source_id=str(sample.id))]})
    assert r.status_code==404 and r.json()['detail']=='SOURCE_NOT_FOUND'
    assert client.post(PATH,json={**base,'items':[line(source_kind='order')]}).status_code==422
    source.product_type='other';db.commit()
    r=client.post(PATH,json={**base,'items':[line(source_kind='order',source_id=str(source.id))]})
    assert r.status_code==422 and r.json()['detail']=='SOURCE_PRODUCT_MISMATCH'


def test_investigation_records_measurements_and_confirmed_quantity(client,setup,product):
    row=processing(client,setup,items=[line(properties=[dict(key='thickness',expected='40',reported='34')])])
    item=detail(client,row)['items'][0]
    finding=dict(item_id=item['id'],confirmed_quantity='80',measurements=[dict(key='thickness',measured='35')])
    bad=client.post(f"{PATH}/{row['id']}/investigate",json=dict(version=row['version'],finding='verified',investigation='Lab',
                     items=[{**finding,'confirmed_quantity':'600'}]))
    assert bad.status_code==422 and bad.json()['detail']=='CONFIRMED_EXCEEDS_DELIVERED'
    row=change(client,row,'investigate',finding='verified',investigation='Lab test',items=[finding])
    item=row['items'][0]
    assert Decimal(str(item['confirmed_quantity']))==80 and item['properties'][0]['measured']=='35'
    text=describe('investigate',row['events'][-1]['details'],'','ar')
    assert 'نتيجة التحقق: مثبتة' in text and 'السماكة: 35' in text and '80' in text


def test_items_can_be_edited_and_keep_their_measurements(client,setup,product):
    row=processing(client,setup,items=[line(properties=[dict(key='thickness',expected='40',reported='34')])])
    item=detail(client,row)['items'][0]
    row=change(client,row,'investigate',finding='pending',investigation='Lab',items=[dict(item_id=item['id'],measurements=[dict(key='thickness',measured='35')])])
    r=client.put(f"{PATH}/{row['id']}/items",json=dict(version=row['version'],items=[
        line(id=item['id'],reported_quantity='150',properties=[dict(key='thickness',expected='40',reported='33')]),
        line(properties=[dict(key='width',expected='1200',reported='1150')])]))
    assert r.status_code==200,r.text
    items=r.json()['items']
    assert [i['line_no'] for i in items]==[1,2] and items[0]['id']==item['id'] and items[0]['properties'][0]['measured']=='35'
    assert items[0]['properties'][0]['reported']=='33' and r.json()['events'][-1]['action']=='items_updated'
    r=client.put(f"{PATH}/{row['id']}/items",json=dict(version=r.json()['version'],items=[line(id=str(uuid4()))]))
    assert r.status_code==404


def test_list_query_count_does_not_grow_with_rows(client,db,setup):
    bind=db.get_bind()
    def statements():
        seen=[]
        listener=lambda *args:seen.append(1)
        sa_event.listen(bind,'before_cursor_execute',listener)
        try:
            client.get(PATH)
        finally:
            sa_event.remove(bind,'before_cursor_execute',listener)
        return len(seen)
    for _ in range(2):
        make(client,setup)
    few=statements()
    for _ in range(6):
        make(client,setup)
    assert statements()==few


def test_report_words_history_in_arabic_and_english(client,db,setup,product):
    row=ready(client,setup,items=[line(properties=[dict(key='thickness',expected='40',reported='34')])])
    from app.commercial.reporting.complaints import Params,build
    for lang,expected in (('ar',['الشحن والتسليم','إسناد المسؤولية','القياس الفعلي','من «جديدة» إلى «قيد المعالجة»']),
                          ('en',['Shipping and delivery','Responsibility assigned','Measured','From «New» to «In processing»'])):
        result=build(db,setup[2],Params(complaint_id=UUID(row['id']),lang=lang),{'register','investigation'})
        text=str([s.model_dump() for s in result.sections])
        assert all(e in text for e in expected),lang
        assert str(setup[1].id) not in text and 'shipping' not in text and 'pending_closure' not in text


def test_approved_roles_grant_the_complaint_permissions():
    from app.foundation.domain.permission_catalog import ALL_PERMISSION_CODES
    from app.foundation.domain.system_roles import SYSTEM_ROLE_BY_CODE, permission_matches, scope_for
    codes=[c for c in ALL_PERMISSION_CODES if c.startswith('commercial:complaints:')]
    def granted(role):
        patterns=SYSTEM_ROLE_BY_CODE[role]['permissions']
        return {c.rsplit(':',1)[1] for c in codes if any(permission_matches(c,p) for p in patterns)}
    assert granted('commercial_manager')=={'read','create','update','assign','investigate','resolve','close','reopen','cancel','report'}
    assert granted('sales_rep')=={'read','create','update'} and scope_for('sales_rep','commercial:complaints:read')=='own'
    assert granted('quality_manager')=={'read','investigate','resolve'}
    assert granted('viewer')=={'read'}


def test_migration_turns_combined_text_into_named_facts():
    import importlib.util
    from pathlib import Path
    path=Path(__file__).parents[2]/'alembic/versions/2026_11_08_1000_f6a1b2n2_complaint_history_and_roles.py'
    spec=importlib.util.spec_from_file_location('complaint_history_migration',path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    owner='00aca8aa-1111-2222-3333-444455556666'
    cases=[('assign',f'commercial; {owner}; 2026-10-12: Follow up'),('start','assessment → processing: Reviewed'),
           ('investigate','finding: verified\n\ninvestigation: Lab'),('linked','order: RFS-1'),('refer_quality','NCR-1: please'),
           ('attachment','photo.jpg'),('created','S'),('note','free text')]
    for action,notes in cases:
        details,rest=m._details(action,notes,'S')
        assert m._notes(action,details,rest,'S')==notes,action
    assert m._details(*cases[0],'S')==(dict(department='commercial',owner_user_id=owner,due_date='2026-10-12'),'Follow up')


def test_ncr_shows_the_complaint_it_was_opened_for(client,setup):
    row=change(client,make(client,setup),'refer-quality',notes='Lab check')
    ncr=client.get('/api/v1/quality/non-conformance-reports/'+row['links'][0]['record_id'])
    assert ncr.status_code==200,ncr.text
    assert ncr.json()['complaint_number']==row['number'] and ncr.json()['complaint_id']==row['id']
    assert ncr.json()['description'].startswith('شكوى العميل رقم '+row['number'])


def test_shorter_flow_cancel_from_new_and_removed_steps(client,setup):
    row=make(client,setup)
    for action in ('assess','start'):
        r=client.post(f"{PATH}/{row['id']}/transitions",json=dict(version=row['version'],action=action,reason='old step'))
        assert r.status_code==422
    r=client.post(f"{PATH}/{row['id']}/links",json=dict(version=row['version'],kind='sample',record_id=str(uuid4())))
    assert r.status_code==422  # a sample is a line's specification source, not a linked record
    assert 'communicate' in row['actions'] and 'note' not in row['actions'] and 'response' not in row['actions']
    row=change(client,row,'transitions',action='cancel',reason='Registered twice')
    assert row['status']=='cancelled' and row['actions']==[]
