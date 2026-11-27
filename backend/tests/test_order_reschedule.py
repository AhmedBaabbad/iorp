from datetime import date, timedelta
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from app.core.db import Base
from app.production.application.order_reschedule_service import OrderRescheduleService
from app.production.domain.enums import ProductionOrderStatus as S
from app.production.infrastructure.models import ProductionOrder
from app.production.api.planning_schemas import RescheduleRequest
from tests.test_production_order_status import env, ROOT


def schedule(env, order, **changes):
    return env.client.post(f"{ROOT}/production-orders/{order['id']}/reschedule", json={
        "planned_end_date": str(date.fromisoformat(order['planned_end_date']) + timedelta(days=5)), "reason": "Delayed material arrival", **changes})


def events(env, order):
    table = Base.metadata.tables["foundation_activity_log"]
    return env.db.execute(select(table).where(table.c.entity_id == UUID(order['id']), table.c.action == "production_order.rescheduled")).mappings().all()


def test_reschedule_updates_flags_and_audits_actor_old_new_dates_and_reason(env):
    today = date.today()
    order = env.order(start=today-timedelta(days=4), end=today-timedelta(days=2))
    response = schedule(env, order, planned_start_date=str(today), planned_end_date=str(today+timedelta(days=5)), reason="  Material delayed  ")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['status'] == order['status'] and not data['lifecycle']['start_overdue'] and not data['lifecycle']['finish_overdue']
    assert data['lifecycle']['actual_start_at'] is None
    entry, = events(env, order)
    assert entry['actor_id'] == env.user.id and entry['actor_name'] == env.user.full_name
    assert entry['details']['schema_version'] == 1 and entry['details']['reason'] == 'Material delayed'
    assert entry['details']['related'] == dict(old_start=order['planned_start_date'], new_start=str(today), old_end=order['planned_end_date'], new_end=str(today+timedelta(days=5)))
    assert data['reschedule_history'][0]['reason'] == 'Material delayed'


@pytest.mark.parametrize('state', ['completed','closed','cancelled'])
def test_finished_orders_rejected_for_post_and_patch(env, state):
    order = env.order(); env.force(order['id'], S(state))
    response = schedule(env, order)
    assert response.status_code == 409 and response.json()['detail']['code'] == 'RESCHEDULE_NOT_ALLOWED'
    response = env.client.patch(f"{ROOT}/production-orders/{order['id']}", json={'planned_end_date':str(date.today()+timedelta(days=10))})
    assert response.status_code == 409 and response.json()['detail']['code'] == 'RESCHEDULE_NOT_ALLOWED'
    assert events(env, order) == []


@pytest.mark.parametrize('state,actual', [('in_progress',False),('on_hold',False),('released',True),('draft',True)])
def test_started_order_keeps_start_but_can_extend_end(env, state, actual):
    from app.core.utils import utc_now
    order = env.order(); env.force(order['id'], S(state))
    if actual:
        env.db.get(ProductionOrder, UUID(order['id'])).actual_start_at = utc_now(); env.db.commit()
    new_start = str(date.fromisoformat(order['planned_start_date'])+timedelta(days=1))
    response = schedule(env, order, planned_start_date=new_start)
    assert response.status_code == 409 and response.json()['detail']['code'] == 'PLANNED_START_LOCKED'
    response = env.client.patch(f"{ROOT}/production-orders/{order['id']}", json={'planned_start_date':new_start})
    assert response.status_code == 409 and response.json()['detail']['code'] == 'PLANNED_START_LOCKED'
    response = schedule(env, order)
    assert response.status_code == 200 and response.json()['planned_start_date'] == order['planned_start_date']


@pytest.mark.parametrize('reason', [None, '', '   ', 'ab', 'x'*501])
def test_reason_required_trimmed_and_bounded(env, reason):
    order = env.order()
    assert schedule(env, order, reason=reason).status_code == 422
    assert events(env, order) == []


@pytest.mark.parametrize('reason', ['abc','x'*500])
def test_reason_boundaries_are_accepted(env, reason):
    assert schedule(env, env.order(), reason=reason).status_code == 200


