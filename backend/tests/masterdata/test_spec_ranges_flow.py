"""Catalogue opt-in, quotation persistence and shipment/return range propagation."""
from uuid import UUID
from decimal import Decimal

from tests.masterdata.test_master_data import md, product, STRAP  # noqa: F401
from tests.commercial.test_quotation_document import doc_env, create_quote, html  # noqa: F401
from tests.commercial.test_customer_reports import env, reports_env, result_env  # noqa: F401
from tests.shipping.test_shipments import ship  # noqa: F401
from tests.quality.test_return_inspections import env as returned_env, returned  # noqa: F401


def test_catalog_range_flag_and_quote_numeric_object(md):
    props = [{**p, 'allows_range': p['key'] == 'thickness_mm'} for p in STRAP['properties']]
    definition = product(md, properties=props)
    assert definition['properties'][1]['allows_range'] is True
    quote = create_quote(md, items=[dict(line_no=1, product_type=definition['key'], quantity='1', unit='roll', unit_price='2',
        requested_spec_json={'width_mm': 12, 'thickness_mm': {'min': .55, 'max': .6}, 'color': 'black'})])
    assert quote['items'][0]['requested_spec_json']['thickness_mm'] == {'min': .55, 'max': .6}
    for language in ('ar', 'en'):
        document = html(md, quote, language)
        assert '0.55 – 0.60' in document and 'dir="ltr"' in document
        assert ('السماكة (مم)' if language == 'ar' else 'Thickness (mm)') in document
        assert 'size:A4 landscape' in document


def test_non_numeric_property_cannot_enable_range(md):
    response = md.client.post('/api/v1/masterdata/products', json={**STRAP,
        'properties': [dict(key='color', name_ar='اللون', name_en='Color', kind='text', allows_range=True)]})
    assert response.status_code == 400 and response.json()['detail']['code'] == 'RANGE_ONLY_FOR_NUMBER'


def test_quote_free_text_interval_is_preserved_on_create_and_update(md):
    definition = product(md)
    item = dict(line_no=1, product_type=definition['key'], quantity='1', unit='roll', unit_price='2',
                requested_spec_json={'legacy': '10-20'})
    quote = create_quote(md, items=[item])
    assert quote['items'][0]['requested_spec_json'] == {'legacy': '10-20'}
    response = md.client.patch(f"/api/v1/commercial/quotes/{quote['id']}", json=dict(items=[item]))
    assert response.status_code == 200, response.text
    assert response.json()['items'][0]['requested_spec_json'] == {'legacy': '10-20'}


def test_quote_legacy_nonnumeric_template_value_can_still_be_edited(md):
    from app.commercial.infrastructure.models import Quote
    definition = product(md)
    item = dict(line_no=1, product_type=definition['key'], quantity='1', unit='roll', unit_price='2',
                requested_spec_json={'width_mm': 12})
    quote = create_quote(md, items=[item])
    # Seed a pre-existing value without relying on the current write validator.
    stored = md.db.get(Quote, UUID(quote['id']))
    stored.items[0].requested_spec_json = {'width_mm': 'legacy width'}
    md.db.commit()
    item['requested_spec_json'] = {'width_mm': 'legacy width'}
    response = md.client.patch(f"/api/v1/commercial/quotes/{quote['id']}", json=dict(items=[item]))
    assert response.status_code == 200, response.text
    assert response.json()['items'][0]['requested_spec_json'] == {'width_mm': 'legacy width'}
    # Creation retains the same historical scalar contract as modification.
    assert create_quote(md, items=[item])['items'][0]['requested_spec_json'] == {'width_mm': 'legacy width'}


