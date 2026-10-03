"""DOC-IDENTITY-001: one corporate header/footer for every report and document, internal or external.

Company values live only in the identity settings; internal reports carry no legal or contact data,
customer-facing documents carry all of it, and a change in the identity reaches every document.
"""
import os
import re
from pathlib import Path

import pytest

from app.core.reporting.service import classification_for, default_margins
from app.core.reporting.registry import registry
from tests.commercial.test_customer_reports import env, preview, reports_env, result_env  # noqa: F401  (fixture chain)
from tests.commercial.test_quotation_document import create_quote, doc_env  # noqa: F401

ROOT = Path(__file__).parents[1]
IDENTITY = dict(legal_name_ar='شركة ريحانة الأفق للصناعة', legal_name_en='Rehanah Al-Ofoq Factory for Industry',
                commercial_registration_no='1009176287', unified_number='7043447197', vat_number='314824635200003',
                address_ar='الرياض – الشفاء – طريق ابن تيمية – 14714', address_en='Al Shifa, Ibn Taymiyyah Rd, Riyadh 14714, Saudi Arabia',
                phone='0557504690', email='factory@rehanh.com', website='https://factory.rehanh.com/',
                descriptor_ar='حلول صناعية لأشرطة التربيط والتغليف', descriptor_en='Industrial Strapping & Packaging Solutions',
                bank_accounts=[dict(bank_name_ar='مصرف الراجحي', bank_name_en='Al Rajhi Bank', iban='SA0380000000608010167519')])
LEGAL_AND_CONTACT = ('1009176287', '7043447197', '314824635200003', '0557504690', 'factory@rehanh.com', 'factory.rehanh.com',
                     'طريق ابن تيمية', 'SA0380000000608010167519', 'مصرف الراجحي')


def identify(e, **change):
    r = e.client.put('/api/v1/organization/branding', json={**IDENTITY, **change})
    assert r.status_code == 200, r.text
    return r.json()


def markup(response) -> str:
    """The rendered document without its embedded stylesheet (class names and comments live there too)."""
    return re.sub(r'<style>.*?</style>', '', response.text, flags=re.S)


def test_classification_follows_the_definition_then_the_audience():
    assert classification_for(registry.get('production.order_full'), 'internal') == 'internal'
    assert classification_for(registry.get('customers.customer_profile'), 'internal') == 'internal'
    assert classification_for(registry.get('customers.customer_profile'), 'customer') == 'external'
    assert classification_for(registry.get('customers.quotation'), 'customer') == 'external'


def test_external_margins_grow_with_the_bank_accounts():
    one, three = (default_margins('external', dict(phone='1', bank_accounts=[dict(is_active=True)] * n)) for n in (1, 3))
    assert three[1] > one[1] > default_margins('internal', {})[1]


def test_internal_report_carries_names_and_internal_mark_only(env):
    identify(env)
    html = markup(preview(env, audience='internal', lang='ar'))
    assert 'شركة ريحانة الأفق للصناعة' in html and 'Rehanah Al-Ofoq Factory for Industry' in html
    assert 'وثيقة داخلية' in html and 'id-internal' in html and 'id-external' not in html
    assert '<th>القسم</th><td>العملاء</td>' in html
    assert 'حلول صناعية لأشرطة التربيط والتغليف' in html and 'Industrial Strapping &amp; Packaging Solutions' in html  # header tagline
    for value in LEGAL_AND_CONTACT:
        assert value not in html, value


def test_customer_version_carries_the_full_legal_identity(env):
    identify(env)
    html = markup(preview(env, audience='customer', lang='en'))
    assert 'id-external' in html and 'Internal document' not in html
    header, footer = html.split('<header', 1)[1].split('</header>', 1)[0], html.split('<footer', 1)[1].split('</footer>', 1)[0]
    # The legal identity is in the header, in Arabic on the right and English on the left.
    for value in ('<dt>CR No.</dt><dd>1009176287', '<dt>Unified No.</dt><dd>7043447197', '<dt>VAT No.</dt><dd>314824635200003',
                  '<dt>السجل التجاري</dt><dd><bdi dir="ltr">1009176287', '<dt>الرقم الموحد</dt>', '<dt>الرقم الضريبي</dt>',
                  'Industrial Strapping &amp; Packaging Solutions'):
        assert value in header, value
    # The footer carries the contacts and the bank accounts, not the legal identity.
    for value in ('Al Shifa, Ibn Taymiyyah Rd', '0557504690', 'factory@rehanh.com', '<em>IBAN</em><bdi dir="ltr">SA0380000000608010167519', 'Al Rajhi Bank'):
        assert value in footer, value
    assert '1009176287' not in footer and '314824635200003' not in footer
    assert 'https://' not in html  # the website is stored and printed without its scheme


