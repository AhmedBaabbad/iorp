"""PROD-QUALITY-FIX-001 data fix (f6a1b2m3): the unit written as "لفة" becomes the code "roll", reversibly."""
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

spec = importlib.util.spec_from_file_location("roll_unit_migration", Path(__file__).parents[2] / "alembic/versions/2026_11_07_1100_f6a1b2m3_roll_unit_text.py")
m3 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m3)

BEFORE = {"production_demand_items": ["لفة", "kg"], "production_allocations": ["لفة", "لفة"], "production_orders": ["لفة"],
          "production_order_items": ["لفة", "m"], "production_result_entries": ["لفة"], "production_waste_records": ["لفة", "kg"]}


@pytest.fixture
def tables():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as c:
        for table, units in BEFORE.items():
            extra = ", secondary_unit VARCHAR(32)" if table == "production_result_entries" else ""
            extra += ", unit_needs_review BOOLEAN NOT NULL DEFAULT 0" if table == "production_waste_records" else ""
            c.execute(sa.text(f"CREATE TABLE {table} (id CHAR(32) PRIMARY KEY, unit VARCHAR(32) NOT NULL{extra})"))
            for unit in units:
                review = ", unit_needs_review" if table == "production_waste_records" else ""
                value = ", :r" if review else ""
                c.execute(sa.text(f"INSERT INTO {table} (id, unit{review}) VALUES (:i, :u{value})"), dict(i=uuid4().hex, u=unit, r=unit == "لفة"))
    yield engine
    engine.dispose()


def units(engine):
    with engine.connect() as c:
        return {table: sorted(c.execute(sa.text(f"SELECT unit FROM {table}")).scalars()) for table in BEFORE}


def test_roll_text_becomes_the_roll_code_and_comes_back_on_downgrade(tables, capsys):
    with tables.begin() as c, Operations.context(MigrationContext.configure(c)):
        m3.upgrade()
    after = units(tables)
    assert after == {table: sorted("roll" if u == "لفة" else u for u in values) for table, values in BEFORE.items()}
    with tables.connect() as c:
        assert c.execute(sa.text("SELECT count(*) FROM production_unit_text_backup")).scalar() == 7
        assert c.execute(sa.text("SELECT count(*) FROM production_waste_records WHERE unit_needs_review")).scalar() == 0
    out = capsys.readouterr().out
    assert "production_allocations.unit: 2 row(s) 'لفة' -> 'roll'" in out

    with tables.begin() as c, Operations.context(MigrationContext.configure(c)):
        m3.downgrade()
    assert units(tables) == {table: sorted(values) for table, values in BEFORE.items()}
    with tables.connect() as c:
        assert "production_unit_text_backup" not in sa.inspect(c).get_table_names()
        assert c.execute(sa.text("SELECT count(*) FROM production_waste_records WHERE unit_needs_review")).scalar() == 1
