"""PROJECT-FIX-002: year-scoped sequential reference numbers (core/numbering.py), shown here on production orders.

PO-YYYY-NNNNNN, one sequence per organization and year, taken from a locked counter: the year is the organization's,
deleting an order never gives its number back, and the UUID stays the internal identifier."""
import os
import threading
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core import numbering
from app.foundation.infrastructure.models import Organization
from app.production.application.order_numbers import next_order_number
from app.production.infrastructure.models import ProductionOrder
from tests.production.test_production_orders import _create_order, work_center  # noqa: F401  (fixture)


@pytest.fixture
def clock(monkeypatch):
    """Sets the instant numbering sees: `clock(2027, 1, 1, 0, 30, "Asia/Riyadh")`."""
    def at(*parts, zone="UTC"):
        moment = datetime(*parts, tzinfo=ZoneInfo(zone))

        class Fixed(datetime):
            @classmethod
            def now(cls, tz=None):
                return moment.astimezone(tz or timezone.utc)
        monkeypatch.setattr(numbering, "datetime", Fixed)
    return at


def test_orders_take_the_next_number_of_the_year(client, auth_headers, work_center, clock):
    clock(2026, 6, 1)
    first = _create_order(client, auth_headers, work_center["id"]).json()
    second = _create_order(client, auth_headers, work_center["id"]).json()
    assert (first["production_order_number"], second["production_order_number"]) == ("PO-2026-000001", "PO-2026-000002")
    assert uuid.UUID(first["id"])  # the internal identifier stays a UUID; the number is for people


def test_a_new_year_starts_again_at_one(db, test_org, clock):
    clock(2026, 12, 31, 12)
    assert next_order_number(db, test_org.id) == "PO-2026-000001"
    assert next_order_number(db, test_org.id) == "PO-2026-000002"
    clock(2027, 1, 1, 8)
    assert next_order_number(db, test_org.id) == "PO-2027-000001"


def test_the_year_is_the_organizations_not_utc(db, test_org, clock):
    test_org.timezone = "Asia/Riyadh"
    db.commit()
    clock(2026, 12, 31, 21, 30)  # 00:30 on 1 January 2027 in Riyadh
    assert next_order_number(db, test_org.id) == "PO-2027-000001"


def test_each_organization_has_its_own_sequence(db, test_org, clock):
    clock(2026, 6, 1)
    other = Organization(name="Other Numbers", code="OTHER-NUM", timezone="UTC")
    db.add(other); db.commit()
    assert [next_order_number(db, test_org.id) for _ in range(2)] == ["PO-2026-000001", "PO-2026-000002"]
    assert next_order_number(db, other.id) == "PO-2026-000001"


def test_a_deleted_order_never_gives_its_number_back(client, auth_headers, work_center, db, clock):
    clock(2026, 6, 1)
    first = _create_order(client, auth_headers, work_center["id"]).json()
    db.delete(db.get(ProductionOrder, uuid.UUID(first["id"]))); db.commit()
    assert _create_order(client, auth_headers, work_center["id"]).json()["production_order_number"] == "PO-2026-000002"


def test_a_failed_creation_does_not_skip_or_repeat(db, test_org, clock):
    clock(2026, 6, 1)
    assert next_order_number(db, test_org.id) == "PO-2026-000001"
    db.commit()
    next_order_number(db, test_org.id)
    db.rollback()  # the document was not saved: its number was never issued
    assert next_order_number(db, test_org.id) == "PO-2026-000002"


def test_master_records_keep_one_continuous_sequence(db, test_org):
    from app.masterdata.infrastructure.models import MasterDataCounter
    values = [numbering.take(db, MasterDataCounter, organization_id=test_org.id, kind="PRD") for _ in range(3)]
    assert values == [1, 2, 3]


@pytest.mark.skipif(os.environ.get("RUN_POSTGRES_TESTS") != "1", reason="Isolated PostgreSQL opt-in")
def test_concurrent_creation_never_repeats_a_number():
    """Twenty sessions take a number at the same moment, the first of a new year included (the counter row does not exist)."""
    from app.core.db import Base, engine
    schema = "test_numbering_" + uuid.uuid4().hex
    with engine.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated = sa.create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"}, pool_size=25)
    try:
        Base.metadata.create_all(isolated)
        org = uuid.uuid4()
        with isolated.begin() as connection:
            connection.execute(sa.text("INSERT INTO foundation_organizations(id,name,code,status,timezone,default_locale,created_at,updated_at) "
                                       "VALUES (:id,'N','NUM','active','UTC','ar',now(),now())"), dict(id=org))
        numbers, start = [], threading.Barrier(20)

        def worker():
            with Session(isolated) as session:
                start.wait()
                numbers.append(next_order_number(session, org))
                session.commit()
        threads = [threading.Thread(target=worker) for _ in range(20)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        year = datetime.now(timezone.utc).year
        assert sorted(numbers) == [f"PO-{year}-{n:06d}" for n in range(1, 21)]
    finally:
        isolated.dispose()
        with engine.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))


def test_the_migration_continues_after_issued_numbers_and_changes_none():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).parents[2] / "alembic/versions/2026_11_09_1000_f6a1b2n5_production_order_counter.py"
    spec = importlib.util.spec_from_file_location("order_counter_migration", path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    a, b = uuid.uuid4(), uuid.uuid4()
    rows = [(a, "PO-20260007"), (a, "PO-2026-000009"), (a, "PO-2025-000120"), (b, "PO-2026-000002"), (b, "PO-TEST-001"), (b, None)]
    assert dict(migration._highest(rows)) == {(a, 2026): 9, (a, 2025): 120, (b, 2026): 2}
    source = path.read_text(encoding="utf-8").upper()
    assert "UPDATE PRODUCTION_ORDERS" not in source and "DELETE FROM PRODUCTION_ORDERS" not in source  # issued numbers stay as they are