def test_quotation_uses_the_shared_external_identity(doc_env):
    identify(doc_env)
    quote = create_quote(doc_env)
    html = markup(doc_env.client.post('/api/v1/reports/customers.quotation/preview', json=dict(quote_id=quote['id'])))
    assert 'id-external' in html and '<dt>السجل التجاري</dt><dd><bdi dir="ltr">1009176287' in html and '<dt>الرقم الموحد</dt>' in html
    assert quote['quote_number'] in html


def test_production_report_is_internal_in_both_languages(env):
    identify(env)
    po = env.planned(quantity='10')
    for lang, mark in (('ar', 'وثيقة داخلية'), ('en', 'Internal document')):
        html = markup(env.client.post('/api/v1/reports/production.order_full/preview', json=dict(order_id=po['id'], lang=lang)))
        assert mark in html and f'dir="{"rtl" if lang == "ar" else "ltr"}"' in html
        assert not [v for v in LEGAL_AND_CONTACT if v in html]


def test_identity_change_reaches_every_document(env):
    identify(env)
    identify(env, phone='0500000001', legal_name_en='Renamed Factory Co.')
    html = markup(preview(env, audience='customer', lang='en'))
    assert '0500000001' in html and 'Renamed Factory Co.' in html and '0557504690' not in html


@pytest.mark.parametrize('field,value', [('vat_number', '1230000000'), ('vat_number', '414824635200003'),
                                         ('commercial_registration_no', '2000005'), ('unified_number', '1043447197')])
def test_invalid_saudi_identifiers_are_refused(env, field, value):
    r = env.client.put('/api/v1/organization/branding', json={**IDENTITY, field: value})
    assert r.status_code == 422


def test_no_company_value_is_written_in_code_or_templates():
    values = ('1009176287', '7043447197', '314824635200003', '0557504690', 'factory@rehanh.com', 'factory.rehanh.com', 'Rehanah', 'ريحانة')
    roots = [ROOT / 'app', ROOT.parent / 'frontend' / 'src']
    offenders = []
    for root in roots:
        for path in root.rglob('*'):
            if path.suffix in {'.py', '.html', '.css', '.ts', '.tsx', '.json'} and '__pycache__' not in path.parts and 'node_modules' not in path.parts:
                text = path.read_text(encoding='utf-8', errors='ignore')
                offenders += [f'{path.relative_to(ROOT.parent)}: {v}' for v in values if v in text]
    assert offenders == []


@pytest.mark.skipif(os.environ.get('RUN_RENDERER_TESTS') != '1', reason='Real Chromium opt-in')
def test_real_pdfs_internal_and_external(env):
    import pymupdf
    from tests.report_samples import samples_dir
    identify(env)
    out = samples_dir('identity')
    po = env.planned(quantity='10')
    cases = [('production-order-ar', '/api/v1/reports/production.order_full/pdf', dict(order_id=po['id'], lang='ar'), 'internal'),
             ('customer-profile-customer-en', '/api/v1/reports/customers.customer_profile/pdf',
              dict(customer_id=str(env.customer.id), audience='customer', lang='en'), 'external'),
             ('customer-profile-internal-ar', '/api/v1/reports/customers.customer_profile/pdf',
              dict(customer_id=str(env.customer.id), audience='internal', lang='ar'), 'internal')]
    for name, url, body, kind in cases:
        r = env.client.post(url, json=body)
        assert r.status_code == 200 and r.content.startswith(b'%PDF-'), r.text[:200]
        (out / f'{name}.pdf').write_bytes(r.content)
        pdf = pymupdf.open(stream=r.content, filetype='pdf')
        text = ''.join(page.get_text() for page in pdf)
        if kind == 'internal':
            assert not [v for v in LEGAL_AND_CONTACT if v in text], name
        else:
            assert '1009176287' in text and '314824635200003' in text and '7043447197' in text, name
        for number, page in enumerate(pdf, 1):  # footer with page numbers on every page
            assert str(number) in page.get_text()
        pdf[0].get_pixmap(matrix=pymupdf.Matrix(1.3, 1.3)).save(str(out / f'{name}.png'))
