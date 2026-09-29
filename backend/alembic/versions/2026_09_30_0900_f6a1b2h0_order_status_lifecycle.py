"""Production order status lifecycle: on_hold/closed, actual dates, status history.

Revision ID: f6a1b2h0
Revises: f6a1b2g9
"""
from uuid import uuid4
from alembic import op
import sqlalchemy as sa

revision = "f6a1b2h0"
down_revision = "f6a1b2g9"
branch_labels = None
depends_on = None

# Each manual action gets its own permission; holders of the old catch-all write permission
# (which could set any status through PATCH) keep that capability.
NEW_PERMISSIONS = ("release", "start", "hold", "complete", "close")
SOURCE_PERMISSION = "production:production_orders:write"


def upgrade():
    bind = op.get_bind()
    # PostgreSQL cannot use a new enum value in the transaction that adds it.
    with op.get_context().autocommit_block():
        for value in ("on_hold", "closed"):
            op.execute(f"ALTER TYPE production_order_status ADD VALUE IF NOT EXISTS '{value}'")
    op.add_column("production_orders", sa.Column("actual_start_at", sa.DateTime(timezone=True)))
    op.add_column("production_orders", sa.Column("actual_end_at", sa.DateTime(timezone=True)))
    op.add_column("production_orders", sa.Column("status_version", sa.Integer(), nullable=False, server_default="1"))
    op.create_table(
        "production_order_status_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("foundation_organizations.id"), nullable=False),
        sa.Column("production_order_id", sa.Uuid(), sa.ForeignKey("production_orders.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("from_status", sa.String(20), nullable=False),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("trigger", sa.String(10), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("foundation_users.id", ondelete="SET NULL")),
        sa.Column("reason", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("trigger IN ('manual','activity','schedule')", name="ck_order_status_history_trigger"),
    )
    op.create_index("ix_order_status_history_order", "production_order_status_history", ["organization_id", "production_order_id", "created_at"])
    for org in bind.scalars(sa.text("SELECT id FROM foundation_organizations")).all():
        for action in NEW_PERMISSIONS:
            code = f"production:orders:{action}"
            bind.execute(sa.text("INSERT INTO foundation_permissions (id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) VALUES (:id,:org,:code,CAST(:name AS text),CAST(:name AS text),'production','orders',:action,now(),now()) ON CONFLICT (organization_id,code) DO NOTHING"),
                         dict(id=uuid4(), org=org, code=code, name=f"{action} orders", action=action))
            new_id = bind.scalar(sa.text("SELECT id FROM foundation_permissions WHERE organization_id=:org AND code=:code"), dict(org=org, code=code))
            holders = bind.execute(sa.text("SELECT rp.role_id, rp.scope FROM foundation_role_permissions rp JOIN foundation_permissions p ON p.id=rp.permission_id WHERE p.organization_id=:org AND p.code=:code"),
                                   dict(org=org, code=SOURCE_PERMISSION)).all()
            for role, scope in holders:
                bind.execute(sa.text("INSERT INTO foundation_role_permissions (id,role_id,permission_id,scope) VALUES (:id,:role,:permission,:scope) ON CONFLICT (role_id,permission_id) DO NOTHING"),
                             dict(id=uuid4(), role=role, permission=new_id, scope=scope))


def downgrade():
    bind = op.get_bind()
    # PostgreSQL cannot drop enum values; orders in the new states would become unreadable.
    if bind.scalar(sa.text("SELECT count(*) FROM production_orders WHERE status::text IN ('on_hold','closed')")):
        raise RuntimeError("Orders are on hold or closed; move them before downgrading")
    op.drop_index("ix_order_status_history_order", table_name="production_order_status_history")
    op.drop_table("production_order_status_history")
    for column in ("status_version", "actual_end_at", "actual_start_at"):
        op.drop_column("production_orders", column)
    # The two enum values and the permission grants are left in place (both are harmless unused).
