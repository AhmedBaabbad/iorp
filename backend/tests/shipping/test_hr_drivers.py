from uuid import UUID, uuid4
import pytest
from sqlalchemy import select
from tests.shipping.test_shipments import ship
from app.shipping.infrastructure.directory_models import Driver, Vehicle
from app.workforce.infrastructure.models import WorkforceMember
from app.foundation.infrastructure.models import TenantAuditEntry

ROOT = '/api/v1/shipping/directory'


def employee(env, code='D1', name='Employee', kind='driver', **values):
    row = WorkforceMember(organization_id=env.org.id, employee_code=code, full_name=name,
                          worker_type=kind, employment_type='employee', **values)
    env.db.add(row)
    env.db.commit()
    return row


def external(**values):
    return dict(name='External driver', affiliation='external', identity_no='ID-001', **values)


def test_external_identity_required_and_duplicate_returns_existing_id(ship):
    missing = ship.client.post(f'{ROOT}/drivers', json=dict(name='Missing', affiliation='external'))
    assert missing.status_code == 422 and missing.json()['detail'] == 'DRIVER_IDENTITY_REQUIRED'
    first = ship.client.post(f'{ROOT}/drivers', json=external())
    assert first.status_code == 201
    second = ship.client.post(f'{ROOT}/drivers', json=external())
    assert second.status_code == 409
    assert second.json()['detail'] == {'code': 'DRIVER_IDENTITY_EXISTS', 'existing_driver_id': first.json()['id']}
    body = external()
    body.update(identity_no=None, version=1)
    assert ship.client.put(f"{ROOT}/drivers/{first.json()['id']}", json=body).json()['detail'] == 'DRIVER_IDENTITY_REQUIRED'


def test_internal_personal_data_is_live_and_incoming_values_are_ignored(ship):
    worker = employee(ship, phone='0551234567', email='employee@example.com', national_id='EMP-ID')
    response = ship.client.post(f'{ROOT}/drivers', json=dict(affiliation='internal', workforce_member_id=str(worker.id),
        name='Forged', phone='Forged', email='not an email', identity_no='Forged'))
    assert response.status_code == 201, response.text
    row = response.json()
    assert (row['name'], row['phone'], row['email'], row['identity_no']) == ('Employee', '0551234567', 'employee@example.com', 'EMP-ID')
    stored = ship.db.get(Driver, UUID(row['id']))
    assert stored.name == '' and stored.phone is None and stored.email is None and stored.identity_no is None
    original = ship.create(driver_id=row['id'])
    worker.full_name = 'Updated employee'
    worker.phone = '0500000000'
    ship.db.commit()
    options = ship.client.get(f'{ROOT}/drivers/options?search=Updated').json()
    assert options[0]['name'] == 'Updated employee'
    assert 'email' not in options[0] and 'identity_no' not in options[0]
    saved = ship.client.patch(f"/api/v1/shipping/shipments/{original['id']}", json={'notes': 'Unrelated edit'}).json()
    assert saved['driver_name'] == 'Employee' and saved['driver_phone'] == original['driver_phone']


def test_driver_fields_vehicle_validation_and_options_privacy(ship):
    vehicle = Vehicle(organization_id=ship.org.id, name='Truck', plate='ABC', created_by=ship.user.id, updated_by=ship.user.id)
    ship.db.add(vehicle)
    ship.db.commit()
    body = external(email='driver@example.com', license_no='L1', license_expiry='2020-01-01',
                    default_vehicle_id=str(vehicle.id), notes='No blocking on expired licenses')
    created = ship.client.post(f'{ROOT}/drivers', json=body)
    assert created.status_code == 201, created.text
    option = ship.client.get(f'{ROOT}/drivers/options').json()[0]
    assert option['default_vehicle_id'] == str(vehicle.id) and option['license_expiry'] == '2020-01-01'
    assert 'identity_no' not in option and 'email' not in option
    body.update(identity_no='ANOTHER', email='invalid')
    assert ship.client.post(f'{ROOT}/drivers', json=body).status_code == 422
    body.update(email=None, default_vehicle_id=str(uuid4()))
    assert ship.client.post(f'{ROOT}/drivers', json=body).status_code == 422
    vehicle.active = False
    ship.db.commit()
    body['default_vehicle_id'] = str(vehicle.id)
    assert ship.client.post(f'{ROOT}/drivers', json=body).status_code == 422


