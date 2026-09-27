"""Repeatable run participation and dedicated execution permissions.

Revision ID: f6a1b2g7
Revises: f6a1b2g6
"""
from uuid import uuid4
from alembic import op
import sqlalchemy as sa

revision = "f6a1b2g7"
down_revision = "f6a1b2g6"
branch_labels = None
depends_on = None

# new code -> the code that guarded the same action before, so no role gains or loses access.
GRANT_MAP = {
    "production:shifts:delete": "production:shift_definitions:write",
    "production:runs:pause": "production:runs:update",
    "production:runs:cancel": "production:runs:update",
}


def upgrade():
    bind = op.get_bind()
    # A worker may leave and rejoin a run; only one open participation per worker is allowed.
    op.drop_constraint("uq_run_worker", "production_run_members", type_="unique")
    op.create_index("uq_run_worker_open", "production_run_members", ["production_run_id", "workforce_member_id"], unique=True,
                    postgresql_where=sa.text("ended_at IS NULL"), sqlite_where=sa.text("ended_at IS NULL"))
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
    if bind.scalar(sa.text("SELECT count(*) FROM (SELECT 1 FROM production_run_members GROUP BY organization_id, production_run_id, workforce_member_id HAVING count(*) > 1) repeated")):
        raise RuntimeError("Workers with repeated run participation exist; archive them before downgrading")
    op.drop_index("uq_run_worker_open", table_name="production_run_members")
    op.create_unique_constraint("uq_run_worker", "production_run_members", ["organization_id", "production_run_id", "workforce_member_id"])
    # Permission grants are retained on downgrade to avoid destroying administrator choices.
