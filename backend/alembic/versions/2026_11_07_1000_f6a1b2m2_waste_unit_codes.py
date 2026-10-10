"""PROD-QUALITY-FIX-001 item 3: a waste record's unit is a code from the central list (app/core/units.py UNITS).

Each stored unit is matched against an explicit table of known spellings (below) and replaced by its code; the text
as written is kept in legacy_unit_text so the downgrade can restore it. A unit that matches nothing is left as written
and the record is flagged (unit_needs_review): nothing is deleted or guessed, and the next edit must choose a unit
from the list. A summary of mapped and unmapped values is printed.

The list itself is fixed here on purpose (a migration must not change when app/core/units.py later grows).
"""
from collections import Counter

from alembic import op
import sqlalchemy as sa

revision = "f6a1b2m2"
down_revision = "f6a1b2m1"
branch_labels = None
depends_on = None

# The codes of app/core/units.py UNITS when this migration was written.
CODES = {"piece", "unit", "pair", "set", "dozen", "lot", "roll", "reel", "coil", "bundle", "pack", "box", "carton", "bag", "sack", "pallet",
         "drum", "can", "bottle", "sheet", "container", "g", "kg", "ton", "lb", "oz", "mm", "cm", "m", "linear_m", "km", "sqm", "cbm", "ml",
         "l", "hour", "day"}

# Known spellings -> code. Latin spellings are matched ignoring case; Arabic as written (after trimming).
MAPPING = {
    # weight
    "kg": "kg", "kgs": "kg", "kilo": "kg", "kilos": "kg", "kilogram": "kg", "kilograms": "kg", "kilogramme": "kg",
    "كجم": "kg", "كغ": "kg", "كغم": "kg", "كيلو": "kg", "كيلوجرام": "kg", "كيلوغرام": "kg", "كيلو جرام": "kg", "كيلو غرام": "kg", "كلغ": "kg",
    "g": "g", "gr": "g", "gram": "g", "grams": "g", "جم": "g", "غ": "g", "جرام": "g", "غرام": "g",
    "ton": "ton", "tons": "ton", "tonne": "ton", "tonnes": "ton", "t": "ton", "طن": "ton",
    # count and packaging
    "pcs": "piece", "pc": "piece", "piece": "piece", "pieces": "piece", "قطعة": "piece", "قطع": "piece",
    "roll": "roll", "rolls": "roll", "رول": "roll", "رولات": "roll",
    "box": "box", "boxes": "box", "صندوق": "box", "carton": "carton", "ctn": "carton", "كرتون": "carton", "كرتونة": "carton",
    "bag": "bag", "bags": "bag", "كيس": "bag", "pallet": "pallet", "plt": "pallet", "طبلية": "pallet",
    # length
    "m": "m", "meter": "m", "metre": "m", "meters": "m", "metres": "m", "متر": "m", "م": "m",
    "mm": "mm", "مم": "mm", "ملم": "mm", "cm": "cm", "سم": "cm",
}


def _code(text):
    value = (text or "").strip()
    if value in CODES:
        return value
    return MAPPING.get(value) or MAPPING.get(value.casefold())


def upgrade():
    op.add_column("production_waste_records", sa.Column("legacy_unit_text", sa.String(32)))
    op.add_column("production_waste_records", sa.Column("unit_needs_review", sa.Boolean(), nullable=False, server_default=sa.false()))
    bind = op.get_bind()
    table = sa.table("production_waste_records", sa.column("id"), sa.column("unit"), sa.column("legacy_unit_text"), sa.column("unit_needs_review"))
    mapped, kept, unmapped = Counter(), 0, Counter()
    for record_id, unit in bind.execute(sa.select(table.c.id, table.c.unit)).all():
        code = _code(unit)
        if code == unit:
            kept += 1
        elif code:
            bind.execute(table.update().where(table.c.id == record_id).values(unit=code, legacy_unit_text=unit))
            mapped[(unit, code)] += 1
        else:
            bind.execute(table.update().where(table.c.id == record_id).values(legacy_unit_text=unit, unit_needs_review=True))
            unmapped[unit] += 1
    print(f"production_waste_records units: {kept} already a code, {sum(mapped.values())} mapped, {sum(unmapped.values())} flagged for review")
    for (text, code), count in sorted(mapped.items()):
        print(f"  mapped   {text!r} -> {code!r}: {count}")
    for text, count in sorted(unmapped.items()):
        print(f"  unmapped {text!r}: {count} (kept as written, unit_needs_review = true)")


def downgrade():
    bind = op.get_bind()
    restored = bind.execute(sa.text("UPDATE production_waste_records SET unit = legacy_unit_text WHERE legacy_unit_text IS NOT NULL")).rowcount
    print(f"production_waste_records: unit restored as written on {restored} record(s)")
    with op.batch_alter_table("production_waste_records") as batch:
        batch.drop_column("unit_needs_review")
        batch.drop_column("legacy_unit_text")
