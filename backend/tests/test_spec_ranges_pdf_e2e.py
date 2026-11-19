"""Real API-to-Chromium PDFs using synthetic data; no operational resources."""
from io import BytesIO
import os
from pathlib import Path
import shutil
import subprocess
import unicodedata

import pytest
from pypdf import PdfReader
from app.core.reporting import providers
from tests.masterdata.test_master_data import md, product, STRAP  # noqa: F401
from tests.commercial.test_quotation_document import doc_env, create_quote  # noqa: F401
from tests.commercial.test_customer_reports import env, reports_env, result_env  # noqa: F401
from tests.shipping.test_shipments import ship, go  # noqa: F401
from tests.shipping.test_delivery_note_totals import sample_note

pytestmark = pytest.mark.skipif(os.environ.get('RUN_SPEC_RANGE_PDF') != '1', reason='Real synthetic PDF E2E opt-in')


@pytest.fixture(autouse=True)
def synthetic_branding(monkeypatch):
    original = providers.branding_provider
    def branding(db, org):
        data = dict(original(db, org))
        for key in ('phone', 'email', 'website', 'address_ar', 'address_en', 'vat_number',
                    'commercial_registration_no', 'unified_number', 'logo_data_uri'):
            data[key] = ''
        data.update(name='Synthetic Factory', legal_name_en='Synthetic Factory', legal_name_ar='مصنع اختباري', bank_accounts=[])
        return data
    monkeypatch.setattr(providers, 'branding_provider', branding)


def save_pdf(response, name, landscape):
    assert response.status_code == 200, response.text if response.status_code != 200 else ''
    assert response.content.startswith(b'%PDF-')
    reader = PdfReader(BytesIO(response.content))
    assert len(reader.pages) == 1
    assert (reader.pages[0].mediabox.width > reader.pages[0].mediabox.height) == landscape
    text = ''.join(page.extract_text() for page in reader.pages)
    assert '0.55' in text and '0.60' in text
    out = Path(os.environ.get('SPEC_RANGE_ARTIFACT_DIR', '../output/pdf/spec-ranges'))
    out.mkdir(parents=True, exist_ok=True)
    pdf = out / (name + '.pdf')
    pdf.write_bytes(response.content)
    if shutil.which('pdftoppm'):
        subprocess.run(['pdftoppm', '-f', '1', '-singlefile', '-scale-to', '1600', '-png', str(pdf), str(out/name)], check=True)
    else:
        import fitz
        with fitz.open(pdf) as document:
            document[0].get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(out/(name+'.png'))


@pytest.mark.parametrize('language', ['ar', 'en'])
def test_quotation_range_pdf(md, language):
    props = [{**p, 'allows_range': p['key'] == 'thickness_mm'} for p in STRAP['properties']]
    definition = product(md, properties=props)
    md.customer.name = md.customer.name_ar = 'عميل اختباري'
    md.customer.name_en = 'Synthetic Customer'
    md.db.commit()
    quote = create_quote(md, attention='قسم المشتريات', subject='Synthetic range quotation', items=[dict(
        line_no=1, product_type=definition['key'], quantity='120', unit='roll', unit_price='25',
        description_ar='شريط تربيط صناعي — بيانات اختبار', description_en='Synthetic strapping band',
        requested_spec_json={'width_mm': 12, 'thickness_mm': {'min': .55, 'max': .6}, 'color': 'black'})])
    response = md.client.post('/api/v1/reports/customers.quotation/pdf', json=dict(quote_id=quote['id'], lang=language, orientation='portrait'))
    save_pdf(response, 'quotation-'+language, True)


@pytest.mark.parametrize('language', ['ar', 'en'])
@pytest.mark.parametrize('gross', [True, False])
def test_delivery_range_pdf(ship, language, gross):
    note = sample_note(ship, gross)
    response = ship.client.post('/api/v1/reports/shipping.delivery_note/pdf', json=dict(shipment_id=note['id'], lang=language))
    save_pdf(response, 'delivery-note-'+language+('' if gross else '-no-gross'), False)
    text = unicodedata.normalize('NFKC', ''.join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages))
    assert all(value in text for value in ('1800', '1500', '3300', '350'))
    weights = ['9', '10', '1800', '1500', '3300'] + (['200', '3500'] if gross else [])
    positions = weight_positions(response.content, language, weights)
    assert positions['3300']['y'] > positions['1800']['y']
    if gross:
        assert positions['3300']['y'] < positions['200']['y'] < positions['3500']['y']
    else:
        assert '3500' not in text



@pytest.mark.parametrize('language', ['ar', 'en'])
def test_return_weight_number_and_unit_pdf(ship, language):
    note = sample_note(ship)
    for action, payload in [('ready', {}), ('dispatch', {}), ('deliver', {'received_by_name': 'Synthetic Receiver'})]:
        response = go(ship, note, action, **payload)
        assert response.status_code == 200, response.text
    returned = ship.client.post('/api/v1/shipping/returns', json=dict(shipment_id=note['id'], reason='quality_defect',
        lines=[dict(shipment_line_id=line['id'], quantity=line['quantity']) for line in note['lines']]))
    assert returned.status_code == 201, returned.text
    response = ship.client.post('/api/v1/reports/shipping.return_note/pdf', json=dict(return_id=returned.json()['id'], lang=language))
    save_pdf(response, 'return-note-'+language, False)
    weight_positions(response.content, language, ['1800', '1500', '3300'])


def weight_positions(content, language, numbers):
    """Measure physical placement independently of PDF text reading order."""
    import pymupdf
    with pymupdf.open(stream=content, filetype='pdf') as document:
        words = document[0].get_text('words')
    unit = '\u0643\u062c\u0645' if language == 'ar' else 'kg'
    units = [word for word in words if unicodedata.normalize('NFKC', word[4]) == unit]
    measurements = {}
    for number in numbers:
        pairs = [(value, label) for value in words if value[4] == number for label in units
                 if max(value[1], label[1]) < min(value[3], label[3]) and abs(value[0] - label[0]) < 50]
        assert len(pairs) == 1, (number, pairs)
        value, label = pairs[0]
        assert (value[0] > label[0]) if language == 'ar' else (value[0] < label[0]), (number, value, label)
        measurements[number] = dict(number_x=round(value[0], 2), unit_x=round(label[0], 2), y=round(value[1], 2))
    return measurements
