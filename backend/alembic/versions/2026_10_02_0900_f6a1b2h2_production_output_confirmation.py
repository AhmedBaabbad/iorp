"""Production outputs as confirmations: shift, order line, verification and corrections.

Revision ID: f6a1b2h2
Revises: f6a1b2h1
"""
from uuid import uuid4
from alembic import op
import sqlalchemy as sa

revision = "f6a1b2h2"
down_revision = "f6a1b2h1"
branch_labels = None
depends_on = None

VERIFY = "production:production_outputs:verify"
SOURCE = "production:production_outputs:write"


def upgrade():
    bind = op.get_bind()
    # Existing outputs have no shift and there is no truthful value to backfill, so the column is
    # optional; existing rows are kept as they are (PROD-OUTPUT-001 made the table read-only).
    op.alter_column("production_outputs", "quantity_produced", type_=sa.Numeric(15, 3), existing_type=sa.Numeric(14, 2), existing_nullable=False)
    op.add_column("production_outputs", sa.Column("shift_definition_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_output_shift_definition", "production_outputs", "production_shift_definitions", ["shift_definition_id"], ["id"], ondelete="RESTRICT")
    op.add_column("production_outputs", sa.Column("verified_at", sa.DateTime(timezone=True)))
    op.add_column("production_outputs", sa.Column("verified_by_user_id", sa.Uuid()))
    op.create_foreign_key("fk_output_verified_by", "production_outputs", "foundation_users", ["verified_by_user_id"], ["id"], ondelete="SET NULL")
    op.add_column("production_outputs", sa.Column("correction_of_id", sa.Uuid()))
    op.create_foreign_key("fk_output_correction_of", "production_outputs", "production_outputs", ["correction_of_id"], ["id"], ondelete="RESTRICT")
    op.add_column("production_outputs", sa.Column("correction_reason", sa.String(500)))
    op.create_index("ix_production_outputs_correction_of_id", "production_outputs", ["correction_of_id"])
    op.create_index("ix_output_org_order_item", "production_outputs", ["organization_id", "production_order_id", "production_order_item_id"])
    op.create_index("ix_output_org_shift_date", "production_outputs", ["organization_id", "shift_definition_id", "output_date"])
    op.create_check_constraint("ck_output_quantity", "production_outputs",
                               "(correction_of_id IS NULL AND quantity_produced > 0) OR (correction_of_id IS NOT NULL AND quantity_produced <> 0)")
    op.create_check_constraint("ck_output_correction_reason", "production_outputs", "correction_of_id IS NULL OR correction_reason IS NOT NULL")
    for org in bind.scalars(sa.text("SELECT id FROM foundation_organizations")).all():
        bind.execute(sa.text("INSERT INTO foundation_permissions (id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) VALUES (:id,:org,:code,'verify production outputs','verify production outputs','production','production_outputs','verify',now(),now()) ON CONFLICT (organization_id,code) DO NOTHING"),
                     dict(id=uuid4(), org=org, code=VERIFY))
        new_id = bind.scalar(sa.text("SELECT id FROM foundation_permissions WHERE organization_id=:org AND code=:code"), dict(org=org, code=VERIFY))
        holders = bind.execute(sa.text("SELECT rp.role_id, rp.scope FROM foundation_role_permissions rp JOIN foundation_permissions p ON p.id=rp.permission_id WHERE p.organization_id=:org AND p.code=:code"),
                               dict(org=org, code=SOURCE)).all()
        for role, scope in holders:
            bind.execute(sa.text("INSERT INTO foundation_role_permissions (id,role_id,permission_id,scope) VALUES (:id,:role,:permission,:scope) ON CONFLICT (role_id,permission_id) DO NOTHING"),
                         dict(id=uuid4(), role=role, permission=new_id, scope=scope))


def downgrade():
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT count(*) FROM production_outputs WHERE correction_of_id IS NOT NULL OR quantity_produced <> round(quantity_produced, 2)")):
        raise RuntimeError("Corrections or three-decimal quantities exist; archive them before downgrading")
    for name in ("ck_output_correction_reason", "ck_output_quantity"):
        op.drop_constraint(name, "production_outputs", type_="check")
    for name in ("ix_output_org_shift_date", "ix_output_org_order_item", "ix_production_outputs_correction_of_id"):
        op.drop_index(name, table_name="production_outputs")
    for fk in ("fk_output_correction_of", "fk_output_verified_by", "fk_output_shift_definition"):
        op.drop_constraint(fk, "production_outputs", type_="foreignkey")
    for column in ("correction_reason", "correction_of_id", "verified_by_user_id", "verified_at", "shift_definition_id"):
        op.drop_column("production_outputs", column)
    op.alter_column("production_outputs", "quantity_produced", type_=sa.Numeric(14, 2), existing_type=sa.Numeric(15, 3), existing_nullable=False)
    # The verify permission is left in place (harmless when unused).
