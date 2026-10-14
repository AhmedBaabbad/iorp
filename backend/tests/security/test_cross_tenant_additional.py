"""Permanent regressions for the three independent-review scenarios."""
from datetime import date
from uuid import uuid4

import pytest
from tests.security.test_cross_tenant_sweep import world
from tests.test_tenant_isolation import isolated_tenants


@pytest.mark.parametrize('path,parameter,key', [
    ('/procurement/purchase-orders', 'supplier_id', 'supplier_id'),
    ('/procurement/purchase-orders/open-for-receipt', 'supplier_id', 'supplier_id'),
    ('/shipping/shipments', 'customer_id', 'customer_id'),
    ('/shipping/returns', 'shipment_id', 'shipment_id'),
])
def test_foreign_query_references_return_empty_lists(world, path, parameter, key):
    response = world['client'].get('/api/v1' + path, headers=world['a'], params={parameter: world['ids'][key]})
    assert response.status_code == 200
    body = response.json()
    assert (body if isinstance(body, list) else body['items']) == []


@pytest.mark.parametrize('reference', ['supplier', 'material'])
def test_patch_own_order_rejects_foreign_references_without_mutation(world, reference):
    client, headers = world['client'], world['a']
    supplier = client.post('/api/v1/procurement/suppliers', headers=headers, json={'name': 'A supplier'})
    assert supplier.status_code == 201
    created = client.post('/api/v1/procurement/purchase-orders', headers=headers, json={
        'supplier_id': supplier.json()['id'], 'order_date': str(date.today()), 'currency': 'SAR',
        'lines': [{'description': 'Own item', 'quantity': '1', 'unit': 'kg', 'unit_price': '5'}]})
    assert created.status_code == 201
    url = '/api/v1/procurement/purchase-orders/' + created.json()['id']
    before = client.get(url, headers=headers).json()
    payload = {'supplier_id': world['ids']['supplier_id']} if reference == 'supplier' else {
        'lines': [{'material_id': world['ids']['material_id'], 'quantity': '1', 'unit': 'kg', 'unit_price': '5'}]}
    rejected = client.patch(url, headers=headers, json=payload)
    assert rejected.status_code == 404
    assert client.get(url, headers=headers).json() == before


@pytest.mark.parametrize('format', ['preview', 'pdf'])
def test_report_body_foreign_document_is_indistinguishable_from_missing(world, format):
    url = '/api/v1/reports/procurement.purchase_order/' + format
    foreign = world['client'].post(url, headers=world['a'], json={'order_id': world['ids']['order_id']})
    missing = world['client'].post(url, headers=world['a'], json={'order_id': str(uuid4())})
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()
