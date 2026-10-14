from uuid import uuid4
from tests.procurement.test_procurement import proc,ROOT
from tests.procurement.test_purchase_orders import order,ORDERS

def test_supplier_contact_selection_preserves_attention_and_checks_supplier(proc):
    e=proc;supplier=e.supplier();material=e.material()
    base=f"{ROOT}/suppliers/{supplier['id']}/contacts"
    response=e.client.post(base,json=dict(name='Original contact',email='contact@example.com'))
    assert response.status_code==201,response.text
    contact=response.json()
    purchase=order(e,supplier,material,supplier_contact_id=contact['id'])
    assert purchase['attention']=='Original contact'
    assert e.client.put(base+'/'+contact['id'],json=dict(name='Renamed',version=1)).status_code==200
    response=e.client.patch(f"{ORDERS}/{purchase['id']}",json=dict(notes='Keep snapshot',attention='Forged'))
    assert response.status_code==200,response.text
    assert response.json()['attention']=='Original contact'
    other=e.supplier(name='Other supplier')
    response=e.client.post(ORDERS,json=dict(supplier_id=other['id'],supplier_contact_id=contact['id'],order_date='2026-10-13',lines=[dict(description='Product',quantity='1',unit='kg',unit_price='1')]))
    assert response.status_code==422,response.text
    assert e.client.get(f'{ROOT}/suppliers/{uuid4()}/contacts').status_code==404
