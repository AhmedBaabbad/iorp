from datetime import datetime, timezone, timedelta, date
from decimal import Decimal
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select, func
from app.core.interfaces.record_history import diff_fields, record_event
from app.core.interfaces.record_history import safe
from app.foundation.application.activity_archive import _purge
from app.foundation.infrastructure.models import TenantActivityLog
from app.production.infrastructure.models import ProductionAllocation, ProductionResultEntry, WasteRecord
from app.quality.infrastructure.models import QualityCheck
from app.quality.domain.enums import QualityCheckType
from tests.test_production_allocation_lifecycle import env, item_id, ROOT


def released(env):
    d=env.demand('50','50')
    po=env.order((item_id(d,0),'50'),(item_id(d,1),'50'))
    allocation=next(a for a in po['allocations'] if a['production_demand_item_id']==item_id(d))
    r=env.release(allocation['id'],'Correct specifications')
    assert r.status_code==200,r.text
    return d,po,allocation


def test_return_edit_and_reallocate_keeps_original_snapshot(env):
    from app.masterdata.infrastructure.models import Product, ProductProperty
    product=Product(organization_id=env.org.id,code='REWORK',key='film',name_ar='Film',name_en='Film',created_by_user_id=env.user.id)
    product.properties=[ProductProperty(line_no=1,key='thickness',name_ar='Thickness',name_en='Thickness',kind='number',allows_range=True)]
    env.db.add(product);env.db.commit()
    d,po,a=released(env)
    spec={'width':12,'color':'red','thickness':{'min':0.70,'max':0.75}}
    r=env.client.patch(f"{ROOT}/demands/{d['id']}/items/{item_id(d)}",json={'target_spec_json':spec,'required_quantity':'60'})
    assert r.status_code==200,r.text
    # The sibling remains allocated and unchanged, header remains locked.
    current=env.get(d['id'])
    assert current['status']=='partially_planned' and current['items'][1]['required_quantity']=='50.000'
    assert env.client.patch(f"{ROOT}/demands/{d['id']}",json={'notes':'header'}).status_code==409
    new=env.order((item_id(d),'60'))
    assert new['lines'][0]['target_spec_json']==spec
    old=env.client.get(f"{ROOT}/production-orders/{po['id']}").json()
    old_alloc=next(x for x in old['allocations'] if x['id']==a['id'])
    assert old_alloc['target_spec_json']=={'width':12} and old_alloc['unit']=='kg'
    logs=env.client.get(f"/api/v1/record-history/production_demand/{d['id']}").json()['items']
    change=next(x for x in logs if x['action']=='production_demand.item_updated')['details']['changes']
    assert {'field':'target_spec_json.color','old':None,'new':'red'} in change
    assert {'field':'target_spec_json.thickness','old':None,'new':{'min':.7,'max':.75}} in change
    for kind,identity in [('production_order',po['id']),('production_demand',d['id'])]:
        entries=env.client.get(f'/api/v1/record-history/{kind}/{identity}').json()['items']
        event=next(e for e in entries if e['action']=='production_allocation.released')
        assert event['actor_name']==env.user.full_name and event['details']['reason']=='Correct specifications'


def test_active_item_locked_history_item_not_deletable_and_add_allowed(env):
    d,po,a=released(env)
    assert env.client.patch(f"{ROOT}/demands/{d['id']}/items/{item_id(d,1)}",json={'notes':'no'}).json()['detail']['code']=='DEMAND_ITEM_ALLOCATED'
    assert env.client.delete(f"{ROOT}/demands/{d['id']}/items/{item_id(d)}").status_code==409
    r=env.client.post(f"{ROOT}/demands/{d['id']}/items",json={'product_type':'film','required_quantity':'10','unit':'kg'})
    assert r.status_code==201,r.text
    assert env.get(d['id'])['status']=='partially_planned'
    assert env.client.delete(f"{ROOT}/demands/{d['id']}/items/{r.json()['id']}").status_code==200


