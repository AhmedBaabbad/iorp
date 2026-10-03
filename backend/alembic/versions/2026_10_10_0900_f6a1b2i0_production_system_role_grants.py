"""System roles receive the production grants their definitions list (PROD-RBAC-001).

Shift rosters and production runs (f6a1b2g3..g7) were added to the catalog without granting
them to existing organizations' system roles, so only an organization root could use them.
Report export history was granted only to holders of foundation:audit:read (f6a1b2h8).
New organizations get these from foundation/domain/system_roles.py; this aligns existing ones.
Only system roles are touched; custom roles keep exactly what an administrator gave them.
Added grants are recorded so the downgrade removes exactly those.
"""
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "f6a1b2i0"
down_revision = "f6a1b2h9"
branch_labels = None
depends_on = None

BACKUP = "production_rbac_i0_added_grants"
RUNS = tuple(f"production:runs:{a}" for a in ("read", "create", "update", "start", "pause", "complete", "cancel", "manage_members"))
ROSTERS = tuple(f"production:shift_rosters:{a}" for a in ("read", "create", "update", "manage_members"))
GRANTS: dict[str, tuple[str, ...]] = {
    "organization_admin": RUNS + ROSTERS,
    "factory_manager": RUNS + ROSTERS + ("reports:exports:read",),
    "production_manager": RUNS + ROSTERS + ("reports:exports:read",),
    "viewer": ("production:runs:read", "production:shift_rosters:read"),
}


def upgrade():
    bind = op.get_bind()
    op.create_table(BACKUP, sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("role_id", sa.Uuid(), nullable=False),
                    sa.Column("permission_id", sa.Uuid(), nullable=False))
    for role_code, codes in GRANTS.items():
        rows = bind.execute(sa.text(
            "SELECT r.id AS role_id, p.id AS permission_id FROM foundation_roles r "
            "JOIN foundation_permissions p ON p.organization_id=r.organization_id "
            "WHERE r.code=:role AND r.is_system AND p.code IN :codes").bindparams(sa.bindparam("codes", expanding=True)),
            dict(role=role_code, codes=list(codes))).all()
        added = 0
        for role_id, permission_id in rows:
            if bind.execute(sa.text(
                    "INSERT INTO foundation_role_permissions (id,role_id,permission_id,scope) VALUES (:id,:role,:permission,'organization') "
                    "ON CONFLICT (role_id,permission_id) DO NOTHING RETURNING id"),
                    dict(id=uuid4(), role=role_id, permission=permission_id)).scalar():
                bind.execute(sa.text(f"INSERT INTO {BACKUP} (id,role_id,permission_id) VALUES (:id,:role,:permission)"),
                             dict(id=uuid4(), role=role_id, permission=permission_id))
                added += 1
        print(f"PROD-RBAC-001 {role_code}: {added} grant(s) added")


def downgrade():
    bind = op.get_bind()
    bind.execute(sa.text(f"DELETE FROM foundation_role_permissions rp USING {BACKUP} b "
                         "WHERE rp.role_id=b.role_id AND rp.permission_id=b.permission_id"))
    op.drop_table(BACKUP)
