from dataclasses import replace
from uuid import uuid4,UUID
from sqlalchemy import select
from tests.commercial.test_customer_reports import env,reports_env,result_env
from app.commercial.infrastructure.models import Customer
from app.commercial.infrastructure.contact_models import CustomerContact

def setup(e):
    e.ctx.auth_user.permissions.update({'commercial:customers:update','shipping:shipments:create','shipping:shipments:update'})
    return f'/api/v1/commercial/customers/{e.customer.id}/directory'

def test_customer_contacts_defaults_and_scoping(env):
    e=env;base=setup(e)
    first=e.client.post(base+'/contacts',json=dict(name='First',is_default=True))
    assert first.status_code==201,first.text
    second=e.client.post(base+'/contacts',json=dict(name='Second',is_default=True)).json()
    old=e.db.get(CustomerContact,UUID(first.json()['id']))
    assert old.is_default is False and old.version==2
    assert e.client.put(base+'/contacts/'+str(old.id),json=dict(name='Stale',version=1)).status_code==409
    assert e.client.post(base+'/sites',json=dict(name='Factory',address='Industrial area',contact_id=second['id'])).status_code==201
    foreign=Customer(organization_id=e.org.id,customer_code='SECOND',name='Other',sales_owner_user_id=e.user.id)
    e.db.add(foreign);e.db.commit()
    assert e.client.post(f'/api/v1/commercial/customers/{foreign.id}/directory/sites',json=dict(name='Invalid',address='A',contact_id=second['id'])).status_code==422
    assert e.client.get(f'/api/v1/commercial/customers/{uuid4()}/directory/contacts').status_code==404
    assert e.client.post(base+'/contacts',json=dict(name='Scope injection',organization_id=str(uuid4()))).status_code==422
    e.ctx.auth_user.permissions.discard('commercial:customers:update')
    assert e.client.post(base+'/contacts',json=dict(name='Unauthorized')).status_code==403

def test_shipping_copies_customer_site_and_contact_without_live_refresh(env):
    e=env;base=setup(e)
    contact=e.client.post(base+'/contacts',json=dict(name='Receiver',phone='0551234567')).json()
    site=e.client.post(base+'/sites',json=dict(name='Factory',address='Original address',contact_id=contact['id'])).json()
    body=dict(customer_id=str(e.customer.id),delivery_site_id=site['id'],shipment_date='2026-10-13',delivery_method='factory_delivery',lines=[dict(description='Product',quantity='1',unit='kg')])
    response=e.client.post('/api/v1/shipping/shipments',json=body)
    assert response.status_code==201,response.text
    shipment=response.json()
    assert shipment['delivery_address']=='Original address' and shipment['consignee_name']=='Receiver'
    assert shipment['customer_contact_id']==contact['id']
    manual=e.client.post('/api/v1/shipping/shipments',json={**body,'customer_contact_id':None,'consignee_name':'Manual receiver'})
    assert manual.status_code==201,manual.text
    assert manual.json()['customer_contact_id'] is None and manual.json()['consignee_name']=='Manual receiver'
    assert e.client.put(base+'/sites/'+site['id'],json=dict(name='Factory',address='Changed',version=1)).status_code==200
    response=e.client.patch('/api/v1/shipping/shipments/'+shipment['id'],json=dict(notes='Keep address',delivery_address='Forged'))
    assert response.status_code==200,response.text
    assert response.json()['delivery_address']=='Original address'
    assert e.client.patch('/api/v1/shipping/shipments/'+shipment['id'],json=dict(delivery_site_id=str(uuid4()))).status_code==422

def test_update_scope_does_not_inherit_broader_read_scope(env):
    e=env;base=setup(e)
    e.customer.sales_owner_user_id=uuid4();e.db.commit()
    e.ctx.tenant=replace(e.ctx.tenant,is_organization_root=False)
    # With no persisted organization-wide update grant, the scope resolver fails closed to own.
    assert e.client.post(base+'/contacts',json=dict(name='Not my customer')).status_code==404


def test_site_other_city_and_country_are_snapshotted_and_https_is_enforced(env):
    e=env;base=setup(e)
    response=e.client.post(base+'/sites',json=dict(name='Synthetic site',address='Road 1',country='ae',
        city='ae_other',city_other='New city',location_url='https://maps.example.test/site'))
    assert response.status_code==201,response.text
    site=response.json()
    body=dict(customer_id=str(e.customer.id),delivery_site_id=site['id'],shipment_date='2026-10-13',
        delivery_method='factory_delivery',lines=[dict(description='Product',quantity='1',unit='kg')])
    response=e.client.post('/api/v1/shipping/shipments',json=body)
    assert response.status_code==201,response.text
    assert response.json()['delivery_city']=='New city' and response.json()['delivery_country']=='ae'
    assert response.json()['location_url']=='https://maps.example.test/site'
    selected=e.client.get(base+'/sites').json()[0]
    assert selected['city_other']=='New city'
    for url in ('javascript:alert(1)','http://maps.example.test','data:text/html,unsafe'):
        bad=e.client.post(base+'/sites',json=dict(name='Unsafe',address='Road',location_url=url))
        assert bad.status_code==422 and bad.json()['detail']=='LOCATION_URL_INVALID'
        bad=e.client.patch('/api/v1/shipping/shipments/'+response.json()['id'],json=dict(location_url=url))
        assert bad.status_code==422 and bad.json()['detail'][0]['type']=='LOCATION_URL_INVALID'
    bad=e.client.post(base+'/sites',json=dict(name='Missing city',address='Road',country='ae',city='ae_other'))
    assert bad.status_code==422 and bad.json()['detail']=='CITY_OTHER_REQUIRED'
    # A pre-existing unsafe link must not bypass shipment validation via selection.
    from app.commercial.infrastructure.contact_models import CustomerSite
    stored=e.db.get(CustomerSite,UUID(site['id']))
    stored.location_url='javascript:alert(1)';e.db.commit()
    rejected=e.client.post('/api/v1/shipping/shipments',json=body)
    assert rejected.status_code==422 and rejected.json()['detail']['code']=='LOCATION_URL_INVALID'
    changed=e.client.put(base+'/sites/'+site['id'],json=dict(name='Site',address='Road',country='sa',city='riyadh',city_other='Discard',version=1))
    assert changed.status_code==200 and changed.json()['city_other'] is None


def test_default_contact_and_other_city_are_used_in_reports_and_shipping(env):
    from tests.commercial.test_customer_reports import preview
    from app.shipping.application.support import CustomerReads
    e=env;base=setup(e)
    e.customer.phone='5551111';e.customer.email='retired@example.test'
    e.customer.country='ae';e.customer.city='ae_other';e.customer.city_other='Synthetic new city'
    e.db.commit()
    contact=e.client.post(base+'/contacts',json=dict(name='Current',phone='5552222',email='current@example.com',is_default=True))
    assert contact.status_code==201,contact.text
    read=CustomerReads(e.db,e.org.id).get(e.customer.id)
    assert read['phone']=='5552222' and read['email']=='current@example.com' and read['city']=='Synthetic new city'
    e.db.expire_all()
    response=preview(e,sections=['information','contacts'],lang='en')
    assert response.status_code==200,response.text
    assert '5552222' in response.text and 'current@example.com' in response.text and 'Synthetic new city' in response.text
    assert 'retired@example.test' not in response.text
