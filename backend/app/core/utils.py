from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def enum_values(enum_class: type[Enum]) -> list[str]:
    return [item.value for item in enum_class]


class TZDateTime(TypeDecorator):
    """DateTime that always returns UTC-aware datetimes.

    PostgreSQL preserves tzinfo natively; SQLite drops it. This coerces
    naive datetimes to UTC on read so Pydantic AwareDatetime validation
    passes in both environments.
    """
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value: datetime | None, dialect: object) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