def test_range_survives_quote_sales_order_demand_and_planning(md):
    from app.commercial.infrastructure.models import Quote, CommercialOrder
    from app.commercial.domain.enums import QuoteStatus, CommercialOrderStatus
    from app.production.infrastructure.models import WorkCenter
    props = [{**p, 'allows_range': p['key'] == 'thickness_mm'} for p in STRAP['properties']]
    definition = product(md, properties=props)
    value = {'min': .55, 'max': .6}
    quote = create_quote(md, items=[dict(line_no=1, product_type=definition['key'], quantity='10', unit='roll', unit_price='2',
        requested_spec_json={'width_mm': 12, 'thickness_mm': value})])
    # Approval behavior is tested separately; establish accepted/confirmed source
    # preconditions here so this test follows the actual specification-copy APIs.
    md.db.get(Quote, UUID(quote['id'])).status = QuoteStatus.ACCEPTED
    md.db.commit()
    md.ctx.user.is_organization_root = True
    order = md.client.post(f"/api/v1/commercial/quotes/{quote['id']}/sales-order", json={})
    assert order.status_code == 201, order.text
    order = order.json()
    assert order['items'][0]['requested_spec_json']['thickness_mm'] == value
    md.db.get(CommercialOrder, UUID(order['id'])).status = CommercialOrderStatus.CONFIRMED
    center = WorkCenter(organization_id=md.org.id, code='WC-RANGE', name='Synthetic range line')
    md.db.add(center); md.db.commit()
    demand = md.client.post('/api/v1/production/demands/from-sales-order', json=dict(
        sales_order_id=order['id'], lines=[dict(order_item_id=order['items'][0]['id'], quantity='10')]))
    assert demand.status_code == 201, demand.text
    demand = demand.json()
    demand = md.client.get(f"/api/v1/production/demands/{demand['id']}").json()
    assert demand['items'][0]['target_spec_json']['thickness_mm'] == value
    if demand['status'] == 'draft':
        ready = md.client.post(f"/api/v1/production/demands/{demand['id']}/status", json=dict(status='ready_for_planning'))
        assert ready.status_code == 200, ready.text
    plan = md.client.post('/api/v1/production/planning/create-production-order', json=dict(
        allocations=[dict(production_demand_item_id=demand['items'][0]['id'], allocated_quantity='10')],
        work_center_id=str(center.id), planned_start_date='2026-10-01', planned_end_date='2026-10-02'))
    assert plan.status_code == 201, plan.text
    assert plan.json()['lines'][0]['target_spec_json']['thickness_mm'] == value


def test_shipping_return_range_reaches_quality_as_an_object(returned_env):
    e = returned_env
    create = e.create
    def ranged_create(**overrides):
        for line in overrides['lines']:
            line.update(thickness_mm='.55', thickness_max_mm='.60')
        return create(**overrides)
    e.create = ranged_create
    note, ret = returned(e)
    assert ret['lines'][0]['thickness_max_mm'] == '0.600'
    response = e.client.post(f"/api/v1/quality/returns/lines/{ret['lines'][0]['id']}/inspection", json={})
    assert response.status_code == 201, response.text
    assert response.json()['lot_values']['thickness_mm'] == {'min': .55, 'max': .6}


def test_shipment_range_is_copied_to_return_and_delivery_pdf(ship):
    from app.shipping.infrastructure.models import Shipment, ShipmentReturnLine
    from app.shipping.application.return_service import ReturnService
    from app.shipping.domain import returns as R
    from sqlalchemy import select
    response = ship.client.post('/api/v1/shipping/shipments', json=ship.body(lines=[dict(
        description='Synthetic band', width_mm='12', thickness_mm='.55', thickness_max_mm='.60',
        quantity='10', unit='roll', unit_net_weight='1', weight_unit='kg')]))
    assert response.status_code == 201, response.text
    row = ship.db.get(Shipment, UUID(response.json()['id']))
    assert row.lines[0].thickness_max_mm == Decimal('.60')
    service = ReturnService(ship.db, ship.ctx.tenant)
    ret = service._new(row, R.CUSTOMER, R.REQUESTED, 'quality_defect', 'Synthetic test', [(row.lines[0], Decimal(1))])
    ship.db.flush()
    line = ship.db.scalar(select(ShipmentReturnLine).where(ShipmentReturnLine.return_id == ret.id))
    assert line.thickness_mm == Decimal('.55') and line.thickness_max_mm == Decimal('.60')
