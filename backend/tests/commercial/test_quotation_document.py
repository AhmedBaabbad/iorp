"""QUOTE-DOC-001: the quotation document, its settings (signature, terms) and the company bank accounts."""
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from tests.commercial.test_customer_reports import env, reports_env, result_env  # noqa: F401  (fixture chain)

QUOTES = "/api/v1/commercial"
TERMS = [
    dict(title_ar="المواصفات الفنية", title_en="Technical specification", body_ar="خامات شريط PP — السماكة وفق العينات المعتمدة.",
         body_en="PP strap material; thickness as per the approved samples."),
    dict(title_ar="مدة الصلاحية", title_en="Validity", body_ar="7 أيام من تاريخ عرض السعر. الأسعار قابلة للتغيير شهريا.",
         body_en="7 days from the quotation date. Prices may change monthly."),
    dict(title_ar="الدفع", title_en="Payment", body_ar="يتم الدفع بعد شهر من تاريخ الفاتورة.", body_en=None),
    dict(title_ar="بند موقوف", body_ar="لا يظهر", is_active=False),
]
BANK = dict(bank_name_ar="مصرف الراجحي", bank_name_en="Al Rajhi Bank", account_name="مصنع ريحانة الأفق للصناعة",
            account_number="123608010000000", iban="SA03 8000 0000 6080 1016 7519", swift_code="RJHISARI")


@pytest.fixture
def doc_env(env):
    env.ctx.auth_user.permissions |= {'commercial:quotes:create', 'commercial:quotes:update', 'commercial:quote_settings:read',
                                      'commercial:quote_settings:update', 'organization:branding:update'}
    return env


