import importlib.util
from pathlib import Path
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect
from app.core.db import Base


def test_migration_upgrade_and_downgrade():
    path = Path(__file__).parents[1] / "alembic/versions/2026_09_15_0900_f6a1b2g4_production_demands.py"
    spec = importlib.util.spec_from_file_location("demand_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    tables = {"production_demands", "production_demand_items", "production_demand_counters"}
    with engine.begin() as conn:
        Base.metadata.create_all(conn, tables=[t for t in Base.metadata.sorted_tables if t.name not in tables])
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            schema = inspect(conn)
            assert tables <= set(schema.get_table_names())
            fk = next(f for f in schema.get_foreign_keys("production_demands") if f["constrained_columns"] == ["quote_id"])
            assert fk["options"]["ondelete"] == "SET NULL"
            assert {"organization_id", "demand_number"} == set(schema.get_unique_constraints("production_demands")[0]["column_names"])
            migration.downgrade()
            assert not (tables & set(inspect(conn).get_table_names()))
    engine.dispose()
