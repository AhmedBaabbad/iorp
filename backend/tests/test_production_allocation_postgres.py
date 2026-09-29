"""Real PostgreSQL locking/migration checks in disposable isolated schemas.

Run with RUN_POSTGRES_TESTS=1. Never writes to application tables.
"""
import importlib.util
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, time
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from uuid import uuid4
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.core.db import Base, engine
from app.core.tenancy import TenantContext
from app.foundation.infrastructure.models import Organization, User
from app.commercial.infrastructure.models import Customer
from app.production.infrastructure.models import WorkCenter, ShiftDefinition, ProductionOrder, ProductionDemand, ProductionDemandItem, ProductionAllocation
from app.production.api.planning_schemas import PlanningOrderCreate
from app.production.application.planning_order_service import PlanningOrderService
from app.production.domain.compatibility import AllocationError
from app.production.domain.order_lifecycle import TransitionError

pytestmark = pytest.mark.skipif(os.environ.get("RUN_POSTGRES_TESTS") != "1", reason="Requires explicit isolated PostgreSQL verification")


@pytest.fixture
def pg():
    name = "test_allocation_" + uuid4().hex
    with engine.begin() as conn:
        conn.execute(sa.text(f'CREATE SCHEMA "{name}"'))
    isolated = sa.create_engine(engine.url, connect_args={"options": f"-csearch_path={name}"})
    try:
        Base.metadata.create_all(isolated)
        with Session(isolated) as db:
            org = Organization(name="Allocation test", code="test", timezone="UTC")
            db.add(org); db.flush()
            user = User(organization_id=org.id, full_name="Test", email="test@example.invalid", password_hash="unused")
            customer = Customer(organization_id=org.id, customer_code="C", name="Test")
            wc = WorkCenter(organization_id=org.id, code="WC", name="Line")
            db.add_all([user, customer, wc]); db.flush()
            demand = ProductionDemand(organization_id=org.id, customer_id=customer.id, demand_number="PD-TEST", status="ready_for_planning")
            demand.items = [ProductionDemandItem(line_no=1, product_type="film", unit="kg", required_quantity=1000)]
            db.add(demand); db.commit()
            ids = dict(org=org.id, user=user.id, center=wc.id, demand=demand.id, item=demand.items[0].id)
        yield isolated, ids
    finally:
        isolated.dispose()
        # Schema name is generated here, never read from external input.
        with engine.begin() as conn:
            conn.execute(sa.text(f'DROP SCHEMA "{name}" CASCADE'))


def test_t12_t13_real_concurrent_allocation(pg):
    isolated, ids = pg
    barrier = Barrier(2)
    payload = PlanningOrderCreate(allocations=[{"production_demand_item_id": ids["item"], "allocated_quantity": "600"}], work_center_id=ids["center"], planned_start_date=date.today(), planned_end_date=date.today())
    def allocate():
        with Session(isolated) as db:
            barrier.wait(timeout=10)
            try:
                order = PlanningOrderService(db, TenantContext(ids["user"], ids["org"])).create_order_from_planning(payload)
                return 201, str(order.id)
            except (AllocationError, TransitionError) as exc:
                return exc.status, exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: allocate(), range(2)))
    assert sorted(r[0] for r in results) == [201, 409]
    with Session(isolated) as db:
        assert db.scalar(sa.select(sa.func.count()).select_from(ProductionOrder)) == 1
        assert db.scalar(sa.select(sa.func.sum(ProductionAllocation.allocated_quantity))) == Decimal(600)
        assert db.get(ProductionDemand, ids["demand"]).status == "partially_planned"


