"""Allocation lifecycle: ACTIVE/RELEASED with release metadata; release/cancel permissions.

Revision ID: f6a1b2g8
Revises: f6a1b2g7
"""
from uuid import uuid4
from alembic import op
import sqlalchemy as sa

revision = "f6a1b2g8"
down_revision = "f6a1b2g7"
branch_labels = None
depends_on = None

# new code -> the code that already allowed the equivalent action, so no role gains or loses capability.
GRANT_MAP = {
    # Cancelling used to be a status PATCH guarded by production_orders:write.
    "production:orders:cancel": "production:production_orders:write",
    # Planners who may reserve quantity may also give it back.
    "production:planning:release_allocation": "production:planning:allocate",
}


def upgrade():
    bind = op.get_bind()
    # Every existing allocation still reserves its quantity; nothing in the data proves a release.
    op.add_column("production_allocations", sa.Column("status", sa.String(10), nullable=False, server_default="active"))
    op.add_column("production_allocations", sa.Column("released_at", sa.DateTime(timezone=True)))
    op.add_column("production_allocations", sa.Column("released_by_user_id", sa.Uuid(), sa.ForeignKey("foundation_users.id", ondelete="SET NULL", name="fk_allocation_released_by")))
    op.add_column("production_allocations", sa.Column("release_reason", sa.String(500)))
    op.create_check_constraint("ck_allocation_status", "production_allocations", "status IN ('active','released')")
    op.create_check_constraint("ck_allocation_release", "production_allocations", "(status = 'active' AND released_at IS NULL) OR (status = 'released' AND released_at IS NOT NULL)")
    op.create_index("ix_allocation_org_item_status", "production_allocations", ["organization_id", "production_demand_item_id", "status"])
    for org in bind.scalars(sa.text("SELECT id FROM foundation_organizations")).all():
        for code, old_code in GRANT_MAP.items():
            _, resource, action = code.split(":")
            bind.execute(sa.text("INSERT INTO foundation_permissions (id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) VALUES (:id,:org,:code,CAST(:name AS text),CAST(:name AS text),'production',:resource,:action,now(),now()) ON CONFLICT (organization_id,code) DO NOTHING"), dict(id=uuid4(), org=org, code=code, name=f"{action} {resource}", resource=resource, action=action))
            new_id = bind.scalar(sa.text("SELECT id FROM foundation_permissions WHERE organization_id=:org AND code=:code"), dict(org=org, code=code))
            roles = bind.execute(sa.text("SELECT rp.role_id, rp.scope FROM foundation_role_permissions rp JOIN foundation_permissions p ON p.id=rp.permission_id WHERE p.organization_id=:org AND p.code=:code"), dict(org=org, code=old_code)).all()
            for role, scope in roles:
                bind.execute(sa.text("INSERT INTO foundation_role_permissions (id,role_id,permission_id,scope) VALUES (:id,:role,:permission,:scope) ON CONFLICT (role_id,permission_id) DO NOTHING"), dict(id=uuid4(), role=role, permission=new_id, scope=scope))


def downgrade():
    bind = op.get_bind()
    # Without the status column a released allocation would silently count as reserved again.
    if bind.scalar(sa.text("SELECT count(*) FROM production_allocations WHERE status = 'released'")):
        raise RuntimeError("Released allocations exist; archive them before downgrading")
    op.drop_index("ix_allocation_org_item_status", table_name="production_allocations")
    op.drop_constraint("ck_allocation_release", "production_allocations", type_="check")
    op.drop_constraint("ck_allocation_status", "production_allocations", type_="check")
    op.drop_constraint("fk_allocation_released_by", "production_allocations", type_="foreignkey")
    for column in ("release_reason", "released_by_user_id", "released_at", "status"):
        op.drop_column("production_allocations", column)
    # Permission grants are retained on downgrade to avoid destroying administrator choices.
