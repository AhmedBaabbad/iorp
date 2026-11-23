"""Validate symbols on new writes while preserving an unchanged historical unit."""
from app.core.units import UNITS


def checked_unit(value: str, previous: str | None = None) -> str:
    if value == previous or value in UNITS:
        return value
    raise ValueError("UNIT_UNKNOWN")
