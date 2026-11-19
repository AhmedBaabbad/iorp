"""Per-unit net, shipment gross, legacy drafts and proportional return weights."""
from decimal import Decimal
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, func
from app.shipping.domain import rules, returns as R
from app.shipping.infrastructure.models import Shipment
from app.shipping.application.return_service import ReturnService
from tests.shipping.test_shipments import ship, ROOT, go  # noqa: F401


def line(quantity='100', unit_weight='9', **extra):
    return dict(description='Synthetic strapping band', quantity=quantity, unit='roll', unit_net_weight=unit_weight, weight_unit='kg', **extra)


@pytest.mark.parametrize('items,expected', [([line()], '900.000'), ([line(), line('50', '12')], '1500.000')])
def test_net_weight_is_computed_on_the_server(ship, items, expected):
    request = ship.body(customer_id=None, customer_name='Synthetic Customer', lines=items, gross_weight='1.6', gross_weight_unit='ton')
    response = ship.client.post(ROOT, json=request)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved['weight_total_kg'] == expected
    assert saved['lines'][0]['weight'] == '900.000'
    assert saved['lines'][0]['unit_net_weight'] == '9.000'
    assert saved['gross_weight_kg'] == '1600.000'
    assert saved['packaging_weight_kg'] == ('100.000' if len(items) == 2 else '700.000')
    if len(items) == 2 and os.getenv('SHIPMENT_WEIGHT_EXAMPLE'):
        out = Path(os.environ['SHIPMENT_WEIGHT_EXAMPLE'])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(dict(method='POST', path=ROOT, request=request, status=response.status_code,
                                      response=saved), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    # A client cannot override the computed net with a submitted total.
    assert ship.client.post(ROOT, json=ship.body(lines=[{**line(), 'weight': '1'}])).status_code == 422


def test_weight_quantity_uses_kilograms_and_forbids_unit_weight(ship):
    for unit, quantity, expected in [('kg', '500', '500.000'), ('ton', '2', '2000.000'), ('g', '5000', '5.000')]:
        item = dict(description='Synthetic weighed goods', quantity=quantity, unit=unit)
        saved = ship.create(lines=[item])
        assert saved['lines'][0]['weight'] == saved['weight_total_kg'] == expected
        assert saved['lines'][0]['unit_net_weight'] is None and saved['lines'][0]['weight_unit'] == 'kg'
        for value in ('9', None):
            result = ship.client.post(ROOT, json=ship.body(lines=[{**item, 'unit_net_weight': value}]))
            assert result.status_code == 400 and result.json()['detail']['code'] == 'UNIT_NET_WEIGHT_NOT_ALLOWED'


def test_grams_tons_packaging_and_gross_validation_are_atomic(ship):
    item = {**line(), 'unit_net_weight': '9000', 'weight_unit': 'g'}
    saved = ship.create(lines=[item], gross_weight='1', gross_weight_unit='ton')
    assert saved['lines'][0]['weight'] == '900000.000'
    assert saved['weight_total_kg'] == '900.000' and saved['packaging_weight_kg'] == '100.000'
    count = ship.db.scalar(select(func.count()).select_from(Shipment))
    result = ship.client.post(ROOT, json=ship.body(lines=[item], gross_weight='800'))
    assert result.status_code == 400 and result.json()['detail']['code'] == 'GROSS_BELOW_NET'
    assert ship.db.scalar(select(func.count()).select_from(Shipment)) == count
    result = ship.client.patch(f"{ROOT}/{saved['id']}", json=dict(gross_weight='800'))
    assert result.status_code == 400 and result.json()['detail']['code'] == 'GROSS_BELOW_NET'
    assert ship.client.get(f"{ROOT}/{saved['id']}").json()['gross_weight_kg'] == '1000.000'
    result = ship.client.patch(f"{ROOT}/{saved['id']}", json=dict(lines=[line('100', '12')]))
    assert result.status_code == 400 and result.json()['detail']['code'] == 'GROSS_BELOW_NET'
    assert ship.client.get(f"{ROOT}/{saved['id']}").json()['weight_total_kg'] == '900.000'
    cleared = ship.client.patch(f"{ROOT}/{saved['id']}", json=dict(gross_weight=None)).json()
    assert cleared['gross_weight_kg'] is None and cleared['packaging_weight_kg'] is None


def test_weight_matching_never_falls_back_to_net():
    d = Decimal
    assert rules.weight_check(d('1000'), d('1100'), d('1090'), d('1'))['reference_kg'] == d('1100')
    assert rules.weight_check(d('1000'), None, d('990'), d('1'))['reference_kg'] == d('1000')
    assert rules.weight_check(None, None, d('900'), d('1')) is None


def test_line_rounding_matches_the_stored_three_decimal_precision():
    from app.shipping.api.schemas import LineInput
    for quantity, expected in [('1.001', '.500'), ('1.003', '.502')]:
        data = LineInput(**line(quantity, '.5'))
        assert rules.line_weight(data)[0] == Decimal(expected)


@pytest.mark.parametrize('gross,gate,reference', [(None, None, None), ('1000', None, '1000.000'), ('1000', '1100', '1100.000')])
def test_delivery_matching_uses_only_gate_or_gross(ship, gross, gate, reference):
    saved = ship.create(lines=[line()], gross_weight=gross, driver_name='Synthetic Driver',
                        driver_affiliation='external', vehicle_plate='TEST')
    assert go(ship, saved, 'ready').status_code == 200
    assert go(ship, saved, 'dispatch', gate_weight=gate).status_code == 200
    delivered = go(ship, saved, 'deliver', received_by_name='Synthetic Receiver', received_weight='990')
    assert delivered.status_code == 200, delivered.text
    check = delivered.json()['weight_check']
    assert (check['reference_kg'] if check else None) == reference


def test_legacy_weight_is_read_printed_and_preserved_on_draft_save(ship):
    from app.shipping.reporting.document import build, DeliveryNoteParams
    saved = ship.create(lines=[line()])
    stored = ship.db.get(Shipment, UUID(saved['id']))
    stored.lines[0].unit_net_weight = None
    stored.lines[0].weight = Decimal('877')
    ship.db.commit()
    read = ship.client.get(f"{ROOT}/{saved['id']}").json()
    assert read['lines'][0]['unit_net_weight'] is None and read['weight_total_kg'] == '877.000'
    document = build(ship.db, ship.ctx.tenant, DeliveryNoteParams(shipment_id=stored.id, lang='en'), []).document
    assert document['lines'][0]['weight'] == '877 kg' and document['lines'][0]['unit_net_weight'] == '—'
    item = {**line(), 'id': read['lines'][0]['id'], 'unit_net_weight': None}
    updated = ship.client.patch(f"{ROOT}/{saved['id']}", json=dict(notes='Synthetic edit', lines=[item]))
    assert updated.status_code == 200, updated.text
    assert updated.json()['weight_total_kg'] == '877.000'
    item.update(id=updated.json()['lines'][0]['id'], unit_net_weight='9')
    assert ship.client.patch(f"{ROOT}/{saved['id']}", json=dict(lines=[item])).json()['weight_total_kg'] == '900.000'


def test_return_share_uses_full_new_line_net_not_unit_weight(ship):
    saved = ship.create(lines=[line()])
    shipment = ship.db.get(Shipment, UUID(saved['id']))
    ret = ReturnService(ship.db, ship.ctx.tenant)._new(shipment, R.CUSTOMER, R.REQUESTED, 'quality_defect', None,
                                                   [(shipment.lines[0], Decimal('20'))])
    assert ret.lines[0].weight == Decimal('180')
    assert ret.lines[0].weight_unit == 'kg'


@pytest.mark.parametrize('quantity,unit,expected', [('50', 'roll', '450.000'), ('100', 'piece', '900.000')])
def test_changed_legacy_quantity_or_unit_requires_a_new_unit_net_weight(ship, quantity, unit, expected):
    saved = ship.create(lines=[line()])  # 100 rolls, full net 900 kg
    stored = ship.db.get(Shipment, UUID(saved['id']))
    stored.lines[0].unit_net_weight = None
    ship.db.commit()
    item = {**line(quantity), 'id': saved['lines'][0]['id'], 'unit': unit, 'unit_net_weight': None}
    result = ship.client.patch(f"{ROOT}/{saved['id']}", json=dict(lines=[item]))
    assert result.status_code == 400 and result.json()['detail']['code'] == 'UNIT_NET_WEIGHT_REQUIRED'
    assert ship.client.get(f"{ROOT}/{saved['id']}").json()['weight_total_kg'] == '900.000'
    item['unit_net_weight'] = '9'
    result = ship.client.patch(f"{ROOT}/{saved['id']}", json=dict(lines=[item]))
    assert result.status_code == 200, result.text
    assert result.json()['lines'][0]['weight'] == result.json()['weight_total_kg'] == expected


def test_legacy_weighed_quantity_is_not_recalculated_by_an_unchanged_draft_save(ship):
    saved = ship.create(lines=[dict(description='Synthetic legacy goods', quantity='100', unit='kg')])
    stored = ship.db.get(Shipment, UUID(saved['id']))
    stored.lines[0].weight = Decimal('877')
    ship.db.commit()
    item = dict(id=saved['lines'][0]['id'], description='Synthetic legacy goods', quantity='100', unit='kg')
    result = ship.client.patch(f"{ROOT}/{saved['id']}", json=dict(lines=[item]))
    assert result.status_code == 200, result.text
    assert result.json()['weight_total_kg'] == '877.000'


def test_line_ids_are_scoped_to_the_existing_shipment(ship):
    saved = ship.create(lines=[line()])
    result = ship.client.patch(f"{ROOT}/{saved['id']}", json=dict(lines=[{**line(), 'id': str(uuid4())}]))
    assert result.status_code == 400 and result.json()['detail']['code'] == 'LINE_NOT_FOUND'
