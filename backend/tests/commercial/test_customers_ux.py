from uuid import UUID
import pytest
from sqlalchemy import select, func, event
from sqlalchemy.exc import IntegrityError
from app.commercial.infrastructure.models import Customer
from app.commercial.infrastructure.contact_models import CustomerContact

BASE = '/api/v1/commercial/customers'


def create(client, headers, with_owner, **extra):
    return client.post(BASE, headers=headers, json=with_owner({'name': 'UX customer', **extra}))


def test_primary_contact_is_created_atomically_and_legacy_columns_are_not_written(client, db, auth_headers, with_owner):
    result = create(client, auth_headers, with_owner, phone='legacy ignored', email='ignored@example.com',
        primary_contact={'name': 'Main contact', 'phone': '+966555123456', 'email': 'main@example.com', 'role': 'Buyer'})
    assert result.status_code == 201, result.text
    row = db.get(Customer, UUID(result.json()['id']))
    contact = db.scalar(select(CustomerContact).where(CustomerContact.customer_id == row.id))
    assert contact.is_default and contact.name == 'Main contact'
    assert row.phone is None and row.email is None
    assert result.json()['phone'] == '+966555123456' and result.json()['email'] == 'main@example.com'


def test_contact_failure_rolls_back_the_customer(client, db, auth_headers, with_owner):
    before = db.scalar(select(func.count()).select_from(Customer))
    def fail(*_): raise IntegrityError('synthetic contact insert', {}, Exception('synthetic'))
    event.listen(CustomerContact, 'before_insert', fail)
    try:
        result = create(client, auth_headers, with_owner, primary_contact={'name': 'Contact'})
        assert result.status_code == 400
    finally:
        event.remove(CustomerContact, 'before_insert', fail)
    assert db.scalar(select(func.count()).select_from(Customer)) == before


def test_optional_contact_requires_a_name_if_any_field_is_present(client, auth_headers, with_owner):
    assert create(client, auth_headers, with_owner, primary_contact={}).status_code == 201
    response = create(client, auth_headers, with_owner, primary_contact={'phone': '5551234'})
    assert response.status_code == 422
    assert response.json()['detail'][0]['type'] == 'CONTACT_NAME_REQUIRED'


def test_city_other_is_kept_only_for_other_and_country_change_clears_it(client, auth_headers, with_owner):
    result = create(client, auth_headers, with_owner, country='sa', city='sa_other', city_other='  New city  ')
    assert result.status_code == 201, result.text
    assert result.json()['city_other'] == 'New city'
    path = BASE + '/' + result.json()['id']
    changed = client.patch(path, headers=auth_headers, json={'country': 'ae'})
    assert changed.status_code == 200, changed.text
    assert changed.json()['city'] is None and changed.json()['city_other'] is None
    changed = client.patch(path, headers=auth_headers, json={'city': 'dubai', 'city_other': 'Discard this'})
    assert changed.status_code == 200 and changed.json()['city_other'] is None
    assert create(client, auth_headers, with_owner, city='sa_other').status_code == 400


def test_contact_search_and_default_fallback_do_not_resurrect_legacy_phone(client, db, auth_headers, with_owner):
    result = create(client, auth_headers, with_owner)
    row = db.get(Customer, UUID(result.json()['id']))
    row.phone, row.email = 'legacy555', 'legacy@example.com'; db.commit()
    assert client.get(BASE + '/' + str(row.id), headers=auth_headers).json()['phone'] == 'legacy555'
    db.add(CustomerContact(organization_id=row.organization_id, customer_id=row.id, name='Default email only',
        phone=None, email='current@example.com', active=True, is_default=True,
        created_by=row.created_by_user_id, updated_by=row.created_by_user_id))
    db.add(CustomerContact(organization_id=row.organization_id, customer_id=row.id, name='Other contact',
        phone='find-contact-123', active=True, is_default=False,
        created_by=row.created_by_user_id, updated_by=row.created_by_user_id))
    db.commit(); db.expire_all()
    current = client.get(BASE + '/' + str(row.id), headers=auth_headers).json()
    assert current['phone'] is None and current['email'] == 'current@example.com'
    found = client.get(BASE + '?search=find-contact-123', headers=auth_headers).json()
    assert found['total'] == 1 and found['items'][0]['id'] == str(row.id)


@pytest.mark.parametrize('url', ['javascript:alert(1)', 'http://maps.google.com', 'data:text/html,test', '//maps.google.com', 'https://'])
def test_location_url_rejects_every_non_https_or_missing_host(url):
    from pydantic import ValidationError
    from app.core.contact_records import SiteInput
    from app.shipping.api.schemas import ShipmentUpdate
    for schema, data in [(SiteInput, {'name': 'Site', 'address': 'Address'}), (ShipmentUpdate, {})]:
        with pytest.raises(ValidationError) as caught:
            schema(**data, location_url=url)
        assert caught.value.errors()[0]['type'] == 'LOCATION_URL_INVALID'
