"""Final order result: production_result_entries (PROD-OUTPUT-001).

The legacy production_outputs table and its rows are left untouched (read-only in the API);
no rows are migrated, because a work-center/shift quantity says nothing about disposition.

Permissions are granted from the ones that did the same job before:
  production:results:read    <- production:production_outputs:read
  production:results:write   <- production:production_outputs:write
  production:results:correct <- production:orders:close

Revision ID: f6a1b2h3
Revises: f6a1b2h2
"""
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "f6a1b2h3"
down_revision = "f6a1b2h2"
branch_labels = None
depends_on = None

GRANTS = (
    ("production:results:read", "read", "production:production_outputs:read"),
    ("production:results:write", "write", "production:production_outputs:write"),
    ("production:results:correct", "correct", "production:orders:close"),
)


def upgrade():
    op.create_table(
        "production_result_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("foundation_organizations.id"), nullable=False),
        sa.Column("production_order_id", sa.Uuid(), sa.ForeignKey("production_orders.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("production_order_item_id", sa.Uuid(), sa.ForeignKey("production_order_items.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("disposition", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Numeric(15, 3), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("secondary_quantity", sa.Numeric(15, 3), nullable=True),
        sa.Column("secondary_unit", sa.String(32), nullable=True),
        sa.Column("counts_as_loss", sa.Boolean(), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("entry_type", sa.String(12), nullable=False, server_default="original"),
        sa.Column("corrects_entry_id", sa.Uuid(), sa.ForeignKey("production_result_entries.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("correction_reason", sa.String(500), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("foundation_users.id"), nullable=False),
        sa.Column("updated_by_user_id", sa.Uuid(), sa.ForeignKey("foundation_users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("disposition IN ('customer_good','stock_good','sample','scrap','rework')", name="ck_result_disposition"),
        sa.CheckConstraint(
            "(entry_type = 'original' AND quantity > 0 AND corrects_entry_id IS NULL AND correction_reason IS NULL)"
            " OR (entry_type = 'correction' AND quantity <> 0 AND corrects_entry_id IS NOT NULL AND correction_reason IS NOT NULL)",
            name="ck_result_entry_type"),
        sa.CheckConstraint(
            "disposition = 'sample' OR (disposition = 'scrap' AND counts_as_loss)"
            " OR (disposition IN ('customer_good','stock_good','rework') AND NOT counts_as_loss)",
            name="ck_result_counts_as_loss"),
        sa.CheckConstraint("(secondary_quantity IS NULL) = (secondary_unit IS NULL)", name="ck_result_secondary_measure"),
    )
    op.create_index("ix_result_org_order", "production_result_entries", ["organization_id", "production_order_id"])
    op.create_index("ix_production_result_entries_production_order_item_id", "production_result_entries", ["production_order_item_id"])
    op.create_index("ix_production_result_entries_corrects_entry_id", "production_result_entries", ["corrects_entry_id"])

    bind = op.get_bind()
    for org in bind.scalars(sa.text("SELECT id FROM foundation_organizations")).all():
        for code, action, source in GRANTS:
            bind.execute(sa.text(
                "INSERT INTO foundation_permissions (id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) "
                "VALUES (:id,:org,:code,:name,:description,'production','results',:action,now(),now()) ON CONFLICT (organization_id,code) DO NOTHING"),
                dict(id=uuid4(), org=org, code=code, name=f"{action} production results", description=f"{action} production results", action=action))
            new_id = bind.scalar(sa.text("SELECT id FROM foundation_permissions WHERE organization_id=:org AND code=:code"), dict(org=org, code=code))
            holders = bind.execute(sa.text(
                "SELECT rp.role_id, rp.scope FROM foundation_role_permissions rp JOIN foundation_permissions p ON p.id=rp.permission_id "
                "WHERE p.organization_id=:org AND p.code=:code"), dict(org=org, code=source)).all()
            for role, scope in holders:
                bind.execute(sa.text("INSERT INTO foundation_role_permissions (id,role_id,permission_id,scope) VALUES (:id,:role,:permission,:scope) "
                                     "ON CONFLICT (role_id,permission_id) DO NOTHING"), dict(id=uuid4(), role=role, permission=new_id, scope=scope))


def downgrade():
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT count(*) FROM production_result_entries")):
        raise RuntimeError("Production result entries exist; export them before downgrading")
    op.drop_table("production_result_entries")
    codes = tuple(code for code, _, _ in GRANTS)
    bind.execute(sa.text("DELETE FROM foundation_role_permissions WHERE permission_id IN (SELECT id FROM foundation_permissions WHERE code IN :codes)")
                 .bindparams(sa.bindparam("codes", expanding=True)), dict(codes=list(codes)))
    bind.execute(sa.text("DELETE FROM foundation_permissions WHERE code IN :codes").bindparams(sa.bindparam("codes", expanding=True)), dict(codes=list(codes)))
