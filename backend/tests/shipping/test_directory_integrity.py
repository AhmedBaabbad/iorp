from uuid import UUID
from sqlalchemy import event
from tests.shipping.test_shipments import ship, ROOT  # noqa: F401
from tests.shipping.test_transport_directory import add, DIRECTORY
from tests.shipping.test_hr_drivers import employee
from app.shipping.infrastructure.directory_models import Driver


def test_saved_driver_invalid_phone_is_not_copied_but_manual_phone_is_rejected(ship):
    saved = add(ship,'drivers',name='Driver',affiliation='external',phone='0551234567')
    assert saved['phone']=='+966551234567'
    row=ship.db.get(Driver,UUID(saved['id']))
    row.phone='legacy invalid'
    ship.db.commit()
    assert ship.create(driver_id=saved['id'])['driver_phone'] is None
    bad=ship.client.post(ROOT,json=ship.body(driver_name='Manual',driver_affiliation='external',driver_phone='invalid'))
    assert bad.status_code==400 and bad.json()['detail']['code']=='PHONE_INVALID'
    for kind,values in [('drivers',dict(name='Bad',affiliation='external',identity_no='NEW')),('carriers',dict(name='Bad'))]:
        response=ship.client.post(f'{DIRECTORY}/{kind}',json={**values,'phone':'invalid'})
        assert response.status_code==422 and response.json()['detail']=='PHONE_INVALID'
    carrier=add(ship,'carriers',name='Carrier',phone='٠٥٥١٢٣٤٥٦٧')
    assert carrier['phone']=='+966551234567'


def test_driver_display_sort_search_and_batch_queries(ship):
    worker=employee(ship,name='Z employee',phone='+966551234567',national_id='INTERNAL-ID')
    add(ship,'drivers',affiliation='internal',workforce_member_id=str(worker.id))
    add(ship,'drivers',name='A external',affiliation='external',phone='0557654321')
    queries=[]
    def capture(conn,cursor,statement,parameters,context,executemany):
        if 'FROM workforce_members' in statement:queries.append(statement)
    event.listen(ship.db.get_bind(),'before_cursor_execute',capture)
    try:
        response=ship.client.get(f'{DIRECTORY}/drivers')
    finally:event.remove(ship.db.get_bind(),'before_cursor_execute',capture)
    assert [r['name'] for r in response.json()['items']]==['A external','Z employee']
    assert len(queries)==1
    for search in ('INTERNAL-ID','551234567','0551','Z employee'):
        result=ship.client.get(f'{DIRECTORY}/drivers',params={'search':search}).json()
        assert [r['name'] for r in result['items']]==['Z employee']
    assert ship.client.get(f'{DIRECTORY}/drivers',params={'search':'557654321'}).json()['total']==1
