"""Operational waste records (PROD-WASTE-001).

- waste_category: from the native enum of plastics-specific values to text with a check
  constraint over cross-industry categories. Existing rows are mapped (see MAP); the old
  value is kept in reason_code when it carried detail the new category drops.
  "rejected_output" was finished product, which is scrap in the final result, not waste;
  such rows become "other" with reason_code "rejected_output" so nothing is lost.
- quantity_wasted: Numeric(14,2) -> Numeric(15,3), like every other production quantity.
- production_run_id (optional) and updated_by_user_id; quantity > 0 checked in the database.

Revision ID: f6a1b2h6
Revises: f6a1b2h5
"""
from alembic import op
import sqlalchemy as sa

revision = "f6a1b2h6"
down_revision = "f6a1b2h5"
branch_labels = None
depends_on = None

# old value -> (new category, keep the old value as reason_code when none is set)
MAP = {
    "startup_loss": ("startup_setup", False),
    "setup_loss": ("startup_setup", True),
    "trim_loss": ("process", True),
    "rewinding_loss": ("process", True),
    "end_of_roll_loss": ("process", True),
    "material_loss": ("material_defect", False),
    "breakage": ("handling_damage", False),
    "contamination_loss": ("contamination", False),
    "rejected_output": ("other", True),
    "other": ("other", False),
}
NEW = ("startup_setup", "changeover", "process", "material_defect", "machine_fault", "handling_damage", "contamination", "other")
# Downgrade: the closest old value for each new category.
BACK = {"startup_setup": "startup_loss", "changeover": "setup_loss", "process": "trim_loss", "material_defect": "material_loss",
        "machine_fault": "other", "handling_damage": "breakage", "contamination": "contamination_loss", "other": "other"}
OLD = ("startup_loss", "trim_loss", "setup_loss", "rejected_output", "breakage", "rewinding_loss", "end_of_roll_loss",
       "material_loss", "contamination_loss", "other")


def upgrade():
    bind = op.get_bind()
    op.execute("ALTER TABLE production_waste_records ALTER COLUMN waste_category TYPE varchar(32) USING waste_category::text")
    op.execute("DROP TYPE IF EXISTS production_waste_category")
    for old, (new, keep) in MAP.items():
        if keep:
            bind.execute(sa.text("UPDATE production_waste_records SET reason_code = :old WHERE waste_category = :old AND reason_code IS NULL"), dict(old=old))
        bind.execute(sa.text("UPDATE production_waste_records SET waste_category = :new WHERE waste_category = :old"), dict(new=new, old=old))
    op.create_check_constraint("ck_waste_category", "production_waste_records", "waste_category IN (" + ",".join(f"'{c}'" for c in NEW) + ")")
    op.alter_column("production_waste_records", "quantity_wasted", type_=sa.Numeric(15, 3), existing_type=sa.Numeric(14, 2), existing_nullable=False)
    op.create_check_constraint("ck_waste_quantity", "production_waste_records", "quantity_wasted > 0")
    op.add_column("production_waste_records", sa.Column("production_run_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_waste_run", "production_waste_records", "production_runs", ["production_run_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_production_waste_records_production_run_id", "production_waste_records", ["production_run_id"])
    op.add_column("production_waste_records", sa.Column("updated_by_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_waste_updated_by", "production_waste_records", "foundation_users", ["updated_by_user_id"], ["id"])
    op.create_index("ix_waste_org_order", "production_waste_records", ["organization_id", "production_order_id"])


def downgrade():
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT count(*) FROM production_waste_records WHERE quantity_wasted <> round(quantity_wasted, 2)")):
        raise RuntimeError("Waste quantities with three decimals exist; they do not fit the old precision")
    op.drop_index("ix_waste_org_order", table_name="production_waste_records")
    op.drop_constraint("fk_waste_updated_by", "production_waste_records", type_="foreignkey")
    op.drop_column("production_waste_records", "updated_by_user_id")
    op.drop_index("ix_production_waste_records_production_run_id", table_name="production_waste_records")
    op.drop_constraint("fk_waste_run", "production_waste_records", type_="foreignkey")
    op.drop_column("production_waste_records", "production_run_id")
    op.drop_constraint("ck_waste_quantity", "production_waste_records", type_="check")
    op.alter_column("production_waste_records", "quantity_wasted", type_=sa.Numeric(14, 2), existing_type=sa.Numeric(15, 3), existing_nullable=False)
    op.drop_constraint("ck_waste_category", "production_waste_records", type_="check")
    for new, old in BACK.items():
        bind.execute(sa.text("UPDATE production_waste_records SET waste_category = :old WHERE waste_category = :new"), dict(old=old, new=new))
    sa.Enum(*OLD, name="production_waste_category").create(bind)
    op.execute("ALTER TABLE production_waste_records ALTER COLUMN waste_category TYPE production_waste_category USING waste_category::production_waste_category")
