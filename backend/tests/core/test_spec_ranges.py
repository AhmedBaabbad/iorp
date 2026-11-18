from decimal import Decimal
from types import SimpleNamespace as NS

import pytest

from app.core.specifications import normalize_numeric, format_spec_value, SpecificationValueError
from app.core.interfaces.product_catalog import ProductInfo, PropertyInfo, ProductSpecificationError
from app.core.interfaces.specification_columns import specification_columns
from app.masterdata.domain.rules import assert_property_values, assert_template, MasterDataError
from app.masterdata.api.schemas import PropertyInput
from app.production.domain.arrangement import arrange
from app.quality.domain.specifications import resolve_limits, evaluate


@pytest.mark.parametrize('value,allowed,code', [
    ({'min': 0.55, 'max': 0.6}, False, 'SPEC_RANGE_NOT_ALLOWED'),
    ({'min': 0.6, 'max': 0.55}, True, 'SPEC_RANGE_REVERSED'),
    ({'min': '0.55', 'max': 0.6}, True, 'SPEC_RANGE_NUMBER'),
    ({'min': True, 'max': 1}, True, 'SPEC_RANGE_NUMBER'),
    ({'min': float('inf'), 'max': 1}, True, 'SPEC_RANGE_NUMBER'),
    ({'min': 0, 'max': float('nan')}, True, 'SPEC_RANGE_NUMBER'),
    ({'min': 0}, True, 'SPEC_RANGE_SHAPE'),
    ({'min': 0, 'max': 1, 'unit': 'mm'}, True, 'SPEC_RANGE_SHAPE'),
])
def test_reject_invalid_ranges(value, allowed, code):
    with pytest.raises(SpecificationValueError, match=code):
        normalize_numeric(value, allowed)


def test_normalize_and_format_preserve_scalar_values():
    assert normalize_numeric({'min': .55, 'max': .6}, True) == {'min': .55, 'max': .6}
    assert normalize_numeric({'min': .55, 'max': .55}, True) == .55
    assert normalize_numeric(.55) == .55
    assert format_spec_value(.55) == '0.55'
    assert format_spec_value({'min': .55, 'max': .6}, 'mm', 'en') == '0.55 – 0.60 mm'


def test_template_opt_in_and_property_validation():
    prop = PropertyInput(key='thickness', name_ar='السماكة', name_en='Thickness', kind='text', allows_range=True)
    with pytest.raises(MasterDataError, match='RANGE_ONLY_FOR_NUMBER'):
        assert_template([prop])
    numeric = PropertyInfo('thickness', 'السماكة', 'Thickness', 'number', allows_range=True)
    values = {'thickness': {'min': 1, 'max': 1}}
    assert_property_values([numeric], values)
    assert values == {'thickness': 1}
    with pytest.raises(ProductSpecificationError, match='SPEC_RANGE_NOT_ALLOWED'):
        assert_property_values([PropertyInfo('thickness', 'السماكة', 'Thickness', 'number')],
                               {'thickness': {'min': 1, 'max': 2}})


def test_production_orders_sort_minimum_then_maximum_and_group_identical_ranges():
    values = [.7, {'min': .55, 'max': .65}, {'min': .55, 'max': .6}, .5, {'min': .55, 'max': .6}]
    entries = [NS(target_spec_json={'thickness_mm': v}, allocated_quantity=Decimal(1), unit='roll') for v in values]
    lines = arrange(entries)
    assert [line.target_spec_json['thickness_mm'] for line in lines] == [.5, {'min': .55, 'max': .6}, {'min': .55, 'max': .65}, .7]
    assert lines[1].quantity == 2


def test_quality_range_is_inclusive_not_a_midpoint():
    target, low, high = resolve_limits({'target_source': 'order_line', 'order_spec_key': 'thickness'},
                                     {'thickness': {'min': .55, 'max': .6}})
    assert target is None and (low, high) == (Decimal('.55'), Decimal('.6'))
    assert evaluate('numeric', [low, high], None, low, high)[-1] == 'pass'
    assert evaluate('numeric', [Decimal('.61')], None, low, high)[-1] == 'fail'


def test_columns_union_template_order_empty_hide_choice_units_and_legacy():
    p1 = ProductInfo('one', 'أول', 'First', True, (
        PropertyInfo('thickness', 'السماكة', 'Thickness', 'number', 'mm', allows_range=True),
        PropertyInfo('unused', 'فارغ', 'Empty', 'text'),
        PropertyInfo('color', 'اللون', 'Color', 'choice', options=(('black', 'أسود', 'Black'),)),
    ))
    p2 = ProductInfo('two', 'ثان', 'Second', True, (PropertyInfo('width', 'العرض', 'Width', 'number', 'mm'),))
    rows = [NS(product_type='one', requested_spec_json={'thickness': {'min': .55, 'max': .6}, 'color': 'black'}),
            NS(product_type='two', requested_spec_json={'width': 12, 'legacy': 'Kept'})]
    result = specification_columns(rows, {'one': p1, 'two': p2}, 'en')
    assert result.headers == ['Thickness (mm)', 'Color', 'Width (mm)', 'Other specifications']
    assert result.rows == [['0.55 – 0.60', 'Black', '—', '—'], ['—', '—', '12', 'legacy: Kept']]
    assert not result.landscape


def test_mixed_units_print_inside_cells_and_more_than_six_switches_orientation():
    products = {key: ProductInfo(key, key, key, True, tuple(
        PropertyInfo(f'p{n}', f'P{n}', f'P{n}', 'number', unit) for n in range(7)))
        for key, unit in [('a', 'mm'), ('b', 'cm')]}
    rows = [NS(product_type=k, requested_spec_json={f'p{n}': n for n in range(7)}) for k in products]
    result = specification_columns(rows, products, 'en')
    assert result.headers[0] == 'P0' and result.rows[0][0] == '0 mm' and result.rows[1][0] == '0 cm'
    assert result.landscape
