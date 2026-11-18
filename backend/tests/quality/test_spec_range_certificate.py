"""A ranged production lot stays an object through inspection and a frozen COA."""
from uuid import UUID
import pytest

from tests.quality.test_quality_certificates import cq, COA  # noqa: F401
from tests.quality.test_quality_specifications import sq, strap_order  # noqa: F401
from tests.quality.test_quality_inspections import q, result_env  # noqa: F401
from app.masterdata.infrastructure.models import Product, ProductProperty
from app.quality.infrastructure.models import QualityCertificate, QualityCheck
from app.production.infrastructure.models import ProductionOrderItem


@pytest.mark.parametrize('inspector_fallback', [False, True])
def test_range_acceptance_and_certificate_columns_are_frozen(cq, inspector_fallback):
    product = Product(organization_id=cq.org.id, created_by_user_id=cq.user.id, code='PRD-RANGE', key='film', name_ar='منتج اختباري', name_en='Synthetic product', kind='finished')
    product.properties = [
        ProductProperty(line_no=1, key='width_mm', name_ar='العرض', name_en='Width', kind='number', unit='mm'),
        ProductProperty(line_no=2, key='thickness_mm', name_ar='السماكة', name_en='Thickness', kind='number', unit='mm', allows_range=True),
    ]
    cq.db.add(product); cq.db.commit()
    check = cq.opened(strap_order(cq, width_mm=5, thickness_mm={'min': .55, 'max': .6}), check_type='finished_product_inspection')
    thickness = next(m for m in check['measurements'] if m['parameter_code'] == 'THICKNESS')
    assert float(thickness['lower_limit']) == .55 and float(thickness['upper_limit']) == .6
    check = cq.measure(check, 'WIDTH', ['5', '5', '5'])
    check = cq.measure(check, 'THICKNESS', ['.55', '.60'])
    check = cq.measure(check, 'ROLL_LENGTH', ['6950'])
    check = cq.measure(check, 'COLOR', result='conforming')
    closed = cq.close_check(check, '120', '120', '0', 'accepted')
    assert closed.status_code == 200, closed.text
    if inspector_fallback:
        # A missing source value must not replace the inspector's effective range
        # with null when the already measured inspection is frozen into a COA.
        inspection = cq.db.get(QualityCheck, UUID(check['id']))
        line = cq.db.get(ProductionOrderItem, inspection.production_order_item_id)
        line.target_spec_json = {**line.target_spec_json, 'thickness_mm': None}
        inspection.lot_values = {**(inspection.lot_values or {}), 'thickness_mm': {'min': .55, 'max': .6}}
        cq.db.commit()
    draft = cq.draft(closed.json())
    frozen = cq.db.get(QualityCertificate, UUID(draft['id'])).product_specification
    assert frozen['values']['thickness_mm'] == {'min': .55, 'max': .6}
    product.properties[1].name_en = 'Changed after certification'
    cq.db.commit()
    response = cq.client.post('/api/v1/reports/quality.certificate/preview', json=dict(certificate_id=draft['id'], lang='en'))
    assert response.status_code == 200, response.text
    assert 'Thickness (mm)' in response.text and '0.55 – 0.60' in response.text
    assert 'Changed after certification' not in response.text
