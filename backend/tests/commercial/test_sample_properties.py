"""Master Data is the only sample property schema. Tests use arbitrary products, never Commercial-specific fields."""
from datetime import datetime, timezone
from uuid import UUID, uuid4
from types import SimpleNamespace
import pytest
from sqlalchemy import select, func
from app.commercial.infrastructure.models import Customer, Sample
from app.masterdata.infrastructure.models import Product, ProductProperty
from app.foundation.infrastructure.models import Organization

BASE='/api/v1/commercial'


@pytest.fixture
def catalog(db,test_org,test_user,auth_headers,client):
    customer=Customer(organization_id=test_org.id,customer_code='SPEC-C',name='Specification customer',sales_owner_user_id=test_user.id)
    product=Product(organization_id=test_org.id,code='PRD-TEST',key='generic_product',name_ar='منتج تجريبي',name_en='Test product',created_by_user_id=test_user.id)
    product.properties=[
        ProductProperty(line_no=1,key='dimension',name_ar='المقاس',name_en='Dimension',kind='number',unit='mm',required=True),
        ProductProperty(line_no=2,key='finish',name_ar='التشطيب',name_en='Finish',kind='choice',options=[dict(value='smooth',label_ar='ناعم',label_en='Smooth')]),
        ProductProperty(line_no=3,key='description',name_ar='الوصف',name_en='Description',kind='text'),
    ]
    db.add_all([customer,product]);db.commit()
    return SimpleNamespace(db=db,org=test_org,user=test_user,customer=customer,product=product,headers=auth_headers,client=client)


def create(e,values=None,**over):
    return e.client.post(f'{BASE}/customers/{e.customer.id}/samples',headers=e.headers,json=dict(
        product_type=e.product.key,request_date='2026-10-06T10:00:00Z',property_values=values if values is not None else {'dimension':12.5},**over))


def test_create_typed_values_template_and_edit_roundtrip(catalog):
    e=catalog;r=create(e,{'dimension':12.5,'finish':'smooth','description':'Trial'})
    assert r.status_code==201,r.text
    saved=r.json()
    assert saved['property_values']=={'dimension':12.5,'finish':'smooth','description':'Trial'}
    assert saved['requested_spec_json']==saved['property_values'] # compatibility view, not a second store
    assert saved['product_definition']['properties'][0]['required'] is True
    row=e.db.get(Sample,UUID(saved['id']));assert row.requested_spec_json['dimension']==12.5
    r=e.client.patch(f"{BASE}/samples/{row.id}",headers=e.headers,json={'property_values':{'dimension':20,'finish':'smooth'}})
    assert r.status_code==200 and r.json()['property_values']['dimension']==20
    read=e.client.get(f'{BASE}/samples/{row.id}',headers=e.headers)
    assert read.json()['property_values']=={'dimension':20,'finish':'smooth'}


@pytest.mark.parametrize('values,code',[
    ({},'SAMPLE_PROPERTY_REQUIRED'),({'dimension':None},'SAMPLE_PROPERTY_REQUIRED'),
    ({'dimension':'12 mm'},'SAMPLE_PROPERTY_NUMBER'),({'dimension':True},'SAMPLE_PROPERTY_NUMBER'),
    ({'dimension':[]},'SAMPLE_PROPERTY_NUMBER'),({'dimension':12,'description':{}},'SAMPLE_PROPERTY_TEXT'),
    ({'dimension':12,'finish':'unknown'},'SAMPLE_PROPERTY_CHOICE'),
    ({'dimension':12,'other_product_property':1},'SAMPLE_PROPERTY_UNKNOWN'),
])
def test_invalid_values_rejected_without_persisting(catalog,values,code):
    r=create(catalog,values)
    assert r.status_code==422 and r.json()['detail']['code']==code,r.text
    assert catalog.db.scalar(select(func.count()).select_from(Sample))==0


def test_unknown_foreign_inactive_products_and_options(catalog):
    e=catalog
    other=Organization(name='Other',code='OTHER-SPEC',timezone='UTC');e.db.add(other);e.db.flush()
    foreign=Product(organization_id=other.id,code='PRD-X',key='foreign_product',name_ar='آخر',name_en='Foreign',created_by_user_id=e.user.id)
    e.db.add(foreign);e.db.commit()
    for key in ['missing','foreign_product']:
        r=e.client.post(f'{BASE}/customers/{e.customer.id}/samples',headers=e.headers,json=dict(product_type=key,request_date='2026-10-06T10:00:00Z',property_values={}))
        assert r.status_code==422 and r.json()['detail']['code']=='SAMPLE_PRODUCT_NOT_FOUND'
    options=e.client.get(f'{BASE}/samples/product-options',headers=e.headers)
    assert options.status_code==200 and [p['key'] for p in options.json()]==[e.product.key]
    e.product.active=False;e.db.commit()
    assert create(e).json()['detail']['code']=='SAMPLE_PRODUCT_INACTIVE'
    assert e.client.get(f'{BASE}/samples/product-options',headers=e.headers).json()==[]


