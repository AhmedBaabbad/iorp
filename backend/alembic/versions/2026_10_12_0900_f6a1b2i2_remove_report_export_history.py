"""Remove the report export history screen's permission (reports:exports:read).

Each generated report already names who prepared it, when, and its reference number, so the
history screen and its API were removed. The report_exports audit table stays: it numbers
references and records failures. Removed rows and grants are kept in a backup table, so the
downgrade restores them exactly.
"""
import sqlalchemy as sa
from alembic import op

revision = "f6a1b2i2"
down_revision = "f6a1b2i1"
branch_labels = None
depends_on = None

CODE = "reports:exports:read"
BACKUP = "report_exports_permission_i2_backup"


def upgrade():
    bind = op.get_bind()
    op.create_table(BACKUP, sa.Column("permission_id", sa.Uuid(), nullable=False), sa.Column("organization_id", sa.Uuid(), nullable=False),
                    sa.Column("name", sa.String(120)), sa.Column("description", sa.Text()), sa.Column("module_name", sa.String(80)),
                    sa.Column("resource_name", sa.String(80)), sa.Column("action_name", sa.String(80)),
                    sa.Column("grant_id", sa.Uuid()), sa.Column("role_id", sa.Uuid()), sa.Column("scope", sa.String(20)))
    # One backup row per grant, plus one per permission without grants.
    bind.execute(sa.text(f"""
        INSERT INTO {BACKUP} (permission_id, organization_id, name, description, module_name, resource_name, action_name, grant_id, role_id, scope)
        SELECT p.id, p.organization_id, p.name, p.description, p.module_name, p.resource_name, p.action_name, rp.id, rp.role_id, rp.scope
        FROM foundation_permissions p LEFT JOIN foundation_role_permissions rp ON rp.permission_id = p.id
        WHERE p.code = :code"""), dict(code=CODE))
    removed = bind.scalar(sa.text(f"SELECT count(grant_id) FROM {BACKUP}"))
    bind.execute(sa.text("DELETE FROM foundation_role_permissions WHERE permission_id IN (SELECT id FROM foundation_permissions WHERE code = :code)"), dict(code=CODE))
    bind.execute(sa.text("DELETE FROM foundation_permissions WHERE code = :code"), dict(code=CODE))
    print(f"Removed {CODE}: {removed} role grant(s); report_exports audit rows kept")


def downgrade():
    bind = op.get_bind()
    bind.execute(sa.text(f"""
        INSERT INTO foundation_permissions (id, organization_id, code, name, description, module_name, resource_name, action_name, created_at, updated_at)
        SELECT DISTINCT permission_id, organization_id, :code, name, description, module_name, resource_name, action_name, now(), now() FROM {BACKUP}
        ON CONFLICT (organization_id, code) DO NOTHING"""), dict(code=CODE))
    bind.execute(sa.text(f"""
        INSERT INTO foundation_role_permissions (id, role_id, permission_id, scope)
        SELECT grant_id, role_id, permission_id, scope FROM {BACKUP} WHERE grant_id IS NOT NULL
        ON CONFLICT (role_id, permission_id) DO NOTHING"""))
    op.drop_table(BACKUP)
