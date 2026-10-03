"""PROD-DOWNTIME-001 migration (f6a1b2h7) on real PostgreSQL, in a disposable schema, never app tables."""
import importlib.util
import os
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
from app.production.infrastructure.models import WorkCenter

pytestmark = pytest.mark.skipif(os.environ.get("RUN_POSTGRES_TESTS") != "1", reason="Opt-in isolated PostgreSQL tests")
spec = importlib.util.spec_from_file_location("downtime_migration", Path(__file__).parents[1] / "alembic/versions/2026_10_07_0900_f6a1b2h7_machine_downtime_events.py")
h7 = importlib.util.module_from_spec(spec); spec.loader.exec_module(h7)


@pytest.fixture
def before_downtime():
    schema = "test_downtime_" + uuid4().hex
    with engine.begin() as c:
        c.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated = sa.create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(isolated)
        with isolated.begin() as c, Operations.context(MigrationContext.configure(c)):
            h7.downgrade()  # back to the native enum, whole minutes and a required reason
        with Session(isolated) as db:
            org = Organization(name="Migration", code="migration", timezone="UTC")
            db.add(org); db.flush()
            user = User(organization_id=org.id, full_name="Planner", email=f"{uuid4().hex}@example.invalid", password_hash="unused")
            center = WorkCenter(organization_id=org.id, code="WC", name="Line")
            db.add_all([user, center]); db.commit()
            ids = dict(org=org.id, user=user.id, center=center.id)
        yield isolated, ids
    finally:
        isolated.dispose()
        with engine.begin() as c:
            c.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))


def _old(c, ids, category, start, end):
    row = uuid4()
    c.execute(sa.text("INSERT INTO production_downtime_events (id, organization_id, work_center_id, start_time, end_time, duration_minutes, category, reason_code, status, created_by_user_id, created_at, updated_at) "
                      "VALUES (:id, :org, :wc, :s, :e, :d, CAST(:cat AS production_downtime_category), 'reason', CAST(:st AS production_downtime_status), :u, now(), now())"),
              dict(id=row, org=ids["org"], wc=ids["center"], s=start, e=end, d=None if end is None else 12, cat=category, st="open" if end is None else "closed", u=ids["user"]))
    return row


def test_categories_mapped_planned_derived_and_duration_recomputed(before_downtime):
    isolated, ids = before_downtime
    with isolated.begin() as c, Operations.context(MigrationContext.configure(c)):
        machine = _old(c, ids, "machine", "2026-09-01 08:00+00", "2026-09-01 08:12:30+00")
        setup = _old(c, ids, "setup", "2026-09-01 09:00+00", "2026-09-01 09:20+00")
        manpower = _old(c, ids, "manpower", "2026-09-01 10:00+00", None)
        h7.upgrade()
        row = lambda i: c.execute(sa.text("SELECT category, planned, duration_minutes, status::text FROM production_downtime_events WHERE id = :i"), dict(i=i)).one()  # noqa: E731
        assert row(machine) == ("breakdown", False, Decimal("12.50"), "closed")  # exact minutes now, not the stored 12
        assert row(setup)[:2] == ("changeover_setup", False)
        assert row(manpower) == ("waiting_labor", False, None, "open")
        for bad in ("UPDATE production_downtime_events SET category = 'machine'",
                    "UPDATE production_downtime_events SET planned = true WHERE category = 'breakdown'",
                    "UPDATE production_downtime_events SET end_time = start_time WHERE end_time IS NOT NULL",
                    "UPDATE production_downtime_events SET status = 'open' WHERE end_time IS NOT NULL"):
            with pytest.raises(sa.exc.IntegrityError):
                with c.begin_nested():
                    c.execute(sa.text(bad))
        h7.downgrade()
        assert c.scalar(sa.text("SELECT category::text FROM production_downtime_events WHERE id = :i"), dict(i=machine)) == "machine"
        h7.upgrade()
        assert row(machine)[0] == "breakdown"
