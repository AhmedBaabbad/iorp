"""Delivery note totals: semantic rows, value columns and isolated numeric weight parts."""
import re

import pytest
from tests.shipping.test_shipments import ship  # noqa: F401


def sample_note(ship, gross=True):
    return ship.create(customer_name='Synthetic Customer', consignee_name='Synthetic receiving team',
        driver_name='Synthetic Driver', driver_affiliation='external', vehicle_plate='TEST 1234', delivery_address='Synthetic destination',
        gross_weight='3500' if gross else None,
        lines=[dict(description='Synthetic band A', width_mm='12', thickness_mm='.55', thickness_max_mm='.60',
                    quantity='200', unit='roll', unit_net_weight='9', weight_unit='kg'),
               dict(description='Synthetic band B', width_mm='15', thickness_mm='.55', thickness_max_mm='.60',
                    quantity='150', unit='roll', unit_net_weight='10', weight_unit='kg')])


@pytest.mark.parametrize('lang', ['ar', 'en'])
@pytest.mark.parametrize('gross', [True, False])
def test_footer_rows_mean_values_and_columns(ship, lang, gross):
    note = sample_note(ship, gross)
    response = ship.client.post('/api/v1/reports/shipping.delivery_note/preview', json=dict(shipment_id=note['id'], lang=lang))
    assert response.status_code == 200, response.text
    footer = re.search(r'<tfoot>(.*?)</tfoot>', response.text, re.S)[1]
    rows = re.findall(r'<tr\b([^>]*)>(.*?)</tr>', footer, re.S)
    kinds = [re.search(r'data-total="([^"]+)"', attrs)[1] for attrs, _ in rows]
    assert kinds == (['quantity', 'net', 'packaging', 'gross'] if gross else ['quantity', 'net'])
    labels = ['إجمالي الكمية', 'الصافي الكلي', 'التغليف والبقية', 'الوزن الإجمالي'] if lang == 'ar' else [
        'Total quantity', 'Total net weight', 'Packaging and remainder', 'Gross weight']
    expected = ['350 ' + ('لفة' if lang == 'ar' else 'roll'), '3300', '200', '3500']
    for (_, row), label, value in zip(rows, labels, expected):
        assert label in row and value in row
    # Quantity belongs to columns 5+6; weights belong to the final (line-net) column.
    assert re.findall(r'colspan="(\d+)"', rows[0][1]) == ['4', '2', '2']
    assert all(re.findall(r'colspan="(\d+)"', row) == ['7'] for _, row in rows[1:])
    unit = 'كجم' if lang == 'ar' else 'kg'
    for value in ('9', '10', '1800', '1500', '3300', *(['200', '3500'] if gross else [])):
        assert f'<bdi dir="ltr">{value}</bdi><span>&nbsp;{unit}</span>' in response.text
    assert not re.search(r'<bdi[^>]*>[^<]*' + unit + r'[^<]*</bdi>', response.text)
