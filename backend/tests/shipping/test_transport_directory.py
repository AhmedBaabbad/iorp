from types import SimpleNamespace
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select,func
from tests.shipping.test_shipments import ship, ROOT
from app.shipping.infrastructure.directory_models import Driver
from app.workforce.infrastructure.models import WorkforceMember

DIRECTORY='/api/v1/shipping/directory'

def add(ship,kind,**body):
    response=ship.client.post(f'{DIRECTORY}/{kind}',json=body)
    assert response.status_code==201,response.text
    return response.json()


def test_saved_external_and_oneoff_are_distinct_and_frozen(ship):
    driver=add(ship,'drivers',name='External',affiliation='external',phone='0551234567')
    shipment=ship.create(driver_id=driver['id'])
    assert shipment['driver_name']=='External' and shipment['driver_affiliation']=='external'
    assert ship.client.put(f"{DIRECTORY}/drivers/{driver['id']}",json=dict(name='Renamed',affiliation='external',version=1)).status_code==200
    edited=ship.client.patch(f"{ROOT}/{shipment['id']}",json=dict(notes='Only notes',driver_name='Spoof')).json()
    assert edited['driver_name']=='External'
    oneoff=ship.create(driver_name='One off',driver_affiliation='internal')
    assert oneoff['driver_id'] is None and oneoff['driver_affiliation']=='internal'
    assert ship.db.scalar(select(func.count()).select_from(Driver))==1


def test_internal_driver_requires_employee_but_no_login(ship):
    employee=WorkforceMember(organization_id=ship.org.id,employee_code='D1',full_name='Employee Driver',worker_type='logistics_coordinator',employment_type='employee')
    ship.db.add(employee);ship.db.commit()
    assert employee.user_id is None
    driver=add(ship,'drivers',name='Ignored',affiliation='internal',workforce_member_id=str(employee.id))
    assert driver['name']=='Employee Driver'
    assert ship.create(driver_id=driver['id'])['driver_affiliation']=='internal'
    assert ship.client.post(f'{DIRECTORY}/drivers',json=dict(name='Invalid',affiliation='internal')).status_code==422
    assert ship.client.post(f'{DIRECTORY}/drivers',json=dict(name='Invalid',affiliation='external',workforce_member_id=str(employee.id))).status_code==422
    from app.workforce.application.services import WorkforceService
    with pytest.raises(ValueError,match='transport directory'):
        WorkforceService(ship.db).delete_workforce_member(employee.id,ship.org.id)
    employee.status='inactive';ship.db.commit()
    assert ship.client.post(ROOT,json=ship.body(driver_id=driver['id'])).status_code==422


def test_classification_required_and_legacy_preserved(ship):
    assert ship.client.post(ROOT,json=ship.body(driver_name='Unknown')).status_code==422
    shipment=ship.create()
    from app.shipping.infrastructure.models import Shipment
    old=ship.db.get(Shipment,UUID(shipment['id']));old.driver_name='Legacy';ship.db.commit()
    response=ship.client.patch(f"{ROOT}/{shipment['id']}",json=dict(notes='Preserve legacy'))
    assert response.status_code==200 and response.json()['driver_affiliation'] is None
    assert ship.client.patch(f"{ROOT}/{shipment['id']}",json=dict(driver_name='New')).status_code==422


def test_unavailable_driver_and_cross_tenant_rejected(ship):
    driver=add(ship,'drivers',name='Driver',affiliation='external')
    row=ship.db.get(Driver,UUID(driver['id']));row.organization_id=uuid4();ship.db.commit()
    assert ship.client.post(ROOT,json=ship.body(driver_id=driver['id'])).status_code==422
    assert ship.client.get(f'{DIRECTORY}/drivers/options').json()==[]
    assert ship.client.put(f"{DIRECTORY}/drivers/{driver['id']}",json=dict(name='X',affiliation='external',version=1)).status_code==404


def test_version_and_permissions(ship):
    driver=add(ship,'drivers',name='Driver',affiliation='external')
    body=dict(name='Changed',affiliation='external',version=1,active=False)
    assert ship.client.put(f"{DIRECTORY}/drivers/{driver['id']}",json=body).status_code==200
    assert ship.client.put(f"{DIRECTORY}/drivers/{driver['id']}",json=body).status_code==409
    assert ship.client.post(ROOT,json=ship.body(driver_id=driver['id'])).status_code==422
    ship.ctx.auth_user.permissions.clear()
    assert ship.client.get(f'{DIRECTORY}/drivers').status_code==403
    assert ship.client.post(f'{DIRECTORY}/drivers',json=dict(name='D',affiliation='external')).status_code==403
