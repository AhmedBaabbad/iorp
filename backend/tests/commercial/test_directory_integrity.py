from uuid import UUID
from tests.commercial.test_contact_directory import env, reports_env, result_env, setup  # noqa: F401
from app.commercial.infrastructure.contact_models import CustomerContact
from app.commercial.api.schemas import PrimaryContactInput
from pydantic import ValidationError
import pytest


def test_contact_phone_normalization_and_primary_contact(env):
    e=env;base=setup(e)
    response=e.client.post(base+'/contacts',json=dict(name='Contact',phone='٠٥٥ ١٢٣ ٤٥٦٧'))
    assert response.status_code==201,response.text
    assert response.json()['phone']=='+966551234567'
    bad=e.client.post(base+'/contacts',json=dict(name='Bad',phone='invalid'))
    assert bad.status_code==422 and bad.json()['detail']=='PHONE_INVALID'
    assert PrimaryContactInput(name='Primary',phone='00966551234567').phone=='+966551234567'
    with pytest.raises(ValidationError) as error:PrimaryContactInput(name='Bad',phone='invalid')
    assert error.value.errors()[0]['type']=='PHONE_INVALID'


def test_defaults_contact_preservation_invalid_phone_and_inactive_site_contact(env):
    e=env;base=setup(e)
    contact=e.client.post(base+'/contacts',json=dict(name='Chosen',phone='0551234567',is_default=True)).json()
    other=e.client.post(base+'/contacts',json=dict(name='Site contact')).json()
    site=e.client.post(base+'/sites',json=dict(name='Default site',address='Road',contact_id=other['id'],is_default=True)).json()
    root='/api/v1/shipping/shipments'
    body=dict(customer_id=str(e.customer.id),shipment_date='2026-11-21',delivery_method='factory_delivery',lines=[dict(description='Product',quantity='1',unit='kg')])
    saved=e.client.post(root,json=body)
    assert saved.status_code==201,saved.text
    assert saved.json()['delivery_site_id']==site['id'] and saved.json()['customer_contact_id']==contact['id']
    kept=e.client.patch(root+'/'+saved.json()['id'],json={'delivery_site_id':site['id']})
    assert kept.json()['customer_contact_id']==contact['id']
    row=e.db.get(CustomerContact,UUID(contact['id']));row.phone='legacy invalid';e.db.commit()
    saved=e.client.post(root,json={**body,'customer_contact_id':contact['id']})
    assert saved.status_code==201,saved.text
    assert saved.json()['consignee_phone'] is None
    e.customer.phone='invalid legacy customer';e.db.commit()
    saved=e.client.post(root,json={**body,'customer_contact_id':None,'delivery_site_id':None})
    assert saved.status_code==201 and saved.json()['consignee_phone'] is None
    row=e.db.get(CustomerContact,UUID(other['id']));row.active=False;e.db.commit()
    edited=e.client.put(base+'/sites/'+site['id'],json=dict(name='Changed',address='Updated',version=site['version'],contact_id=other['id']))
    assert edited.status_code==200,edited.text
    bad=e.client.post(base+'/sites',json=dict(name='New',address='Road',contact_id=other['id']))
    assert bad.status_code==422 and bad.json()['detail']=='CONTACT_NOT_IN_CUSTOMER'
