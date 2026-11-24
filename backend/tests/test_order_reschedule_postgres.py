"""Actual PostgreSQL row serialization against a concurrent completion."""
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import date, timedelta
from threading import Event
from uuid import uuid4
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from app.core.db import Base, engine
from app.core.tenancy import TenantContext
from app.main import app  # noqa: F401 -- register metadata and activity provider
from app.production.application.order_reschedule_service import OrderRescheduleService
from app.production.api.planning_schemas import RescheduleRequest
from app.production.domain.enums import ProductionOrderStatus as S
from app.production.domain.order_lifecycle import TransitionError
from app.production.infrastructure.models import ProductionOrder, WorkCenter

pytestmark=pytest.mark.skipif(os.environ.get('RUN_POSTGRES_TESTS')!='1',reason='Isolated PostgreSQL opt-in')


def test_completion_lock_prevents_a_stale_reschedule():
    schema='test_order_reschedule_'+uuid4().hex
    with engine.begin() as connection: connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated)
        org,user=uuid4(),uuid4()
        with isolated.begin() as connection:
            connection.execute(Base.metadata.tables['foundation_organizations'].insert().values(id=org,name='Synthetic',code=str(org),status='active',timezone='UTC',default_locale='en'))
            connection.execute(Base.metadata.tables['foundation_users'].insert().values(id=user,organization_id=org,email='synthetic@example.test',full_name='Scheduler',password_hash='unused',status='active',is_organization_root=False))
        with Session(isolated) as db:
            center=WorkCenter(organization_id=org,name='Line',code='RESCHEDULE'); db.add(center); db.flush()
            order=ProductionOrder(organization_id=org,production_order_number='PO-LOCK',work_center_id=center.id,product_type='film',planned_quantity=10,unit='kg',planned_start_date=date.today(),planned_end_date=date.today(),created_by_user_id=user)
            db.add(order); db.commit(); order_id=order.id
        requested=Event()
        def extend():
            with Session(isolated) as db:
                db.execute(sa.text("SET LOCAL lock_timeout='3s'"))
                requested.set()
                try:
                    OrderRescheduleService(db,TenantContext(user,org)).reschedule(order_id,RescheduleRequest(planned_end_date=date.today()+timedelta(days=3),reason='Material delayed'))
                except TransitionError as exc: return exc.code
                return 'incorrectly accepted'
        with Session(isolated) as blocker, ThreadPoolExecutor(max_workers=1) as pool:
            current=blocker.scalar(sa.select(ProductionOrder).where(ProductionOrder.id==order_id).with_for_update())
            current.status=S.COMPLETED; blocker.flush()
            future=pool.submit(extend)
            try:
                assert requested.wait(5)
                with pytest.raises(TimeoutError): future.result(timeout=.3)
            finally: blocker.commit()
            assert future.result(timeout=5)=='RESCHEDULE_NOT_ALLOWED'
        with Session(isolated) as db:
            assert db.get(ProductionOrder,order_id).planned_end_date==date.today()
            logs=Base.metadata.tables['foundation_activity_log']
            assert db.scalar(sa.select(sa.func.count()).select_from(logs).where(logs.c.action=='production_order.rescheduled'))==0
    finally:
        isolated.dispose()
        with engine.begin() as connection: connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
