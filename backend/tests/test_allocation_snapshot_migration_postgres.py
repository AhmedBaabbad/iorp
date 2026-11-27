"""Allocation history survives a demand correction, backfilled on PostgreSQL 16."""
import importlib.util
import os
from pathlib import Path
from datetime import date
from uuid import uuid4
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.production.infrastructure.models import ProductionOrder, ProductionOrderItem, ProductionAllocation
from app.core.utils import utc_now
from tests.test_production_allocation_postgres import pg

pytestmark=pytest.mark.skipif(os.environ.get('RUN_POSTGRES_TESTS')!='1',reason='Requires explicit isolated PostgreSQL verification')


def test_active_and_released_snapshot_upgrade_downgrade_and_rerun(pg):
    isolated,ids=pg
    with Session(isolated) as db:
        orders=[]
        for n in range(3):
            o=ProductionOrder(organization_id=ids['org'],production_order_number=f'PO-SNAPSHOT-{n}',work_center_id=ids['center'],
                product_type='film',planned_quantity=10,unit='kg',planned_start_date=date.today(),planned_end_date=date.today())
            o.items=[ProductionOrderItem(line_no=1,target_spec_json={'color':'old','thickness':{'min':.7,'max':.75}},planned_quantity=10,unit='kg')]
            db.add(o);orders.append(o)
        db.flush()
        from app.production.infrastructure.models import ProductionDemandItem
        item=db.get(ProductionDemandItem,ids['item']);item.target_spec_json={'color':'new'}
        allocations=[]
        for n,o in enumerate(orders):
            a=ProductionAllocation(organization_id=ids['org'],production_order_id=o.id,production_demand_id=ids['demand'],
                production_demand_item_id=ids['item'],production_order_item_id=o.items[0].id if n!=2 else None,
                allocated_quantity=10,unit='kg',status='active' if n==0 else 'released',released_at=None if n==0 else utc_now())
            db.add(a);allocations.append(a)
        db.commit();identities=[a.id for a in allocations]
    spec=importlib.util.spec_from_file_location('allocation_snapshots',Path(__file__).parents[1]/'alembic/versions/f6a1b2p9_allocation_snapshots.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    with isolated.begin() as conn:
        conn.execute(sa.text('ALTER TABLE production_allocations DROP COLUMN target_spec_json_snapshot, DROP COLUMN product_type_snapshot'))
        conn.execute(sa.text('DROP INDEX ix_foundation_activity_record_history'))
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            rows=conn.execute(sa.text('SELECT id,target_spec_json_snapshot,product_type_snapshot,unit FROM production_allocations')).mappings().all()
            by_id={r['id']:r for r in rows}
            assert by_id[identities[0]]['target_spec_json_snapshot']=={'color':'new'}
            assert by_id[identities[1]]['target_spec_json_snapshot']=={'color':'old','thickness':{'min':.7,'max':.75}}
            assert by_id[identities[2]]['target_spec_json_snapshot']=={'color':'new'}
            assert all(r['unit']=='kg' and r['product_type_snapshot']=='film' for r in rows)
            migration.downgrade()
            assert 'target_spec_json_snapshot' not in {c['name'] for c in sa.inspect(conn).get_columns('production_allocations')}
            migration.upgrade()
