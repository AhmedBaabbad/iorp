"""One transactional normalization across production tables; PostgreSQL 16 opt-in."""
import importlib.util
import logging
import os
from pathlib import Path
from uuid import uuid4
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.orm import Session
from app.core.db import Base, engine
from app.core.tenancy import TenantContext
from app.main import app  # noqa: F401 -- register metadata
from app.production.application.planning_order_service import PlanningOrderService
from app.production.domain.compatibility import DemandItemCompatibilityChecker
from app.production.infrastructure.models import ProductionDemand, ProductionDemandItem, ProductionOrder, WorkCenter

pytestmark = pytest.mark.skipif(os.environ.get("RUN_POSTGRES_TESTS") != "1", reason="Isolated PostgreSQL opt-in")


@pytest.fixture
def isolated():
    name = "test_production_units_" + uuid4().hex
    with engine.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{name}"'))
    isolated_engine = sa.create_engine(engine.url, connect_args={"options": f"-csearch_path={name}"})
    try:
        Base.metadata.create_all(isolated_engine)
        yield isolated_engine
    finally:
        isolated_engine.dispose()
        with engine.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{name}" CASCADE'))


def migration():
    path = Path(__file__).parents[1] / "alembic/versions/2026_11_23_1200_f6a1b2p7_production_units.py"
    spec = importlib.util.spec_from_file_location("production_units_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_all_tables_aliases_privacy_idempotence_and_noop_downgrade(isolated, caplog):
    module = migration()
    # Small extra production table verifies discovery, including future unit-bearing tables.
    metadata = sa.MetaData()
    table = sa.Table("production_unit_probe", metadata, sa.Column("id", sa.Integer, primary_key=True), sa.Column("unit", sa.String(32)))
    metadata.create_all(isolated)
    values = ["لفة", " Roll ", "pcs", "كجم", "  secret-unknown  ", " CM "]
    with isolated.begin() as connection:
        connection.execute(table.insert(), [dict(id=i, unit=value) for i, value in enumerate(values)])
    caplog.set_level(logging.INFO, logger="alembic.runtime.migration")
    with isolated.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        module.upgrade()
        expected = ["roll", "roll", "piece", "kg", values[4], "cm"]
        assert list(connection.scalars(sa.select(table.c.unit).order_by(table.c.id))) == expected
        module.downgrade()
        module.upgrade()
        assert list(connection.scalars(sa.select(table.c.unit).order_by(table.c.id))) == expected
    assert "Unit normalization skipped: table=production_unit_probe column=unit id=4" in caplog.text
    assert "secret-unknown" not in caplog.text
    assert "table=production_unit_probe converted=5" in caplog.text
    for name in ("production_demand_items", "production_orders", "production_order_items", "production_allocations", "production_result_entries", "production_waste_records"):
        assert f"table={name} converted=" in caplog.text


def test_failure_rolls_back_earlier_table_changes(isolated, monkeypatch):
    module = migration()
    metadata = sa.MetaData()
    table = sa.Table("production_aaa_probe", metadata, sa.Column("id", sa.Integer, primary_key=True), sa.Column("unit", sa.String(32)))
    metadata.create_all(isolated)
    with isolated.begin() as connection:
        connection.execute(table.insert().values(id=1, unit="لفة"))
    original = module.normalize_table
    def fail_after_first(connection, name):
        if name != table.name:
            raise RuntimeError("synthetic failure")
        return original(connection, name)
    monkeypatch.setattr(module, "normalize_table", fail_after_first)
    with pytest.raises(RuntimeError, match="synthetic failure"):
        with isolated.begin() as connection, Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
    with isolated.connect() as connection:
        assert connection.scalar(sa.select(table.c.unit)) == "لفة"


def test_every_production_snapshot_keeps_the_same_canonical_unit():
    module = migration()
    name = "test_unit_snapshots_" + uuid4().hex
    tables = ("production_demand_items", "production_orders", "production_order_items", "production_allocations", "production_result_entries", "production_waste_records")
    with engine.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{name}"'))
        connection.execute(sa.text(f'SET LOCAL search_path TO "{name}"'))
        # Minimal historical shapes exercise discovery without application-model defaults.
        for table in tables:
            connection.execute(sa.text(f'CREATE TABLE {table} (id integer PRIMARY KEY, unit varchar(32))'))
            connection.execute(sa.text(f'INSERT INTO {table} VALUES (1, :unit)'), {"unit": " لفة " if table != "production_orders" else " Roll "})
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
        for table in tables:
            assert connection.scalar(sa.text(f'SELECT unit FROM {table} WHERE id=1')) == "roll"
        connection.execute(sa.text(f'DROP SCHEMA "{name}" CASCADE'))


def test_normalized_demand_becomes_eligible_for_roll_order(isolated):
    from datetime import date
    module = migration()
    with isolated.begin() as connection:
        organizations = Base.metadata.tables["foundation_organizations"]
        org, user, customer = uuid4(), uuid4(), uuid4()
        connection.execute(organizations.insert().values(id=org, name="Synthetic", code=str(org), status="active", timezone="UTC", default_locale="en"))
        connection.execute(Base.metadata.tables["foundation_users"].insert().values(id=user, organization_id=org, email="synthetic@example.test", full_name="Tester", password_hash="unused", status="active", is_organization_root=False))
        connection.execute(Base.metadata.tables["commercial_customers"].insert().values(id=customer, organization_id=org, customer_code="C-UNITS", name="Synthetic", name_en="Synthetic", status="active", relationship_stage="lead", priority_level="medium"))
    with Session(isolated) as db:
        center = WorkCenter(organization_id=org, name="Line", code="UNITS")
        demand = ProductionDemand(organization_id=org, customer_id=customer, demand_number="D-UNITS", status="ready_for_planning")
        db.add_all([center, demand]); db.flush()
        item = ProductionDemandItem(production_demand_id=demand.id, line_no=1, product_type="film", required_quantity=10, unit="لفة")
        order = ProductionOrder(organization_id=org, work_center_id=center.id, production_order_number="P-UNITS", product_type="film", planned_quantity=10, unit="roll", planned_start_date=date(2026, 1, 1), planned_end_date=date(2026, 1, 2), created_by_user_id=user)
        db.add_all([item, order]); db.commit()
        service = PlanningOrderService(db, TenantContext(user, org), DemandItemCompatibilityChecker())
        assert service.eligible_orders(item.id) == []
        db.rollback()
        with db.begin(), Operations.context(MigrationContext.configure(db.connection())):
            module.upgrade()
        db.expire_all()
        assert [row["id"] for row in service.eligible_orders(item.id)] == [order.id]
