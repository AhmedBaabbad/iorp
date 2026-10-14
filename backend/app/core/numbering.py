"""Reference numbers (PROJECT-FIX-002): {PREFIX}-{YEAR}-{SEQUENCE} for transactional documents, {PREFIX}-{SEQUENCE} for
master records.

Each module keeps its own counter table, keyed by organization (and kind) and year, and is its only writer; this is the
one way they take the next value:

- the year is the organization's own (its time zone), so a document made on 1 January at 00:30 in Riyadh is that year's;
- the counter row is created without a race (PostgreSQL: INSERT … ON CONFLICT DO NOTHING) and then locked FOR UPDATE, so
  two documents created at the same moment never get the same number;
- the value only grows: deleting or cancelling a document never gives its number back. A rolled-back creation takes
  its increment back with it, so no number is ever issued twice or skipped by a failure.

The internal identifier of every record stays its UUID; the reference is for people (screens, search, reports).
"""
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.db import Base


def organization_zone(db, organization_id) -> ZoneInfo:
    """The organization's time zone (shared-table read; no foundation model import)."""
    organizations = Base.metadata.tables["foundation_organizations"]
    name = db.scalar(select(organizations.c.timezone).where(organizations.c.id == organization_id))
    try:
        return ZoneInfo(name or "UTC")
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def organization_year(db, organization_id) -> int:
    return datetime.now(organization_zone(db, organization_id)).year


def take(db, model, value_field: str = "value", start: int = 0, **key) -> int:
    """The next value of the counter row `key` (created at `start` when missing), locked for this transaction."""
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(pg_insert(model).values(**key, **{value_field: start}).on_conflict_do_nothing())
        row = db.scalar(select(model).filter_by(**key).with_for_update().execution_options(populate_existing=True))
    else:  # SQLite (tests): one writer at a time
        row = db.scalar(select(model).filter_by(**key))
        if row is None:
            row = model(**key, **{value_field: start})
            db.add(row)
    setattr(row, value_field, getattr(row, value_field) + 1)
    db.flush()
    return getattr(row, value_field)


def reference(prefix: str, year: int, value: int, width: int = 4) -> str:
    """PREFIX-YYYY-NNNN; a prefix already ending in "-" (a configurable one, e.g. "PO-") is not doubled."""
    return f"{prefix.rstrip('-')}-{year}-{value:0{width}d}"