def test_changed_unit_does_not_relabel_returned_quantities(env):
    d,_,a=released(env)
    response=env.client.patch(f"{ROOT}/demands/{d['id']}/items/{item_id(d)}",json={'unit':'roll'})
    assert response.status_code==200,response.text
    current=env.get(d['id'])
    assert current['items'][0]['unit']=='roll'
    assert current['items'][0]['released_quantities_by_unit']=={'kg':'50.000'}
    assert current['released_quantities_by_unit']=={'kg':'50.000'}
    assert env.db.get(ProductionAllocation,UUID(a['id'])).unit=='kg'


@pytest.mark.parametrize('kind',['result','waste','check'])
def test_line_production_blocks_return(env,kind):
    d=env.demand('50','50');po=env.order((item_id(d),'50'),(item_id(d,1),'50'))
    a=po['allocations'][0]
    base=dict(organization_id=env.org.id,production_order_id=UUID(po['id']),production_order_item_id=UUID(a['production_order_item_id']))
    if kind=='result':
        row=ProductionResultEntry(**base,disposition='customer_good',quantity=1,unit='kg',counts_as_loss=False,created_by_user_id=env.user.id)
    elif kind=='waste':
        row=WasteRecord(**base,work_center_id=env.center.id,waste_date=date.today(),quantity_wasted=1,unit='kg',created_by_user_id=env.user.id)
    else:
        row=QualityCheck(**base,inspection_code='QC-REWORK',check_datetime=datetime.now(timezone.utc),check_type=QualityCheckType.IN_PROCESS_INSPECTION,qty_inspected=1,qty_accepted=1,qty_rejected=0,checked_by_user_id=env.user.id)
    env.db.add(row);env.db.commit()
    r=env.release(a['id'])
    assert r.status_code==409,r.text
    assert r.json()['detail']['code']=='ORDER_LINE_HAS_PRODUCTION'
    assert env.db.get(ProductionAllocation,UUID(a['id'])).status=='active'


def test_history_pagination_scope_permission_and_archive(env):
    d=env.demand();identity=UUID(d['id'])
    for n in range(4):
        record_event(env.db,env.org.id,'production_demand',identity,d['demand_number'],'production_demand.updated',env.ctx.tenant,
                     [dict(field='notes',old=str(n),new=str(n+1))])
    env.db.commit()
    endpoint=f'/api/v1/record-history/production_demand/{identity}'
    page=env.client.get(endpoint+'?page=2&page_size=2').json()
    assert page['total']>=6 and page['page']==2 and len(page['items'])==2
    assert env.client.get(endpoint.replace(str(identity),str(uuid4()))).status_code==404
    assert env.client.get(endpoint.replace('production_demand','unknown')).status_code==404
    # The same UUID in another tenant never leaks history.
    old=env.ctx.tenant
    from app.core.tenancy import TenantContext
    env.ctx.tenant=TenantContext(old.user_id,uuid4(),permissions=old.permissions)
    assert env.client.get(endpoint).status_code==404
    env.ctx.tenant=old
    env.ctx.auth_user.permissions=frozenset()
    assert env.client.get(endpoint).status_code==404
    env.ctx.auth_user.permissions=old.permissions
    entries=list(env.db.scalars(select(TenantActivityLog).where(TenantActivityLog.entity_id==identity)))
    before=datetime(2020,1,1,tzinfo=timezone.utc)
    for e in entries:e.created_at=before
    env.db.commit()
    _purge(env.db,env.org.id,before,before+timedelta(days=32));env.db.commit()
    assert env.client.get(endpoint).json()['total']==len(entries)


def test_diff_and_strict_failure_roll_back_item_and_history(env,monkeypatch):
    assert diff_fields({'qty':Decimal('1.250'),'password':'old'},{'qty':Decimal('2.500'),'password':'new'},['qty','password'])==[dict(field='qty',old='1.250',new='2.500')]
    assert safe({'nested':{'api_key':'not-for-history','private_key':'not-for-history','value':Decimal('1.25')}})=={'nested':{'value':'1.25'}}
    d,_,_=released(env)
    before=env.db.scalar(select(func.count()).select_from(TenantActivityLog))
    def broken(*args,**kwargs):raise RuntimeError('history unavailable')
    from app.core.interfaces.activity_log import get_registered_activity_logger
    monkeypatch.setattr(get_registered_activity_logger(), 'log_activity_strict', broken)
    with pytest.raises(RuntimeError,match='history unavailable'):
        env.client.patch(f"{ROOT}/demands/{d['id']}/items/{item_id(d)}",json={'notes':'not committed'})
    env.db.expire_all()
    assert env.get(d['id'])['items'][0]['notes'] is None
    assert env.db.scalar(select(func.count()).select_from(TenantActivityLog))==before