@pytest.mark.parametrize('permission', ['shipping:shipments:create', 'shipping:shipments:update',
    'procurement:receipts:create', 'procurement:receipts:update'])
def test_quick_permissions_external_only_and_audited(ship, permission):
    ship.ctx.auth_user.permissions = {permission}
    response = ship.client.post(f'{ROOT}/drivers/quick', json=external())
    assert response.status_code == 201, response.text
    entry = ship.db.scalar(select(TenantAuditEntry).where(TenantAuditEntry.entity_id == response.json()['id']))
    assert entry is not None and entry.actor_id == ship.user.id
    assert ship.client.post(f'{ROOT}/drivers/quick', json=external()).status_code == 409
    assert ship.client.post(f'{ROOT}/drivers/quick', json={'name': 'Internal', 'affiliation': 'internal'}).status_code == 422


def test_quick_denies_directory_read_or_write_alone(ship):
    for permissions in [set(), {'shipping:directory:read'}, {'shipping:directory:write'}]:
        ship.ctx.auth_user.permissions = permissions
        assert ship.client.post(f'{ROOT}/drivers/quick', json=external()).status_code == 403


def test_workers_driver_first_then_name_and_tenant_isolation(ship):
    employee(ship, 'O1', 'A operator', 'operator')
    driver = employee(ship, 'D1', 'Z driver')
    foreign = employee(ship, 'F1', 'Foreign driver')
    foreign.organization_id = uuid4()
    ship.db.commit()
    workers = ship.client.get(f'{ROOT}/workers').json()
    assert [row['name'] for row in workers] == ['Z driver', 'A operator']
    assert workers[0]['worker_type'] == 'driver'
    assert ship.client.post(f'{ROOT}/drivers', json=dict(affiliation='internal', workforce_member_id=str(foreign.id))).status_code == 422
    saved = ship.client.post(f'{ROOT}/drivers/quick', json=external()).json()
    record = ship.db.get(Driver, UUID(saved['id']))
    record.organization_id = uuid4()
    ship.db.commit()
    assert ship.client.get(f"{ROOT}/drivers/options?selected_id={saved['id']}").json() == []
    # The same external identity belongs to a different tenant and must not leak a duplicate id.
    assert ship.client.post(f'{ROOT}/drivers/quick', json=external()).status_code == 201


def test_legacy_external_without_identity_can_be_edited(ship):
    row = Driver(organization_id=ship.org.id, name='Legacy', affiliation='external', created_by=ship.user.id, updated_by=ship.user.id)
    ship.db.add(row)
    ship.db.commit()
    response = ship.client.put(f'{ROOT}/drivers/{row.id}', json={'name': 'Legacy edited', 'affiliation': 'external', 'version': 1})
    assert response.status_code == 200 and response.json()['identity_no'] is None


def test_employee_identity_update_cannot_duplicate_an_existing_driver(ship):
    from app.workforce.application.services import WorkforceService
    from app.workforce.api.schemas import WorkforceMemberUpdate
    from fastapi import HTTPException
    worker = employee(ship, national_id='INTERNAL-ID')
    assert ship.client.post(f'{ROOT}/drivers', json=dict(affiliation='internal', workforce_member_id=str(worker.id))).status_code == 201
    saved = ship.client.post(f'{ROOT}/drivers', json=external()).json()
    with pytest.raises(HTTPException) as caught:
        WorkforceService(ship.db).update_workforce_member(worker.id, ship.org.id, WorkforceMemberUpdate(national_id='ID-001'))
    assert caught.value.status_code == 409
    assert caught.value.detail['existing_driver_id'] == saved['id']