def create_quote(e, **extra):
    now = datetime.now(timezone.utc)
    body = dict(issue_date=now.isoformat(), valid_until=(now + timedelta(days=7)).isoformat(), currency='SAR', tax_rate='15',
                attention='مدير المشتريات', subject='عرض سعر 15MM + 5MM', notes=None,
                items=[dict(line_no=1, product_type='strap', quantity='2000', unit='roll', unit_price='95',
                            description_ar='شريط تربيط أسود مقاس 5MM × 0.35MM × 10KG', description_en='Black strapping band 5MM × 0.35MM × 10KG'),
                       dict(line_no=2, product_type='strap', requested_spec_json={'width': '15MM', 'thickness': '0.85MM'},
                            quantity='150', unit='roll', unit_price='60')])
    body.update(extra)
    r = e.client.post(f"{QUOTES}/customers/{e.customer.id}/quotes", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def settle(e):
    assert e.client.put(f"{QUOTES}/quote-settings", json=dict(signature_title_ar='مدير المبيعات', signature_title_en='Sales Manager',
                                                              show_preparer_name=True, terms=TERMS)).status_code == 200
    branding = e.client.get('/api/v1/organization/branding').json()
    keep = {k: branding[k] for k in ('legal_name_ar', 'legal_name_en', 'phone', 'email', 'website', 'address_ar', 'address_en', 'primary_color')}
    keep.update(legal_name_ar='مصنع ريحانة الأفق للصناعة', legal_name_en='Rehanat Al Ofoq Industrial Factory', phone='0557504690',
                email='factory@rehanh.com', website='factory.rehanh.com', address_ar='المملكة العربية السعودية - الخرج - الرفايع',
                address_en='Al-Kharj, Saudi Arabia', bank_accounts=[BANK, dict(BANK, bank_name_ar='بنك موقوف', is_active=False)])
    r = e.client.put('/api/v1/organization/branding', json=keep)
    assert r.status_code == 200, r.text
    return r.json()


def html(e, quote, lang='ar'):
    r = e.client.post('/api/v1/reports/customers.quotation/preview', json=dict(quote_id=quote['id'], lang=lang))
    assert r.status_code == 200, r.text
    return r.text


def test_server_computes_vat_from_the_rate_and_numbers_are_qt(doc_env):
    quote = create_quote(doc_env, tax_amount='1')  # a client amount is ignored when the rate is given
    assert quote['quote_number'].startswith('QT-')
    assert Decimal(quote['subtotal_amount']) == Decimal('199000') and Decimal(quote['tax_amount']) == Decimal('29850.00')
    assert Decimal(quote['total_amount']) == Decimal('228850.00')
    items = [dict({k: i[k] for k in ('line_no', 'product_type', 'requested_spec_json', 'quantity', 'unit', 'unit_price')}, discount_percent='10')
             for i in quote['items']]
    r = doc_env.client.patch(f"{QUOTES}/quotes/{quote['id']}", json=dict(items=items, discount_amount='1'))  # an amount is not taken
    assert Decimal(r.json()['discount_amount']) == Decimal('19900.00')  # 10 % of every line
    assert Decimal(r.json()['tax_amount']) == Decimal('26865.00')  # 15 % of 179,100 after the discount
    assert Decimal(r.json()['total_amount']) == Decimal('205965.00')


def test_settings_round_trip_and_defaults(doc_env):
    r = doc_env.client.get(f"{QUOTES}/quote-settings").json()
    assert r['signature_title_ar'] == 'مدير المبيعات' and r['signature_title_en'] == 'Sales Manager' and r['terms'] == []
    settle(doc_env)
    r = doc_env.client.get(f"{QUOTES}/quote-settings").json()
    assert [t['title_ar'] for t in r['terms']] == [t['title_ar'] for t in TERMS] and r['show_preparer_name'] is True
    doc_env.ctx.auth_user.permissions.discard('commercial:quote_settings:update')
    assert doc_env.client.put(f"{QUOTES}/quote-settings", json=dict(terms=[])).status_code == 403


def test_bank_accounts_are_normalised_and_validated(doc_env):
    branding = settle(doc_env)
    assert branding['bank_accounts'][0]['iban'] == 'SA0380000000608010167519' and len(branding['bank_accounts']) == 2
    r = doc_env.client.put('/api/v1/organization/branding', json=dict(bank_accounts=[dict(BANK, iban='not an iban')]))
    assert r.status_code == 422


def test_arabic_document_content(doc_env):
    settle(doc_env)
    text = html(doc_env, create_quote(doc_env))
    for expected in ('عرض سعر', 'مدير المشتريات', 'عرض سعر 15MM + 5MM', 'شريط تربيط أسود مقاس 5MM × 0.35MM × 10KG', 'لفة',
                     '2,000', '190,000.00', 'ضريبة القيمة المضافة (15%)', '29,850.00', '228,850.00', 'الإجمالي شامل الضريبة',
                     'الشروط والأحكام', 'خامات شريط PP', 'مع خالص التحية', 'مدير المبيعات', 'مصرف الراجحي', 'SA0380000000608010167519',
                     'factory@rehanh.com', 'factory.rehanh.com'):
        assert expected in text, expected
    assert 'strap — 15MM × 0.85MM' in text  # no description: product and specification
    assert 'بند موقوف' not in text and 'لا يظهر' not in text  # inactive term and inactive bank account


def test_a_specification_typed_without_values_is_printed_in_full(doc_env):
    """A whole description typed as the property, with no value, prints in order with the other rows (PP Strap … then White)."""
    long = "PP Strap 19mm X 0.85mm X 10 KG (1000 Meter) White (transparent core), export packing"
    quote = create_quote(doc_env, items=[dict(line_no=1, product_type="PP Strap", requested_spec_json={long: "", "color": "White"},
                                              quantity="100", unit="roll", unit_price="60")])
    for lang in ("ar", "en"):
        assert f"PP Strap — {long} × White" in html(doc_env, quote, lang)


def test_english_document_prints_only_english_settings(doc_env):
    settle(doc_env)
    text = html(doc_env, create_quote(doc_env), 'en')
    for expected in ('Quotation', 'Black strapping band', 'roll', 'Total including VAT', 'Terms and conditions', 'Technical specification',
                     'Sales Manager', 'Al Rajhi Bank', 'With best regards'):
        assert expected in text, expected
    assert 'يتم الدفع بعد شهر' not in text and 'الدفع' not in text  # a term without English is not printed: no mixing


def test_the_settings_language_is_the_quotation_language(doc_env):
    assert doc_env.client.get(f"{QUOTES}/quote-settings").json()['document_language'] == 'ar'
    english_only = dict(title_en='Delivery', body_en='Ex-works Al-Kharj, within 10 days of the order.')
    r = doc_env.client.put(f"{QUOTES}/quote-settings", json=dict(document_language='en', signature_title_en='Sales Director', terms=[english_only, TERMS[0]]))
    assert r.status_code == 200, r.text
    assert r.json()['document_language'] == 'en' and r.json()['terms'][0]['title_ar'] is None
    assert doc_env.client.put(f"{QUOTES}/quote-settings", json=dict(document_language='fr')).status_code == 422
    assert doc_env.client.put(f"{QUOTES}/quote-settings", json=dict(terms=[dict(title_en='Delivery')])).status_code == 422
    quote = create_quote(doc_env)
    seen = {}
    import app.commercial.reporting.customers.routes as routes
    original = routes.generate_response
    routes.generate_response = lambda key, params, fmt, current, db: seen.update(params) or original(key, params, 'html', current, db)
    try:
        doc_env.client.get(f"{QUOTES}/quotes/{quote['id']}/document.pdf")
        assert seen['lang'] == 'en'  # no language asked: the settings' language
        doc_env.client.get(f"{QUOTES}/quotes/{quote['id']}/document.pdf", params=dict(lang='ar'))
        assert seen['lang'] == 'ar'
    finally:
        routes.generate_response = original
    text = html(doc_env, quote, 'en')
    assert 'Ex-works Al-Kharj' in text and 'Sales Director' in text and 'Technical specification' in text
    arabic = html(doc_env, quote, 'ar')
    assert 'Ex-works Al-Kharj' not in arabic and 'المواصفات الفنية' in arabic


def test_quotation_is_not_in_the_report_center_and_needs_quote_read(doc_env):
    quote = create_quote(doc_env)
    keys = {d['key'] for d in doc_env.client.get('/api/v1/reports/definitions?module=customers').json()}
    assert 'customers.quotation' not in keys
    doc_env.ctx.auth_user.permissions.discard('commercial:quotes:read')
    from dataclasses import replace
    doc_env.ctx.tenant = replace(doc_env.ctx.tenant, is_organization_root=False)
    doc_env.ctx.user.is_organization_root = False
    r = doc_env.client.post('/api/v1/reports/customers.quotation/preview', json=dict(quote_id=quote['id']))
    assert r.status_code == 403


def test_unknown_or_foreign_quote_is_not_found(doc_env):
    r = doc_env.client.post('/api/v1/reports/customers.quotation/preview', json=dict(quote_id=str(uuid4())))
    assert r.status_code == 404 and r.json()['detail'] == 'QUOTE_NOT_FOUND'


@pytest.mark.skipif(os.environ.get('RUN_RENDERER_TESTS') != '1', reason='Real Chromium opt-in')
def test_real_quotation_pdf_samples(doc_env):
    import pymupdf
    settle(doc_env)
    doc_env.customer.name = 'الشركة المتحدة لصناعة الكرتون'
    doc_env.db.commit()
    quote = create_quote(doc_env)
    from tests.report_samples import samples_dir
    out = samples_dir('quotation')
    out.mkdir(parents=True, exist_ok=True)
    for lang in ('ar', 'en'):
        r = doc_env.client.get(f"/api/v1/commercial/quotes/{quote['id']}/document.pdf", params=dict(lang=lang))
        assert r.status_code == 200 and r.content.startswith(b'%PDF-'), r.text[:300]
        (out / f'quotation-{lang}.pdf').write_bytes(r.content)
        pdf = pymupdf.open(stream=r.content, filetype='pdf')
        text = ''.join(page.get_text() for page in pdf)
        assert quote['quote_number'] in text and 'SA0380000000608010167519' in text
        pdf[0].get_pixmap(matrix=pymupdf.Matrix(1.3, 1.3)).save(str(out / f'quotation-{lang}.png'))


def discounted(e, first='10', second='0'):
    quote = create_quote(e)
    items = [dict({k: i[k] for k in ('line_no', 'product_type', 'requested_spec_json', 'quantity', 'unit', 'unit_price', 'description_ar', 'description_en')},
                  discount_percent=pct) for i, pct in zip(quote['items'], (first, second))]
    r = e.client.patch(f"{QUOTES}/quotes/{quote['id']}", json=dict(items=items))
    assert r.status_code == 200, r.text
    return r.json()


def test_discount_on_one_line_is_taken_before_vat(doc_env):
    quote = discounted(doc_env)  # line 1: 2,000 × 95 = 190,000 less 10 %; line 2: 150 × 60 = 9,000, no discount
    first, second = quote['items']
    assert Decimal(first['discount_amount']) == Decimal('19000.00') and Decimal(first['net_total']) == Decimal('171000.00')
    assert Decimal(second['discount_amount']) == 0 and Decimal(second['net_total']) == Decimal('9000.00')
    assert Decimal(quote['subtotal_amount']) == Decimal('199000.00') and Decimal(quote['discount_amount']) == Decimal('19000.00')
    assert Decimal(quote['tax_amount']) == Decimal('27000.00')  # 15 % of 180,000
    assert Decimal(quote['total_amount']) == Decimal('207000.00')
    r = doc_env.client.patch(f"{QUOTES}/quotes/{quote['id']}", json=dict(items=[dict(line_no=1, product_type='strap', quantity='1', unit='roll',
                                                                                      unit_price='1', discount_percent='101')]))
    assert r.status_code == 422


def test_document_shows_the_discount_lines_and_totals(doc_env):
    settle(doc_env)
    text = html(doc_env, discounted(doc_env))
    for expected in ('المجموع قبل الخصم', '199,000.00', 'الخصم على البند 1 (10%)', '- 19,000.00', 'المجموع بعد الخصم', '180,000.00',
                     'ضريبة القيمة المضافة (15%)', '27,000.00', '207,000.00', 'الصافي', '10% = 19,000.00', '171,000.00'):
        assert expected in text, expected
    text = html(doc_env, discounted(doc_env, '10', '10'), 'en')
    for expected in ('Subtotal before discount', 'Discount (10%)', 'Subtotal after discount', '179,100.00', 'Net'):
        assert expected in text, expected
    plain = html(doc_env, create_quote(doc_env))
    assert 'الصافي' not in plain and 'المجموع قبل الضريبة' in plain  # a quotation without a discount reads as before