@pytest.mark.parametrize('operation',['demand_create','header','status','demand_delete','item_add','item_delete',
                                      'allocation_create','allocation_change','allocation_return','order_create','order_update','order_cancel'])
def test_every_mutation_rolls_back_when_required_history_fails(env,monkeypatch,operation):
    from app.production.infrastructure.models import ProductionDemand,ProductionDemandItem,ProductionOrder
    from app.production.application.services import ProductionOrderService
    from app.production.api.schemas import ProductionOrderCreate
    from app.core.tenancy import TenantContext
    permissions=env.ctx.tenant.permissions|{'production:demands:delete'}
    env.ctx.auth_user.permissions=permissions
    env.ctx.tenant=TenantContext(env.user.id,env.org.id,permissions=permissions)
    d=env.demand('50','50')
    po=None
    if operation.startswith('allocation_') and operation!='allocation_create' or operation in ('order_update','order_cancel'):
        po=env.order((item_id(d),'50'),(item_id(d,1),'50'))
    if operation=='demand_delete':
        assert env.client.post(f"{ROOT}/demands/{d['id']}/status",json={'status':'draft'}).status_code==200
    def state():
        return (
            [(r.id,r.status,r.notes) for r in env.db.scalars(select(ProductionDemand).order_by(ProductionDemand.id))],
            [(r.id,r.required_quantity,r.target_spec_json,r.notes) for r in env.db.scalars(select(ProductionDemandItem).order_by(ProductionDemandItem.id))],
            [(r.id,r.status,r.planned_quantity,r.notes) for r in env.db.scalars(select(ProductionOrder).order_by(ProductionOrder.id))],
            [(r.id,r.status,r.allocated_quantity) for r in env.db.scalars(select(ProductionAllocation).order_by(ProductionAllocation.id))],
            env.db.scalar(select(func.count()).select_from(TenantActivityLog)))
    before=state()
    def broken(*args,**kwargs):raise RuntimeError('required history unavailable')
    from app.core.interfaces.activity_log import get_registered_activity_logger
    monkeypatch.setattr(get_registered_activity_logger(), 'log_activity_strict', broken)
    item_url=f"{ROOT}/demands/{d['id']}/items"
    calls={
        'demand_create':lambda:env.client.post(f'{ROOT}/demands',json={'customer_id':str(env.customer.id),'items':[{'product_type':'film','required_quantity':'10','unit':'kg'}]}),
        'header':lambda:env.client.patch(f"{ROOT}/demands/{d['id']}",json={'notes':'rollback'}),
        'status':lambda:env.client.post(f"{ROOT}/demands/{d['id']}/status",json={'status':'draft','reason':'Changed plan'}),
        'demand_delete':lambda:env.client.delete(f"{ROOT}/demands/{d['id']}"),
        'item_add':lambda:env.client.post(item_url,json={'product_type':'film','required_quantity':'10','unit':'kg'}),
        'item_delete':lambda:env.client.delete(item_url+'/'+item_id(d)),
        'allocation_create':lambda:env.allocate((item_id(d),'10')),
        'allocation_change':lambda:env.client.patch(f"{ROOT}/allocations/{po['allocations'][0]['id']}",json={'allocated_quantity':'20'}),
        'allocation_return':lambda:env.release(po['allocations'][0]['id']),
        'order_create':lambda:ProductionOrderService(env.db).create_production_order(env.ctx.tenant,ProductionOrderCreate(work_center_id=env.center.id,product_type='film',planned_quantity='10',unit='kg',planned_start_date='2030-01-01',planned_end_date='2030-01-02')),
        'order_update':lambda:env.client.patch(f"{ROOT}/production-orders/{po['id']}",json={'notes':'rollback'}),
        'order_cancel':lambda:env.cancel(po['id']),
    }
    with pytest.raises(RuntimeError,match='required history unavailable'):
        calls[operation]()
    env.db.expire_all()
    assert state()==before