def test_t32_t33_migration_preserves_references_and_downgrades(pg):
    isolated, ids = pg
    path = Path(__file__).parents[1] / "alembic/versions/2026_09_15_1000_f6a1b2g5_production_allocations.py"
    spec = importlib.util.spec_from_file_location("allocation_migration", path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    # Build the previous order-header shape through the actual downgrade.
    with isolated.begin() as conn:
        conn.execute(sa.text("CREATE TYPE production_order_priority AS ENUM ('urgent','normal','low')"))
        with Operations.context(MigrationContext.configure(conn)):
            migration.downgrade()
        shift_id, order_id, reference = uuid4(), uuid4(), uuid4()
        conn.execute(sa.text("INSERT INTO production_shift_definitions (id, organization_id, code, name, shift_type, start_time, end_time, duration_hours, crosses_midnight, status, created_at, updated_at) VALUES (:id,:org,'SD','Shift','morning','07:00','15:00',8,false,'active',now(),now())"), dict(id=shift_id, org=ids["org"]))
        conn.execute(sa.text("INSERT INTO production_orders (id, organization_id, production_order_number, work_center_id, commercial_order_id, shift_definition_id, product_type, planned_quantity, unit, priority, status, planned_start_date, planned_end_date, created_by_user_id, created_at, updated_at) VALUES (:id,:org,'PO-HISTORY',:wc,:ref,:shift,'film',100,'kg','normal','draft',CURRENT_DATE,CURRENT_DATE,:user,now(),now())"), dict(id=order_id, org=ids["org"], wc=ids["center"], ref=reference, shift=shift_id, user=ids["user"]))
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
        row = conn.execute(sa.text("SELECT legacy_commercial_order_ref, legacy_shift_ref FROM production_orders")).one()
        assert row[0]["commercial_order_id"] == str(reference)
        assert row[1]["shift_definition_id"] == str(shift_id)
        with Operations.context(MigrationContext.configure(conn)):
            migration.downgrade()
        row = conn.execute(sa.text("SELECT commercial_order_id, shift_definition_id FROM production_orders")).one()
        assert row == (reference, shift_id)


def _concurrently(fn, n=2):
    barrier = Barrier(n)
    def run(_):
        barrier.wait(timeout=10)
        return fn()
    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(run, range(n)))


def test_prod_plan_003_t21_concurrent_remaining_quantity(pg):
    """Remaining 400 after a 600 allocation: two planners race for it, only one wins."""
    isolated, ids = pg
    def payload(qty):
        return PlanningOrderCreate(allocations=[{"production_demand_item_id": ids["item"], "allocated_quantity": qty}], work_center_id=ids["center"], planned_start_date=date.today(), planned_end_date=date.today())
    with Session(isolated) as db:
        PlanningOrderService(db, TenantContext(ids["user"], ids["org"])).create_order_from_planning(payload("600"))
    def allocate():
        with Session(isolated) as db:
            try:
                PlanningOrderService(db, TenantContext(ids["user"], ids["org"])).create_order_from_planning(payload("400"))
                return 201, None
            except (AllocationError, TransitionError) as exc:
                return exc.status, exc.code
    results = sorted(_concurrently(allocate))
    assert results == [(201, None), (409, "ALLOCATION_QUANTITY_CONFLICT")]
    with Session(isolated) as db:
        assert db.scalar(sa.select(sa.func.sum(ProductionAllocation.allocated_quantity)).where(ProductionAllocation.status == "active")) == Decimal(1000)
        assert db.get(ProductionDemand, ids["demand"]).status == "planned"


def test_prod_plan_003_concurrent_cancel_releases_once(pg):
    from app.production.application.order_status_service import OrderStatusService
    isolated, ids = pg
    with Session(isolated) as db:
        order = PlanningOrderService(db, TenantContext(ids["user"], ids["org"])).create_order_from_planning(PlanningOrderCreate(
            allocations=[{"production_demand_item_id": ids["item"], "allocated_quantity": "600"}], work_center_id=ids["center"], planned_start_date=date.today(), planned_end_date=date.today()))
        order_id = order.id
    def cancel():
        with Session(isolated) as db:
            try:
                OrderStatusService(db, TenantContext(ids["user"], ids["org"])).transition(order_id, "cancel", can=lambda code: True, reason="race")
                return 200
            except (AllocationError, TransitionError) as exc:
                return exc.status
    assert sorted(_concurrently(cancel)) == [200, 409]
    with Session(isolated) as db:
        assert db.get(ProductionDemand, ids["demand"]).status == "ready_for_planning"
        assert db.scalar(sa.select(sa.func.count()).select_from(ProductionAllocation).where(ProductionAllocation.status == "released")) == 1


