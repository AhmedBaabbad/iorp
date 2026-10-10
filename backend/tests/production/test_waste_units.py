"""PROD-QUALITY-FIX-001 item 3: a waste record's unit is a code from the central list (app/core/units.py)."""
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.core.units import UNITS
from tests.production.test_waste_records import WASTE, code, env  # noqa: F401  (env is a fixture)

spec = importlib.util.spec_from_file_location("waste_units_migration", Path(__file__).parents[2] / "alembic/versions/2026_11_07_1000_f6a1b2m2_waste_unit_codes.py")
m2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m2)


@pytest.mark.parametrize("unit", ["kg", "roll", "ton", "piece"])
def test_units_from_the_central_list_are_accepted(env, unit):
    po = env.order()
    r = env.add(po, unit=unit)
    assert r.status_code == 201, r.text
    assert r.json()["unit"] == unit and r.json()["unit_needs_review"] is False


@pytest.mark.parametrize("unit", ["كجم", "KG", "kilo", "rolls", "x"])
def test_free_text_and_translated_labels_are_rejected(env, unit):
    po = env.order()
    r = env.client.post(WASTE, json={"production_order_id": po["id"], "waste_date": "2026-10-01", "quantity_wasted": "1", "unit": unit,
                                     "categories": [{"category": "process"}]})
    assert r.status_code == 422 and code(r) == "UNIT_UNKNOWN", r.text
    record = env.added(po)
    r = env.client.patch(f"{WASTE}/{record['id']}", json={"unit": unit})
    assert r.status_code == 422 and code(r) == "UNIT_UNKNOWN"


def test_a_flagged_record_must_choose_a_unit_on_its_next_edit(env):
    po = env.order()
    record = env.added(po)
    row = next(r for r in env.rows() if str(r.id) == record["id"])
    row.unit, row.legacy_unit_text, row.unit_needs_review = "بالة", "بالة", True
    env.db.commit()
    shown = env.client.get(f"{WASTE}/{record['id']}").json()
    assert shown["unit_needs_review"] is True and shown["legacy_unit_text"] == "بالة"
    # Editing anything else keeps the unknown unit and is refused.
    r = env.client.patch(f"{WASTE}/{record['id']}", json={"notes": "checked"})
    assert r.status_code == 422 and code(r) == "UNIT_UNKNOWN"
    r = env.client.patch(f"{WASTE}/{record['id']}", json={"unit": "kg"})
    assert r.status_code == 200, r.text
    assert r.json()["unit"] == "kg" and r.json()["unit_needs_review"] is False and r.json()["legacy_unit_text"] == "بالة"


# ---- the migration -----------------------------------------------------------------------------

def test_mapping_targets_exist_in_the_central_list():
    assert m2.CODES == set(UNITS)
    assert set(m2.MAPPING.values()) <= set(UNITS)


@pytest.fixture
def old_waste():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(sa.text("CREATE TABLE production_waste_records (id VARCHAR(36) PRIMARY KEY, unit VARCHAR(32) NOT NULL)"))
        for unit in ("kg", "kg", "KG", "كجم", " كيلو ", "Kilogram", "طن", "roll", "لفة", "بالة", "بالة"):
            c.execute(sa.text("INSERT INTO production_waste_records (id, unit) VALUES (:i, :u)"), dict(i=str(uuid4()), u=unit))
    yield engine
    engine.dispose()


def _rows(engine):
    with engine.connect() as c:
        return c.execute(sa.text("SELECT unit, legacy_unit_text, unit_needs_review FROM production_waste_records ORDER BY unit, legacy_unit_text")).all()


def test_migration_maps_known_variants_and_flags_the_rest(old_waste, capsys):
    with old_waste.begin() as c, Operations.context(MigrationContext.configure(c)):
        m2.upgrade()
    rows = _rows(old_waste)
    mapped = sorted((legacy, unit) for unit, legacy, review in rows if legacy and not review)
    assert mapped == sorted([("KG", "kg"), ("كجم", "kg"), (" كيلو ", "kg"), ("Kilogram", "kg"), ("طن", "ton")])
    flagged = sorted((unit, legacy) for unit, legacy, review in rows if review)
    # Nothing guessed or deleted: unknown text stays as written and is flagged ("لفة" has its own migration).
    assert flagged == [("بالة", "بالة"), ("بالة", "بالة"), ("لفة", "لفة")]
    assert sorted(unit for unit, legacy, _ in rows if legacy is None) == ["kg", "kg", "roll"]
    out = capsys.readouterr().out
    assert "3 already a code, 5 mapped, 3 flagged for review" in out and "unmapped 'بالة': 2" in out

    with old_waste.begin() as c, Operations.context(MigrationContext.configure(c)):
        m2.downgrade()
    with old_waste.connect() as c:
        units = sorted(c.execute(sa.text("SELECT unit FROM production_waste_records")).scalars())
        columns = {col["name"] for col in sa.inspect(c).get_columns("production_waste_records")}
    assert units == sorted(["kg", "kg", "KG", "كجم", " كيلو ", "Kilogram", "طن", "roll", "لفة", "بالة", "بالة"])
    assert columns == {"id", "unit"}
