"""Remove the legacy production outputs (the work-center/shift output design) entirely.

The final order result (production_result_entries, f6a1b2h3) replaced it. This drops the
production_outputs table, the quality columns that pointed at it (quality_checks,
quality_defects, quality_rejections: production_output_id) and its permissions.

It refuses to run while any output row or quality reference exists, so no recorded data is
lost by accident: export or delete those rows first, deliberately.

Revision ID: f6a1b2h5
Revises: f6a1b2h4
"""
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "f6a1b2h5"
down_revision = "f6a1b2h4"
branch_labels = None
depends_on = None

QUALITY_TABLES = ("quality_checks", "quality_defects", "quality_rejections")
PERMISSIONS = ("read", "write", "verify")


def upgrade():
    bind = op.get_bind()
    outputs = bind.scalar(sa.text("SELECT count(*) FROM production_outputs"))
    references = sum(bind.scalar(sa.text(f"SELECT count(*) FROM {t} WHERE production_output_id IS NOT NULL")) for t in QUALITY_TABLES)
    if outputs or references:
        raise RuntimeError(f"{outputs} production outputs and {references} quality references exist; export or delete them before removing the legacy outputs")
    for table in QUALITY_TABLES:
        op.drop_index(f"ix_{table}_production_output_id", table_name=table)
        op.drop_column(table, "production_output_id")
    op.drop_table("production_outputs")
    bind.execute(sa.text("DROP TYPE IF EXISTS production_output_status"))
    bind.execute(sa.text("DELETE FROM foundation_role_permissions WHERE permission_id IN "
                         "(SELECT id FROM foundation_permissions WHERE code LIKE 'production:production_outputs:%')"))
    bind.execute(sa.text("DELETE FROM foundation_permissions WHERE code LIKE 'production:production_outputs:%'"))


def downgrade():
    """Recreates the empty table (its f6a1b2h4 shape), the quality columns and the permissions; role grants are not restored."""
    op.create_table(
        "production_outputs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("organization_id", sa.UUID(), sa.ForeignKey("foundation_organizations.id"), nullable=False),
        sa.Column("production_order_id", sa.UUID(), sa.ForeignKey("production_orders.id"), nullable=False),
        sa.Column("work_center_id", sa.UUID(), sa.ForeignKey("production_work_centers.id"), nullable=False),
        sa.Column("production_order_item_id", sa.UUID(), sa.ForeignKey("production_order_items.id"), nullable=True),
        sa.Column("output_date", sa.Date(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quantity_produced", sa.Numeric(15, 3), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("output_status", sa.Enum("recorded", "verified", "posted", name="production_output_status", native_enum=False), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), sa.ForeignKey("foundation_users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("shift_definition_id", sa.UUID(), sa.ForeignKey("production_shift_definitions.id", ondelete="RESTRICT", name="fk_output_shift_definition"), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by_user_id", sa.UUID(), sa.ForeignKey("foundation_users.id", ondelete="SET NULL", name="fk_output_verified_by"), nullable=True),
        sa.Column("correction_of_id", sa.UUID(), sa.ForeignKey("production_outputs.id", ondelete="RESTRICT", name="fk_output_correction_of"), nullable=True),
        sa.Column("correction_reason", sa.String(500), nullable=True),
        sa.CheckConstraint("(correction_of_id IS NULL AND quantity_produced > 0) OR (correction_of_id IS NOT NULL AND quantity_produced <> 0)", name="ck_output_quantity"),
        sa.CheckConstraint("correction_of_id IS NULL OR correction_reason IS NOT NULL", name="ck_output_correction_reason"),
    )
    for column in ("organization_id", "production_order_id", "work_center_id", "production_order_item_id", "output_date", "created_by_user_id", "correction_of_id"):
        op.create_index(f"ix_production_outputs_{column}", "production_outputs", [column])
    op.create_index("ix_output_org_order_item", "production_outputs", ["organization_id", "production_order_id", "production_order_item_id"])
    op.create_index("ix_output_org_shift_date", "production_outputs", ["organization_id", "shift_definition_id", "output_date"])
    for table in QUALITY_TABLES:
        op.add_column(table, sa.Column("production_output_id", sa.UUID(), nullable=True))
        op.create_index(f"ix_{table}_production_output_id", table, ["production_output_id"])
    bind = op.get_bind()
    for org in bind.scalars(sa.text("SELECT id FROM foundation_organizations")).all():
        for action in PERMISSIONS:
            label = f"{action} production outputs"
            bind.execute(sa.text(
                "INSERT INTO foundation_permissions (id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) "
                "VALUES (:id,:org,:code,:name,:description,'production','production_outputs',:action,now(),now()) ON CONFLICT (organization_id,code) DO NOTHING"),
                dict(id=uuid4(), org=org, code=f"production:production_outputs:{action}", name=label, description=label, action=action))