def test_no_change_and_invalid_range(env):
    order = env.order()
    unchanged = schedule(env, order, planned_end_date=order['planned_end_date'])
    assert unchanged.status_code == 400 and unchanged.json()['detail']['code'] == 'NOTHING_CHANGED'
    response = schedule(env, order, planned_end_date=str(date.fromisoformat(order['planned_start_date'])-timedelta(days=1)))
    assert response.status_code == 400 and response.json()['detail']['code'] == 'INVALID_PLANNED_DATES'
    assert events(env, order) == []


def test_patch_date_change_has_same_audit_and_noop_has_none(env):
    order = env.order()
    response = env.client.patch(f"{ROOT}/production-orders/{order['id']}",json={'planned_end_date':str(date.today()+timedelta(days=12))})
    assert response.status_code == 200, response.text
    entry, = events(env, order)
    assert entry['details']['reason'] is None and entry['details']['related']['old_end'] == order['planned_end_date']
    assert entry['details']['related']['new_end'] == response.json()['planned_end_date']
    env.client.patch(f"{ROOT}/production-orders/{order['id']}",json={'planned_end_date':response.json()['planned_end_date'], 'notes':'No further schedule change'})
    assert len(events(env, order)) == 1


def test_permission_tenant_and_missing_order(env):
    order = env.order()
    env.ctx.auth_user.permissions.discard('production:production_orders:update')
    assert schedule(env, order).status_code == 403
    env.ctx.auth_user.permissions.add('production:production_orders:update')
    assert schedule(env, dict(order,id=str(uuid4()))).status_code == 404
    old_org = env.ctx.tenant.organization_id
    from dataclasses import replace
    env.ctx.tenant = replace(env.ctx.tenant,organization_id=uuid4())
    assert schedule(env, order).status_code == 404
    env.ctx.tenant = replace(env.ctx.tenant,organization_id=old_org)
    assert events(env, order) == []


@pytest.mark.parametrize('path',['post','patch'])
def test_required_audit_failure_rolls_back_date_change(env, monkeypatch, path):
    order = env.order()
    class BrokenLogger:
        def log_activity_strict(self,*args,**kwargs): raise RuntimeError('audit unavailable')
    monkeypatch.setattr('app.core.interfaces.record_history.get_registered_activity_logger',lambda:BrokenLogger())
    with pytest.raises(RuntimeError,match='audit unavailable'):
        if path=='post':
            OrderRescheduleService(env.db,env.ctx.tenant).reschedule(UUID(order['id']),RescheduleRequest(planned_end_date=date.today()+timedelta(days=20),reason='New material arrival'))
        else:
            from app.production.application.services import ProductionOrderService
            from app.production.api.schemas import ProductionOrderUpdate
            ProductionOrderService(env.db).update_production_order(env.ctx.tenant,UUID(order['id']),ProductionOrderUpdate(planned_end_date=date.today()+timedelta(days=20)))
    env.db.expire_all()
    assert str(env.db.get(ProductionOrder,UUID(order['id'])).planned_end_date) == order['planned_end_date']
    assert events(env,order) == []


def test_orders_update_is_sufficient_without_activity_log_read_permission(env):
    order=env.order()
    env.ctx.auth_user.permissions={'production:production_orders:update'}
    assert schedule(env,order).status_code==200


def test_service_uses_tenant_scoped_row_lock(env, monkeypatch):
    order = env.order(); queries=[]
    original=env.db.scalar
    def scalar(statement,*args,**kwargs):
        queries.append(str(statement.compile(dialect=postgresql.dialect())))
        return original(statement,*args,**kwargs)
    monkeypatch.setattr(env.db,'scalar',scalar)
    OrderRescheduleService(env.db,env.ctx.tenant).reschedule(UUID(order['id']),RescheduleRequest(planned_end_date=date.today()+timedelta(days=20),reason='New material arrival'))
    assert 'FOR UPDATE' in queries[0] and 'organization_id' in queries[0]
