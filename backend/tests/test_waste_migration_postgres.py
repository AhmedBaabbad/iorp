"""PROD-WASTE-001 migration (f6a1b2h6) on real PostgreSQL, in a disposable schema, never app tables."""
import importlib.util
import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.orm import Session

from app.core.db import Base, engine
from app.foundation.infrastructure.models import Organization, User
from app.production.infrastructure.models import ProductionOrder, WorkCenter

pytestmark = pytest.mark.skipif(os.environ.get("RUN_POSTGRES_TESTS") != "1", reason="Opt-in isolated PostgreSQL tests")
spec = importlib.util.spec_from_file_location("waste_migration", Path(__file__).parents[1] / "alembic/versions/2026_10_06_0900_f6a1b2h6_operational_waste_records.py")
h6 = importlib.util.module_from_spec(spec); spec.loader.exec_module(h6)
# The models now hold categories in their own table (f6a1b2m4); undo that first to reach the shape h6 started from.
spec = importlib.util.spec_from_file_location("waste_categories_migration", Path(__file__).parents[1] / "alembic/versions/2026_11_07_1200_f6a1b2m4_waste_record_categories.py")
m4 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m4)


@pytest.fixture
def before_waste():
    schema = "test_waste_" + uuid4().hex
    with engine.begin() as c:
        c.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated = sa.create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(isolated)
        with isolated.begin() as c, Operations.context(MigrationContext.configure(c)):
            m4.downgrade()
            h6.downgrade()  # back to the native enum with the plastics-specific values
        with Session(isolated) as db:
            org = Organization(name="Migration", code="migration", timezone="UTC")
            db.add(org); db.flush()
            user = User(organization_id=org.id, full_name="Planner", email=f"{uuid4().hex}@example.invalid", password_hash="unused")
            center = WorkCenter(organization_id=org.id, code="WC", name="Line")
            db.add_all([user, center]); db.flush()
            order = ProductionOrder(organization_id=org.id, production_order_number="PO-1", work_center_id=center.id, product_type="film",
                                    planned_quantity=100, unit="kg", status="in_progress", planned_start_date=date.today(), planned_end_date=date.today(),
                                    created_by_user_id=user.id)
            db.add(order); db.commit()
            ids = dict(org=org.id, user=user.id, order=order.id, center=center.id)
        yield isolated, ids
    finally:
        isolated.dispose()
        with engine.begin() as c:
            c.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))


def _old_row(c, ids, category, reason=None, quantity="4.25"):
    row_id = uuid4()
    c.execute(sa.text("INSERT INTO production_waste_records (id, organization_id, production_order_id, work_center_id, waste_date, quantity_wasted, unit, waste_category, reason_code, created_by_user_id, created_at, updated_at) "
                      "VALUES (:id, :org, :o, :wc, '2026-09-01', :q, 'kg', CAST(:cat AS production_waste_category), :reason, :u, now(), now())"),
              dict(id=row_id, org=ids["org"], o=ids["order"], wc=ids["center"], q=quantity, cat=category, reason=reason, u=ids["user"]))
    return row_id


def test_old_categories_are_mapped_and_nothing_is_lost(before_waste):
    isolated, ids = before_waste
    with isolated.begin() as c, Operations.context(MigrationContext.configure(c)):
        rows = {name: _old_row(c, ids, name, reason) for name, reason in (
            ("startup_loss", None), ("trim_loss", None), ("end_of_roll_loss", "ROLL-7"), ("rejected_output", None), ("breakage", None))}
        h6.upgrade()
        got = {name: c.execute(sa.text("SELECT waste_category, reason_code, quantity_wasted FROM production_waste_records WHERE id = :i"), dict(i=i)).one()
               for name, i in rows.items()}
        assert got["startup_loss"][:2] == ("startup_setup", None)
        assert got["trim_loss"][:2] == ("process", "trim_loss")          # detail kept
        assert got["end_of_roll_loss"][:2] == ("process", "ROLL-7")      # an existing reason is never overwritten
        assert got["rejected_output"][:2] == ("other", "rejected_output")
        assert got["breakage"][:2] == ("handling_damage", None)
        assert got["breakage"][2] == Decimal("4.250")
        columns = {x["name"]: x for x in sa.inspect(c).get_columns("production_waste_records")}
        assert "production_run_id" in columns and "updated_by_user_id" in columns
        with pytest.raises(sa.exc.IntegrityError):  # the new category list holds at database level
            with c.begin_nested():
                c.execute(sa.text("UPDATE production_waste_records SET waste_category = 'trim_loss'"))
        with pytest.raises(sa.exc.IntegrityError):
            with c.begin_nested():
                c.execute(sa.text("UPDATE production_waste_records SET quantity_wasted = 0"))


def test_downgrade_round_trip(before_waste):
    isolated, ids = before_waste
    with isolated.begin() as c, Operations.context(MigrationContext.configure(c)):
        row = _old_row(c, ids, "breakage")
        h6.upgrade()
        h6.downgrade()
        assert c.scalar(sa.text("SELECT waste_category::text FROM production_waste_records WHERE id = :i"), dict(i=row)) == "breakage"
        h6.upgrade()
        c.execute(sa.text("UPDATE production_waste_records SET quantity_wasted = 1.125"))
        with pytest.raises(RuntimeError, match="three decimals"):
            h6.downgrade()
