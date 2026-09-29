"""Arrange a production order's allocations into specification lines.

Each distinct specification becomes one order line. Lines are ordered by width, then
color, then thickness, then weight; numbers ascend, text sorts alphabetically, and a
missing value sorts after any present one.
"""
import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

# Spec keys used for ordering, in priority order. Each entry lists accepted key names.
SORT_KEYS: tuple[tuple[str, ...], ...] = (
    ("width_mm", "width"),
    ("color", "colour"),
    ("thickness_mm", "thickness", "thickness_micron"),
    ("roll_weight_kg", "weight_kg", "weight"),
)


@dataclass
class ArrangedLine:
    line_no: int
    target_spec_json: dict | None
    unit: str
    quantity: Decimal = Decimal(0)
    allocations: list = field(default_factory=list)


def spec_identity(spec: dict | None) -> str:
    """Canonical text of a specification; equal specifications share one line."""
    return json.dumps(spec or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _value(spec: dict, names: tuple[str, ...]):
    for name in names:
        if name in spec and spec[name] not in (None, ""):
            return spec[name]
    return None


def _sort_part(value):
    # (missing?, is-text?, number, text): numbers sort numerically, text alphabetically, missing last.
    if value is None:
        return (1, 0, Decimal(0), "")
    try:
        return (0, 0, Decimal(str(value).strip()), "")
    except (InvalidOperation, ValueError):
        return (0, 1, Decimal(0), str(value).strip().casefold())


def sort_key(spec: dict | None):
    spec = spec or {}
    return tuple(_sort_part(_value(spec, names)) for names in SORT_KEYS) + (spec_identity(spec),)


def arrange(entries, *, spec=lambda e: e.target_spec_json, quantity=lambda e: e.allocated_quantity, unit=lambda e: e.unit):
    """Group entries (allocations or planned allocations) by specification into ordered lines."""
    groups: dict[str, ArrangedLine] = {}
    for entry in entries:
        key = spec_identity(spec(entry))
        line = groups.get(key)
        if line is None:
            line = groups[key] = ArrangedLine(line_no=0, target_spec_json=spec(entry), unit=unit(entry))
        line.quantity += quantity(entry)
        line.allocations.append(entry)
    lines = sorted(groups.values(), key=lambda line: sort_key(line.target_spec_json))
    for number, line in enumerate(lines, 1):
        line.line_no = number
    return lines


def common_spec(specs) -> dict | None:
    """Key/values shared by every specification; the order header shows only what all lines agree on."""
    specs = [s or {} for s in specs]
    if not specs:
        return None
    shared = {k: v for k, v in specs[0].items() if all(k in s and s[k] == v for s in specs[1:])}
    return shared or None
