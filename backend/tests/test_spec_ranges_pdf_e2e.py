"""Real API-to-Chromium PDFs using synthetic data; no operational resources."""
from io import BytesIO
import os
from pathlib import Path
import shutil
import subprocess

import pytest
from pypdf import PdfReader
from app.core.reporting import providers
from tests.masterdata.test_master_data import md, product, STRAP  # noqa: F401
from tests.commercial.test_quotation_document import doc_env, create_quote  # noqa: F401
from tests.commercial.test_customer_reports import env, reports_env, result_env  # noqa: F401
from tests.shipping.test_shipments import ship  # noqa: F401

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


def test_delivery_range_pdf(ship):
    note = ship.create(customer_name='Synthetic Customer', consignee_name='Synthetic receiving team',
        driver_name='Synthetic Driver', driver_affiliation='external', delivery_address='Synthetic destination',
        lines=[dict(description='Synthetic band', width_mm='12', thickness_mm='.55', thickness_max_mm='.60',
                    quantity='120', unit='roll', weight='1200', weight_unit='kg')])
    response = ship.client.post('/api/v1/reports/shipping.delivery_note/pdf', json=dict(shipment_id=note['id'], lang='ar'))
    save_pdf(response, 'delivery-note-ar', False)