def test_prod_plan_003_migration_marks_existing_allocations_active(pg):
    isolated, ids = pg
    path = Path(__file__).parents[1] / "alembic/versions/2026_09_28_0900_f6a1b2g8_allocation_lifecycle.py"
    spec = importlib.util.spec_from_file_location("lifecycle_migration", path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    with isolated.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            migration.downgrade()
        order_id = uuid4()
        conn.execute(sa.text("INSERT INTO production_orders (id, organization_id, production_order_number, work_center_id, product_type, planned_quantity, unit, priority, status, planned_start_date, planned_end_date, created_by_user_id, created_at, updated_at) VALUES (:id,:org,'PO-OLD',:wc,'film',100,'kg','normal','draft',CURRENT_DATE,CURRENT_DATE,:user,now(),now())"), dict(id=order_id, org=ids["org"], wc=ids["center"], user=ids["user"]))
        conn.execute(sa.text("INSERT INTO production_allocations (id, organization_id, production_order_id, production_demand_id, production_demand_item_id, allocated_quantity, unit, created_at, updated_at) VALUES (:id,:org,:po,:d,:i,100,'kg',now(),now())"), dict(id=uuid4(), org=ids["org"], po=order_id, d=ids["demand"], i=ids["item"]))
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
        assert conn.execute(sa.text("SELECT status, released_at, released_by_user_id, release_reason FROM production_allocations")).one() == ("active", None, None, None)
        conn.execute(sa.text("UPDATE production_allocations SET status='released', released_at=now()"))
        with pytest.raises(RuntimeError), Operations.context(MigrationContext.configure(conn)):
            migration.downgrade()


def _order_for_race(isolated, ids):
    with Session(isolated) as db:
        return PlanningOrderService(db, TenantContext(ids["user"], ids["org"])).create_order_from_planning(PlanningOrderCreate(
            allocations=[{"production_demand_item_id": ids["item"], "allocated_quantity": "600"}], work_center_id=ids["center"],
            planned_start_date=date.today(), planned_end_date=date.today())).id


def _cancel_during(isolated, ids, order_id):
    """Start a real cancellation on another connection; wait until it is blocked on a lock or finished."""
    import time
    from app.production.application.order_status_service import OrderStatusService
    def cancel():
        with Session(isolated) as db:
            try:
                OrderStatusService(db, TenantContext(ids["user"], ids["org"])).transition(order_id, "cancel", can=lambda code: True, reason="race")
                return "cancelled"
            except (AllocationError, TransitionError) as exc:
                return exc.code
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(cancel)
    deadline = time.monotonic() + 10
    with isolated.connect() as probe:
        while not future.done() and time.monotonic() < deadline:
            if probe.execute(sa.text("SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock' AND pid <> pg_backend_pid()")).scalar():
                break
            time.sleep(0.05)
    return pool, future


def test_prod_plan_003_order_edit_cannot_interleave_with_cancel(pg):
    """An order edit that holds the row must not lose or corrupt a concurrent cancellation (review H-1).

    Status itself can no longer be PATCHed; the edit still locks the row, so the cancel waits for it.
    """
    from app.production.application.services import ProductionOrderService
    from app.production.api.schemas import ProductionOrderUpdate
    isolated, ids = pg
    order_id = _order_for_race(isolated, ids)
    tenant = TenantContext(ids["user"], ids["org"])
    race = {}
    with Session(isolated) as db:
        svc = ProductionOrderService(db)
        original = svc.production_orders.get_by_id_for_update
        def read_then_race(org, oid):
            row = original(org, oid)
            race["pool"], race["future"] = _cancel_during(isolated, ids, oid)
            return row
        svc.production_orders.get_by_id_for_update = read_then_race
        svc.update_production_order(tenant, order_id, ProductionOrderUpdate(notes="edited while cancelling"))
    outcome = race["future"].result(timeout=20); race["pool"].shutdown()
    with Session(isolated) as db:
        order = db.get(ProductionOrder, order_id)
        statuses = [a.status for a in db.scalars(sa.select(ProductionAllocation))]
    # The cancel waited for the edit, then went through on the fresh row.
    assert outcome == "cancelled"
    assert order.status == "cancelled" and order.notes == "edited while cancelling" and statuses == ["released"]


def test_prod_plan_003_run_start_cannot_interleave_with_cancel(pg):
    """A run start that has checked the order must block cancellation until it commits (review H-2)."""
    from app.production.application.execution_service import ExecutionService
    from app.production.infrastructure.execution_models import ProductionRun
    isolated, ids = pg
    order_id = _order_for_race(isolated, ids)
    tenant = TenantContext(ids["user"], ids["org"])
    with Session(isolated) as db:
        run = ProductionRun(organization_id=ids["org"], production_order_id=order_id, work_center_id=ids["center"], run_date=date.today(), status="planned", created_by_user_id=ids["user"])
        db.add(run); db.commit(); run_id = run.id
    race = {}
    with Session(isolated) as db:
        ex = ExecutionService(db, tenant)
        get = ex.get
        def get_then_race(model, record_id, lock=False):
            row = get(model, record_id, lock=lock)
            if model is ProductionOrder:
                race["pool"], race["future"] = _cancel_during(isolated, ids, record_id)
            return row
        ex.get = get_then_race
        ex.transition(run_id, "start")
        db.commit()
    outcome = race["future"].result(timeout=20); race["pool"].shutdown()
    with Session(isolated) as db:
        order = db.get(ProductionOrder, order_id)
        statuses = [a.status for a in db.scalars(sa.select(ProductionAllocation))]
    assert outcome == "ORDER_EXECUTION_STARTED"
    assert order.status != "cancelled" and statuses == ["active"]


def test_order_lines_migration_backfills_and_guards_downgrade(pg):
    isolated, ids = pg
    path = Path(__file__).parents[1] / "alembic/versions/2026_09_29_0900_f6a1b2g9_order_spec_lines.py"
    spec = importlib.util.spec_from_file_location("order_lines_migration", path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    with isolated.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            migration.downgrade()
        conn.execute(sa.text("UPDATE production_demand_items SET target_spec_json = CAST(:s AS json)"), dict(s='{"width_mm": 20, "color": "red"}'))
        second = uuid4()
        conn.execute(sa.text("INSERT INTO production_demand_items (id, production_demand_id, line_no, product_type, required_quantity, unit, target_spec_json, created_at, updated_at) VALUES (:id,:d,2,'film',500,'kg',CAST(:s AS json),now(),now())"),
                     dict(id=second, d=ids["demand"], s='{"width_mm": 10, "color": "red"}'))
        order_id = uuid4()
        conn.execute(sa.text("INSERT INTO production_orders (id, organization_id, production_order_number, work_center_id, product_type, planned_quantity, unit, priority, status, planned_start_date, planned_end_date, created_by_user_id, created_at, updated_at) VALUES (:id,:org,'PO-OLD',:wc,'film',300,'kg','normal','draft',CURRENT_DATE,CURRENT_DATE,:user,now(),now())"),
                     dict(id=order_id, org=ids["org"], wc=ids["center"], user=ids["user"]))
        for item, qty in ((ids["item"], 100), (second, 200)):
            conn.execute(sa.text("INSERT INTO production_allocations (id, organization_id, production_order_id, production_demand_id, production_demand_item_id, allocated_quantity, unit, status, created_at, updated_at) VALUES (:id,:org,:po,:d,:i,:q,'kg','active',now(),now())"),
                         dict(id=uuid4(), org=ids["org"], po=order_id, d=ids["demand"], i=item, q=qty))
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
        lines = conn.execute(sa.text("SELECT line_no, planned_quantity, target_spec_json->>'width_mm' FROM production_order_items WHERE production_order_id = :o ORDER BY line_no"), dict(o=order_id)).all()
        assert lines == [(1, Decimal(200), "10"), (2, Decimal(100), "20")]
        assert conn.execute(sa.text("SELECT count(*) FROM production_allocations WHERE production_order_item_id IS NULL")).scalar() == 0
        # Released history may repeat a demand item in the same order once upgraded ...
        conn.execute(sa.text("UPDATE production_allocations SET status='released', released_at=now() WHERE production_demand_item_id = :i"), dict(i=second))
        conn.execute(sa.text("INSERT INTO production_allocations (id, organization_id, production_order_id, production_demand_id, production_demand_item_id, allocated_quantity, unit, status, created_at, updated_at) VALUES (:id,:org,:po,:d,:i,50,'kg','active',now(),now())"),
                     dict(id=uuid4(), org=ids["org"], po=order_id, d=ids["demand"], i=second))
        # ... but two ACTIVE rows for the same item and order are rejected.
        with pytest.raises(sa.exc.IntegrityError), conn.begin_nested():
            conn.execute(sa.text("INSERT INTO production_allocations (id, organization_id, production_order_id, production_demand_id, production_demand_item_id, allocated_quantity, unit, status, created_at, updated_at) VALUES (:id,:org,:po,:d,:i,1,'kg','active',now(),now())"),
                         dict(id=uuid4(), org=ids["org"], po=order_id, d=ids["demand"], i=second))
        # Downgrading would collapse that history, so it is refused.
        with pytest.raises(RuntimeError), Operations.context(MigrationContext.configure(conn)):
            migration.downgrade()


def test_order_status_concurrent_transitions_apply_once(pg):
    """Two users press the same button on the same version: one wins, the other is told to refresh."""
    from app.production.application.order_status_service import OrderStatusService
    isolated, ids = pg
    order_id = _order_for_race(isolated, ids)
    def release():
        with Session(isolated) as db:
            try:
                OrderStatusService(db, TenantContext(ids["user"], ids["org"])).transition(order_id, "release", can=lambda code: True, expected_version=1)
                return "released"
            except TransitionError as exc:
                return exc.code
    assert sorted(_concurrently(release)) == ["ORDER_STATUS_CHANGED", "released"]
    with Session(isolated) as db:
        order = db.get(ProductionOrder, order_id)
        history = db.scalar(sa.text("SELECT count(*) FROM production_order_status_history WHERE production_order_id = :o"), dict(o=order_id))
    assert order.status == "released" and order.status_version == 2 and history == 1