def test_legacy_unmapped_sample_can_be_read_and_notes_updated(catalog):
    e=catalog;old={'free form':{'nested':['old',12]},'historical':True}
    sample=Sample(customer_id=e.customer.id,sample_code='OLD-1',product_type='Old product name',requested_spec_json=old,
        request_date=datetime.now(timezone.utc),created_by_user_id=e.user.id)
    e.db.add(sample);e.db.commit()
    r=e.client.patch(f'{BASE}/samples/{sample.id}',headers=e.headers,json={'notes':'Keep specifications'})
    assert r.status_code==200 and r.json()['property_values']==old and r.json()['product_definition'] is None
    r=e.client.patch(f'{BASE}/samples/{sample.id}',headers=e.headers,json={'product_type':'Old product name','requested_spec_json':old})
    assert r.status_code==200 and r.json()['requested_spec_json']==old
    r=e.client.patch(f'{BASE}/samples/{sample.id}',headers=e.headers,json={'property_values':{'invented':42}})
    assert r.status_code==422
    e.db.refresh(sample);assert sample.requested_spec_json==old


def test_retired_property_preserved_but_cannot_be_changed(catalog):
    e=catalog
    sample=Sample(customer_id=e.customer.id,sample_code='OLD-2',product_type=e.product.key,
        requested_spec_json={'dimension':8,'retired_property':'old'},request_date=datetime.now(timezone.utc),created_by_user_id=e.user.id)
    e.db.add(sample);e.db.commit()
    r=e.client.patch(f'{BASE}/samples/{sample.id}',headers=e.headers,json={'property_values':{'dimension':9,'retired_property':'old'}})
    assert r.status_code==200 and r.json()['property_values']['retired_property']=='old'
    r=e.client.patch(f'{BASE}/samples/{sample.id}',headers=e.headers,json={'property_values':{'dimension':10}})
    assert r.status_code==200 and r.json()['property_values']=={'dimension':10,'retired_property':'old'}
    r=e.client.patch(f'{BASE}/samples/{sample.id}',headers=e.headers,json={'property_values':{'dimension':9,'retired_property':'changed'}})
    assert r.status_code==422


def test_old_payload_alias_validated_and_ambiguous_payload_rejected(catalog):
    e=catalog
    body=dict(product_type=e.product.key,request_date='2026-10-06T10:00:00Z',requested_spec_json={'dimension':'bad'})
    r=e.client.post(f'{BASE}/customers/{e.customer.id}/samples',headers=e.headers,json=body)
    assert r.status_code==422
    body['requested_spec_json']={'dimension':12}
    assert e.client.post(f'{BASE}/customers/{e.customer.id}/samples',headers=e.headers,json=body).status_code==201
    body['property_values']={'dimension':12}
    assert e.client.post(f'{BASE}/customers/{e.customer.id}/samples',headers=e.headers,json=body).status_code==422


def test_definition_changes_are_loaded_from_master_data(catalog):
    e=catalog
    e.product.properties.append(ProductProperty(line_no=4,key='arbitrary_field',name_ar='خاصية إضافية',name_en='Additional property',kind='text',required=True))
    e.db.commit()
    assert create(e).json()['detail']['property_key']=='arbitrary_field'
    r=create(e,{'dimension':0,'arbitrary_field':'text'})
    assert r.status_code==201 and r.json()['product_definition']['properties'][-1]['key']=='arbitrary_field'


def test_empty_catalog_is_not_free_text_creation(catalog):
    e=catalog;e.db.delete(e.product);e.db.commit()
    assert create(e).status_code==422
    assert e.client.get(f'{BASE}/samples/product-options').status_code==401


def test_boolean_cannot_bypass_numeric_validation_on_update(catalog):
    e=catalog
    saved=create(e,{'dimension':1}).json()
    r=e.client.patch(f"{BASE}/samples/{saved['id']}",headers=e.headers,json={'property_values':{'dimension':True}})
    assert r.status_code==422 and r.json()['detail']['code']=='SAMPLE_PROPERTY_NUMBER'
    e.db.expire_all()
    assert e.db.get(Sample,UUID(saved['id'])).requested_spec_json=={'dimension':1}
