"""Machine downtime events (PROD-DOWNTIME-001).

- category: native enum -> text with a check constraint over factory-standard categories,
  split into planned stops and availability losses. Existing rows are mapped (MAP).
- planned: derived from the category, stored so reports can filter without a lookup.
- duration_minutes: whole minutes -> Numeric(10,2), recomputed from the stored times.
- reason_code becomes optional; production_run_id, closed_by_user_id, updated_by_user_id added.
- The database checks the period (end after start) and that status matches end_time.

Revision ID: f6a1b2h7
Revises: f6a1b2h6
"""
from alembic import op
import sqlalchemy as sa

revision = "f6a1b2h7"
down_revision = "f6a1b2h6"
branch_labels = None
depends_on = None

MAP = {"machine": "breakdown", "material": "material_shortage", "manpower": "waiting_labor", "quality": "quality_issue",
       "utilities": "utilities", "setup": "changeover_setup", "other": "other"}
NEW = ("planned_maintenance", "break_meeting", "no_orders", "changeover_setup", "breakdown", "material_shortage", "waiting_labor",
       "quality_issue", "utilities", "other")
PLANNED = ("planned_maintenance", "break_meeting", "no_orders")
BACK = {"planned_maintenance": "machine", "break_meeting": "other", "no_orders": "other", "changeover_setup": "setup", "breakdown": "machine",
        "material_shortage": "material", "waiting_labor": "manpower", "quality_issue": "quality", "utilities": "utilities", "other": "other"}
OLD = ("machine", "material", "manpower", "quality", "utilities", "setup", "other")
TABLE = "production_downtime_events"


def _in(values):
    return "(" + ",".join(f"'{v}'" for v in values) + ")"


def upgrade():
    bind = op.get_bind()
    op.execute(f"ALTER TABLE {TABLE} ALTER COLUMN category TYPE varchar(32) USING category::text")
    op.execute("DROP TYPE IF EXISTS production_downtime_category")
    for old, new in MAP.items():
        bind.execute(sa.text(f"UPDATE {TABLE} SET category = :new WHERE category = :old"), dict(new=new, old=old))
    op.create_check_constraint("ck_downtime_category", TABLE, f"category IN {_in(NEW)}")
    op.add_column(TABLE, sa.Column("planned", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute(f"UPDATE {TABLE} SET planned = (category IN {_in(PLANNED)})")
    op.create_check_constraint("ck_downtime_planned", TABLE, f"planned = (category IN {_in(PLANNED)})")
    op.alter_column(TABLE, "duration_minutes", type_=sa.Numeric(10, 2), existing_type=sa.Integer(), existing_nullable=True)
    op.execute(f"UPDATE {TABLE} SET duration_minutes = round(extract(epoch FROM end_time - start_time) / 60.0, 2) WHERE end_time IS NOT NULL")
    op.alter_column(TABLE, "reason_code", nullable=True, existing_type=sa.String(255))
    op.create_check_constraint("ck_downtime_period", TABLE, "end_time IS NULL OR end_time > start_time")
    op.create_check_constraint("ck_downtime_status", TABLE, "(status = 'open' AND end_time IS NULL AND duration_minutes IS NULL)"
                               " OR (status = 'closed' AND end_time IS NOT NULL AND duration_minutes IS NOT NULL)")
    op.add_column(TABLE, sa.Column("production_run_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_downtime_run", TABLE, "production_runs", ["production_run_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_production_downtime_events_production_run_id", TABLE, ["production_run_id"])
    for column, fk in (("closed_by_user_id", "fk_downtime_closed_by"), ("updated_by_user_id", "fk_downtime_updated_by")):
        op.add_column(TABLE, sa.Column(column, sa.Uuid(), nullable=True))
        op.create_foreign_key(fk, TABLE, "foundation_users", [column], ["id"])
    op.create_index("ix_downtime_org_center_start", TABLE, ["organization_id", "work_center_id", "start_time"])


def downgrade():
    bind = op.get_bind()
    if bind.scalar(sa.text(f"SELECT count(*) FROM {TABLE} WHERE reason_code IS NULL")):
        bind.execute(sa.text(f"UPDATE {TABLE} SET reason_code = category WHERE reason_code IS NULL"))  # the old column required one
    op.drop_index("ix_downtime_org_center_start", table_name=TABLE)
    for column, fk in (("updated_by_user_id", "fk_downtime_updated_by"), ("closed_by_user_id", "fk_downtime_closed_by")):
        op.drop_constraint(fk, TABLE, type_="foreignkey")
        op.drop_column(TABLE, column)
    op.drop_index("ix_production_downtime_events_production_run_id", table_name=TABLE)
    op.drop_constraint("fk_downtime_run", TABLE, type_="foreignkey")
    op.drop_column(TABLE, "production_run_id")
    for name in ("ck_downtime_status", "ck_downtime_period", "ck_downtime_planned", "ck_downtime_category"):
        op.drop_constraint(name, TABLE, type_="check")
    op.alter_column(TABLE, "reason_code", nullable=False, existing_type=sa.String(255))
    op.alter_column(TABLE, "duration_minutes", type_=sa.Integer(), existing_type=sa.Numeric(10, 2), existing_nullable=True,
                    postgresql_using="round(duration_minutes)::integer")
    op.drop_column(TABLE, "planned")
    for new, old in BACK.items():
        bind.execute(sa.text(f"UPDATE {TABLE} SET category = :old WHERE category = :new"), dict(old=old, new=new))
    sa.Enum(*OLD, name="production_downtime_category").create(bind)
    op.execute(f"ALTER TABLE {TABLE} ALTER COLUMN category TYPE production_downtime_category USING category::production_downtime_category")
