"""PROD-QUALITY-FIX-001 item 4: a waste record may carry several categories, each with its share of the quantity.

New table production_waste_record_categories (one line per record and category, quantity > 0; the lines of a record add
up to the record's quantity, enforced by the service). Every existing record becomes one line: its category with its
full quantity. The single column waste_category is then dropped.

Downgrade: the column comes back holding, per record, the category with the largest quantity (ties: alphabetical);
the other lines are lost with the table, which the downgrade prints.
"""
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "f6a1b2m4"
down_revision = "f6a1b2m3"
branch_labels = None
depends_on = None

CATEGORIES = ("startup_setup", "changeover", "process", "material_defect", "machine_fault", "handling_damage", "contamination", "other")
CHECK = "category IN (" + ",".join(f"'{c}'" for c in CATEGORIES) + ")"
OLD_CHECK = "waste_category IN (" + ",".join(f"'{c}'" for c in CATEGORIES) + ")"


def upgrade():
    op.create_table(
        "production_waste_record_categories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("foundation_organizations.id"), nullable=False),
        sa.Column("waste_record_id", sa.Uuid(), sa.ForeignKey("production_waste_records.id", ondelete="CASCADE", name="fk_waste_category_record"),
                  nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("quantity", sa.Numeric(15, 3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(CHECK, name="ck_waste_line_category"),
        sa.CheckConstraint("quantity > 0", name="ck_waste_line_quantity"),
        sa.UniqueConstraint("waste_record_id", "category", name="uq_waste_line_record_category"),
    )
    op.create_index("ix_waste_line_record", "production_waste_record_categories", ["waste_record_id"])
    op.create_index("ix_waste_line_org_category", "production_waste_record_categories", ["organization_id", "category"])
    bind = op.get_bind()
    records_table = sa.table("production_waste_records", sa.column("id", sa.Uuid()), sa.column("organization_id", sa.Uuid()),
                             sa.column("waste_category", sa.String()), sa.column("quantity_wasted", sa.Numeric(15, 3)))
    records = bind.execute(sa.select(records_table.c.id, records_table.c.organization_id, records_table.c.waste_category,
                                     records_table.c.quantity_wasted)).all()
    lines = sa.table("production_waste_record_categories", sa.column("id", sa.Uuid()), sa.column("organization_id", sa.Uuid()),
                     sa.column("waste_record_id", sa.Uuid()), sa.column("category", sa.String()), sa.column("quantity", sa.Numeric(15, 3)),
                     sa.column("created_at", sa.DateTime(timezone=True)), sa.column("updated_at", sa.DateTime(timezone=True)))
    now = datetime.now(timezone.utc)
    if records:
        op.bulk_insert(lines, [dict(id=uuid.uuid4(), organization_id=org, waste_record_id=record_id, category=category, quantity=quantity,
                                    created_at=now, updated_at=now) for record_id, org, category, quantity in records])
    print(f"production_waste_record_categories: {len(records)} record(s) -> {len(records)} line(s), each its category with the full quantity")
    with op.batch_alter_table("production_waste_records") as batch:
        batch.drop_index("ix_production_waste_records_waste_category")
        batch.drop_constraint("ck_waste_category", type_="check")
        batch.drop_column("waste_category")


def downgrade():
    with op.batch_alter_table("production_waste_records") as batch:
        batch.add_column(sa.Column("waste_category", sa.String(32)))
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT waste_record_id, category, quantity FROM production_waste_record_categories")).all()
    best, lost = {}, 0
    for record_id, category, quantity in sorted(rows, key=lambda r: (str(r[0]), -r[2], r[1])):
        if record_id in best:
            lost += 1
        else:
            best[record_id] = category
    for record_id, category in best.items():
        bind.execute(sa.text("UPDATE production_waste_records SET waste_category = :c WHERE id = :i"), dict(c=category, i=record_id))
    print(f"production_waste_records: waste_category restored on {len(best)} record(s) (largest line); {lost} other line(s) dropped")
    with op.batch_alter_table("production_waste_records") as batch:
        batch.alter_column("waste_category", existing_type=sa.String(32), nullable=False)
        batch.create_check_constraint("ck_waste_category", OLD_CHECK)
        batch.create_index("ix_production_waste_records_waste_category", ["waste_category"])
    op.drop_index("ix_waste_line_org_category", table_name="production_waste_record_categories")
    op.drop_index("ix_waste_line_record", table_name="production_waste_record_categories")
    op.drop_table("production_waste_record_categories")
