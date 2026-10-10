"""PROD-QUALITY-FIX-001 data fix: the unit written as "لفة" becomes the central code "roll".

The factory makes PP strap, counted in rolls; the owner confirmed (2026-10-10) that "لفة" in its records means a roll
(not "coil", whose Arabic name is "لفّة"). Only production tables hold the text: demand items, allocations, orders,
order lines, result entries (and waste records, should one have it). They change together, so an order, its lines,
its allocations and its demand items keep the same unit.

Every changed row is recorded in production_unit_text_backup (table, column, row id, text as written), printed per
table, and restored from there by the downgrade.
"""
from alembic import op
import sqlalchemy as sa

revision = "f6a1b2m3"
down_revision = "f6a1b2m2"
branch_labels = None
depends_on = None

TEXT, CODE = "لفة", "roll"
COLUMNS = (("production_demand_items", "unit"), ("production_allocations", "unit"), ("production_orders", "unit"),
           ("production_order_items", "unit"), ("production_result_entries", "unit"), ("production_result_entries", "secondary_unit"),
           ("production_waste_records", "unit"))


def upgrade():
    op.create_table("production_unit_text_backup",
                    sa.Column("table_name", sa.String(64), primary_key=True), sa.Column("column_name", sa.String(64), primary_key=True),
                    sa.Column("row_id", sa.Uuid(), primary_key=True), sa.Column("written_as", sa.String(64), nullable=False))
    bind = op.get_bind()
    for table, column in COLUMNS:
        ids = bind.execute(sa.text(f"SELECT id FROM {table} WHERE TRIM({column}) = :t"), dict(t=TEXT)).scalars().all()
        for row_id in ids:
            bind.execute(sa.text("INSERT INTO production_unit_text_backup (table_name, column_name, row_id, written_as) "
                                 f"SELECT :tn, :cn, id, {column} FROM {table} WHERE id = :i"), dict(tn=table, cn=column, i=row_id))
        if ids:
            bind.execute(sa.text(f"UPDATE {table} SET {column} = :c WHERE TRIM({column}) = :t"), dict(c=CODE, t=TEXT))
        print(f"{table}.{column}: {len(ids)} row(s) '{TEXT}' -> '{CODE}'")
    # A waste record flagged for review only because of this text is resolved by the same mapping.
    resolved = bind.execute(sa.text("UPDATE production_waste_records SET unit_needs_review = :f WHERE unit = :c AND unit_needs_review = :t"),
                            dict(f=False, t=True, c=CODE)).rowcount
    print(f"production_waste_records: {resolved} record(s) no longer need a unit review")


def downgrade():
    bind = op.get_bind()
    for table, column in COLUMNS:
        restored = bind.execute(sa.text(
            f"UPDATE {table} SET {column} = b.written_as FROM production_unit_text_backup b "
            f"WHERE b.table_name = :tn AND b.column_name = :cn AND b.row_id = {table}.id"), dict(tn=table, cn=column)).rowcount
        print(f"{table}.{column}: {restored} row(s) restored as written")
    bind.execute(sa.text("UPDATE production_waste_records SET unit_needs_review = :t WHERE TRIM(unit) = :w"), dict(t=True, w=TEXT))
    op.drop_table("production_unit_text_backup")
