import pytest
from uuid import UUID

from app.commercial.domain.customer_names import has_arabic_letter

BASE = '/api/v1/commercial/customers'


@pytest.mark.parametrize('names,display', [
    ({'name_ar': '  عميل تجريبي  '}, 'عميل تجريبي'),
    ({'name_en': '  Synthetic customer  '}, 'Synthetic customer'),
    ({'name_ar': 'عميل', 'name_en': 'Customer'}, 'عميل'),
])
def test_create_names_and_compatibility_display(client, auth_headers, with_owner, names, display):
    response = client.post(BASE, headers=auth_headers, json=with_owner(names))
    assert response.status_code == 201, response.text
    row = response.json()
    assert row['name'] == display
    for key in ('name_ar', 'name_en'):
        assert row[key] == ((names.get(key) or '').strip() or None)


@pytest.mark.parametrize('names', [{}, {'name_ar': '', 'name_en': '  '}, {'name_ar': None, 'name_en': None}])
def test_both_empty_have_a_clear_error(client, auth_headers, with_owner, names):
    response = client.post(BASE, headers=auth_headers, json=with_owner(names))
    assert response.status_code == 422
    assert response.json()['detail'][0]['type'] == 'CUSTOMER_NAME_REQUIRED'


def test_update_recomputes_display_and_preserves_omitted_language(client, auth_headers, with_owner):
    created = client.post(BASE, headers=auth_headers, json=with_owner({'name_en': 'English'})).json()
    path = BASE + '/' + created['id']
    changed = client.patch(path, headers=auth_headers, json={'name_ar': ' عربي '})
    assert changed.status_code == 200, changed.text
    assert changed.json()['name'] == 'عربي' and changed.json()['name_en'] == 'English'
    legacy = client.patch(path, headers=auth_headers, json={'name': 'Updated English'})
    assert legacy.json()['name_ar'] == 'عربي' and legacy.json()['name'] == 'عربي'
    assert legacy.json()['name_en'] == 'Updated English'
    changed = client.patch(path, headers=auth_headers, json={'name_ar': ' '})
    assert changed.json()['name'] == 'Updated English' and changed.json()['name_ar'] is None
    rejected = client.patch(path, headers=auth_headers, json={'name_ar': None, 'name_en': None})
    assert rejected.status_code == 400 and rejected.json()['detail'] == 'CUSTOMER_NAME_REQUIRED'
    assert client.get(path, headers=auth_headers).json()['name'] == 'Updated English'


def test_both_names_search_list_and_picker(client, db, test_org, auth_headers, with_owner):
    from app.commercial.infrastructure.lookups import CommercialCustomerLookup
    from app.shipping.application.support import CustomerReads
    created = client.post(BASE, headers=auth_headers, json=with_owner({'name_ar': 'عميل بحث', 'name_en': 'Unique bilingual'})).json()
    for text in ('بحث', 'bilingual'):
        page = client.get(BASE, headers=auth_headers, params={'search': text}).json()
        assert [r['id'] for r in page['items']] == [created['id']]
        picker = client.get(BASE + '/lookup', headers=auth_headers, params={'search': text}).json()
        assert picker[0]['id'] == created['id'] and picker[0]['name_en'] == 'Unique bilingual'
        production = CommercialCustomerLookup().find_customers(db, test_org.id, text)
        assert production[0].id == UUID(created['id']) and production[0].name_en == 'Unique bilingual'
        shipping = CustomerReads(db, test_org.id).search(text)
        assert shipping[0]['id'] == UUID(created['id']) and shipping[0]['name_en'] == 'Unique bilingual'


@pytest.mark.parametrize('field', ['name_ar', 'name_en'])
def test_name_length_is_checked_after_trimming(client, auth_headers, with_owner, field):
    assert client.post(BASE, headers=auth_headers, json=with_owner({field: ' ' + 'X' * 255 + ' '})).status_code == 201
    assert client.post(BASE, headers=auth_headers, json=with_owner({field: 'X' * 256})).status_code == 422


def test_legacy_api_still_classifies_and_trims(client, auth_headers, with_owner):
    row = client.post(BASE, headers=auth_headers, json=with_owner({'name': ' Mixed عميل '})).json()
    assert row['name_ar'] == 'Mixed عميل' and row['name_en'] is None


def test_unicode_arabic_letter_ranges_and_punctuation():
    assert has_arabic_letter('mixed ع customer')
    assert has_arabic_letter('\ufb50')
    assert has_arabic_letter('\U0001ee00')
    assert not has_arabic_letter('English 123 ، ١٢٣')


@pytest.mark.parametrize('language,ar,en,expected', [
    ('en', 'عميل عربي', 'English customer', 'English customer'),
    ('ar', 'عميل عربي', 'English customer', 'عميل عربي'),
    ('en', 'عميل عربي', None, 'عميل عربي'),
    ('ar', None, 'English customer', 'English customer'),
])
def test_quotation_document_uses_document_language_and_fallback(doc_env, language, ar, en, expected):
    from tests.commercial.test_quotation_document import create_quote, html
    doc_env.customer.name_ar, doc_env.customer.name_en = ar, en
    doc_env.customer.name = ar or en
    doc_env.db.commit()
    quote = create_quote(doc_env)
    text = html(doc_env, quote, language)
    assert expected in text
    other = en if language == 'ar' else ar
    if other and other != expected:
        assert other not in text
    # Free-text heading content remains untouched in both document languages.
    assert 'مدير المشتريات' in text and 'عرض سعر 15MM + 5MM' in text


from tests.commercial.test_quotation_document import doc_env  # noqa: E402,F401
from tests.commercial.test_customer_reports import env, reports_env, result_env  # noqa: E402,F401
