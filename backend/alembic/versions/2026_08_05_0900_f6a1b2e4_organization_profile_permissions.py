"""seed organization profile permissions

Revision ID: f6a1b2e4
Revises: f6a1b2e3
"""
from collections.abc import Sequence
from alembic import op

revision: str = "f6a1b2e4"
down_revision: str | None = "f6a1b2e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO foundation_permissions (id, code, name, module_name, action_name)
        VALUES
          (gen_random_uuid(), 'foundation:organization:read', 'Read Organization Profile', 'foundation', 'organization:read'),
          (gen_random_uuid(), 'foundation:organization:update', 'Update Organization Profile', 'foundation', 'organization:update'),
          (gen_random_uuid(), 'foundation:organization:branding', 'Manage Organization Branding', 'foundation', 'organization:branding')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO foundation_role_permissions (id, role_id, permission_id)
        SELECT gen_random_uuid(), r.id, p.id
        FROM foundation_roles r
        JOIN foundation_permissions p ON p.code = 'foundation:organization:read'
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """)
    op.execute("""
        INSERT INTO foundation_role_permissions (id, role_id, permission_id)
        SELECT gen_random_uuid(), r.id, p.id
        FROM foundation_roles r
        JOIN foundation_permissions p ON p.code IN ('foundation:organization:update', 'foundation:organization:branding')
        WHERE r.code = 'organization_admin'
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM foundation_role_permissions WHERE permission_id IN (SELECT id FROM foundation_permissions WHERE code IN ('foundation:organization:read','foundation:organization:update','foundation:organization:branding'))")
    op.execute("DELETE FROM foundation_permissions WHERE code IN ('foundation:organization:read','foundation:organization:update','foundation:organization:branding')")
