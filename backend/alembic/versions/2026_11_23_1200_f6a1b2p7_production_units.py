"""Normalize production unit symbols atomically; preserve unrecognized historical values."""
import logging
from alembic import op
import sqlalchemy as sa

revision = "f6a1b2p7"
down_revision = "f6a1b2p6"
branch_labels = depends_on = None
log = logging.getLogger("alembic.runtime.migration")

# Frozen at this revision. Never import application normalization/reference data into migrations.
OFFICIAL_UNITS = frozenset({
    "piece", "unit", "pair", "set", "dozen", "lot", "roll", "reel", "coil", "bundle", "pack", "box",
    "carton", "bag", "sack", "pallet", "drum", "can", "bottle", "sheet", "container", "g", "kg", "ton",
    "lb", "oz", "mm", "cm", "m", "linear_m", "km", "sqm", "cbm", "ml", "l", "hour", "day",
})
ALIASES = {
    "roll": "roll", "rolls": "roll", "لفة": "roll", "لفه": "roll", "لفات": "roll", "رول": "roll",
    "pcs": "piece", "pc": "piece", "piece": "piece", "pieces": "piece", "قطعة": "piece", "قطعه": "piece", "حبة": "piece", "حبه": "piece",
    "kg": "kg", "kgs": "kg", "كجم": "kg", "كغ": "kg", "كيلو": "kg", "كيلوجرام": "kg",
    "m": "m", "متر": "m", "meter": "m", "meters": "m", "metre": "m", "metres": "m",
    "ton": "ton", "tons": "ton", "طن": "ton", "tonne": "ton", "tonnes": "ton", "t": "ton",
    "g": "g", "gram": "g", "grams": "g", "جم": "g", "جرام": "g",
    "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb", "رطل": "lb",
    "oz": "oz", "ounce": "oz", "ounces": "oz", "أونصة": "oz", "اونصة": "oz",
    "وحدة": "unit", "وحده": "unit", "زوج": "pair", "طقم": "set", "دفعة": "lot",
}


def normalize(value):
    if value is None:
        return None
    symbol = value.strip().lower()
    return symbol if symbol in OFFICIAL_UNITS else ALIASES.get(symbol)


def normalize_table(bind, name):
    table = sa.Table(name, sa.MetaData(), autoload_with=bind)
    if "id" not in table.c:
        raise RuntimeError(f"Production unit table has no record id: {name}")
    converted = 0
    result = bind.execute(sa.select(table.c.id, table.c.unit).execution_options(yield_per=500))
    for record in result:
        value = normalize(record.unit)
        if value is None:
            if record.unit is not None:
                log.warning("Unit normalization skipped: table=%s column=unit id=%s", name, record.id)
        elif value != record.unit:
            bind.execute(table.update().where(table.c.id == record.id).values(unit=value))
            converted += 1
    log.info("Unit normalization completed: table=%s converted=%d", name, converted)
    return converted


def upgrade():
    bind = op.get_bind()
    # Alembic's outer transaction covers every table, including allocations and their parent snapshots.
    # No commits or autocommit blocks are allowed here.
    if not bind.in_transaction():
        raise RuntimeError("Production unit normalization requires one transaction")
    inspector = sa.inspect(bind)
    for name in sorted(inspector.get_table_names()):
        if name.startswith("production_") and any(column["name"] == "unit" for column in inspector.get_columns(name)):
            normalize_table(bind, name)


def downgrade():
    # Intentional no-op: multiple old spellings map to one symbol, so the original text cannot be recovered.
    pass
