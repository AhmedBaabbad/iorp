"""Real HTTP boundaries with foreign records and persisted-state assertions."""
import uuid

import pytest

from tests.test_tenant_isolation import isolated_tenants
from app.masterdata.infrastructure.models import Product
from app.procurement.infrastructure.models import Supplier
from app.shipping.infrastructure.directory_models import Carrier
from app.notifications.infrastructure.models import NotificationItem, Announcement


@pytest.fixture
def foreign_records(db, isolated_tenants):
    d = isolated_tenants
    org, user = d['org_b'].id, d['user_b'].id
    rows = {
        'product': Product(organization_id=org, code='FOREIGN', key='foreign', name_ar='Foreign', name_en='Foreign', created_by_user_id=user),
        'supplier': Supplier(organization_id=org, supplier_code='FOREIGN', name='Foreign', category='raw_material', created_by_user_id=user),
        'carrier': Carrier(organization_id=org, name='Foreign', created_by=user, updated_by=user),
        'notification': NotificationItem(organization_id=org, recipient_user_id=user, event='test', category='work'),
        'announcement': Announcement(organization_id=org, author_user_id=user, author_name='Foreign', title='Foreign', body='Private', audience='everyone'),
    }
    db.add_all(rows.values())
    db.commit()
    return rows


@pytest.mark.parametrize('key,path,method,payload', [
    ('product', '/masterdata/products/{id}', 'get', None),
    ('product', '/masterdata/products/{id}', 'patch', {'name_en': 'Changed'}),
    ('supplier', '/procurement/suppliers/{id}', 'get', None),
    ('supplier', '/procurement/suppliers/{id}', 'patch', {'name': 'Changed'}),
    ('supplier', '/procurement/suppliers/{id}/status', 'post', {'status': 'approved'}),
    ('carrier', '/shipping/directory/carriers/{id}', 'put', {'name': 'Changed', 'version': 1}),
    ('notification', '/notifications/{id}/read', 'post', None),
    ('notification', '/notifications/{id}/hide', 'post', None),
    ('notification', '/notifications/{id}/acknowledge', 'post', None),
    ('announcement', '/announcements/{id}', 'get', None),
    ('announcement', '/announcements/{id}/withdraw', 'post', None),
])
def test_foreign_resource_matches_missing_and_remains_unchanged(client, db, isolated_tenants, foreign_records, key, path, method, payload):
    row = foreign_records[key]
    before = {c.name: getattr(row, c.name) for c in row.__table__.columns}
    kwargs = {'headers': isolated_tenants['headers']}
    if payload is not None:
        kwargs['json'] = payload
    foreign = client.request(method, '/api/v1' + path.format(id=row.id), **kwargs)
    missing = client.request(method, '/api/v1' + path.format(id=uuid.uuid4()), **kwargs)
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()
    db.refresh(row)
    assert {c.name: getattr(row, c.name) for c in row.__table__.columns} == before


@pytest.mark.parametrize('key,path', [
    ('product', '/masterdata/products'), ('supplier', '/procurement/suppliers'),
    ('carrier', '/shipping/directory/carriers'), ('notification', '/notifications'),
    ('announcement', '/announcements'),
])
def test_foreign_records_hidden_despite_scope_override(client, isolated_tenants, foreign_records, key, path):
    d = isolated_tenants
    result = client.get('/api/v1' + path, headers={**d['headers'], 'X-Organization-ID': str(d['org_b'].id)},
                        params={'organization_id': str(d['org_b'].id)})
    assert result.status_code == 200
    assert str(foreign_records[key].id) not in result.text


def test_foreign_carrier_reference_rejected(client, db, isolated_tenants, foreign_records):
    from app.shipping.infrastructure.directory_models import Driver
    before = db.query(Driver).count()
    response = client.post('/api/v1/shipping/directory/drivers', headers=isolated_tenants['headers'],
                           json={'name': 'New driver', 'affiliation': 'external', 'carrier_id': str(foreign_records['carrier'].id)})
    # References use an opaque 422, unlike direct resource URLs (404).
    assert response.status_code == 422
    assert response.json() == {'detail': 'TRANSPORT_RECORD_UNAVAILABLE'}
    missing = client.post('/api/v1/shipping/directory/drivers', headers=isolated_tenants['headers'],
                          json={'name': 'New driver', 'affiliation': 'external', 'carrier_id': str(uuid.uuid4())})
    assert missing.status_code == response.status_code
    assert missing.json() == response.json()
    assert db.query(Driver).count() == before
