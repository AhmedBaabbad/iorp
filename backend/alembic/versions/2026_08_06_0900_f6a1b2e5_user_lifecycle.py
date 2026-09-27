"""add locked user status and lifecycle permissions

Revision ID: f6a1b2e5
Revises: f6a1b2e4
"""
from collections.abc import Sequence

from alembic import op

revision: str = "f6a1b2e5"
down_revision: str | None = "f6a1b2e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE user_status ADD VALUE IF NOT EXISTS 'locked'")
    op.execute("""
        INSERT INTO foundation_permissions (id, code, name, module_name, action_name)
        VALUES
          (gen_random_uuid(), 'foundation:users:activate', 'Activate Users', 'foundation', 'users:activate'),
          (gen_random_uuid(), 'foundation:users:deactivate', 'Deactivate Users', 'foundation', 'users:deactivate'),
          (gen_random_uuid(), 'foundation:users:lock', 'Lock Users', 'foundation', 'users:lock')
        ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO foundation_role_permissions (id, role_id, permission_id)
        SELECT gen_random_uuid(), r.id, p.id
        FROM foundation_roles r
        JOIN foundation_permissions p ON p.code IN (
          'foundation:users:activate', 'foundation:users:deactivate', 'foundation:users:lock'
        )
        WHERE r.code = 'organization_admin'
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM foundation_role_permissions WHERE permission_id IN (SELECT id FROM foundation_permissions WHERE code IN ('foundation:users:activate','foundation:users:deactivate','foundation:users:lock'))")
    op.execute("DELETE FROM foundation_permissions WHERE code IN ('foundation:users:activate','foundation:users:deactivate','foundation:users:lock')")
    # PostgreSQL enum values are intentionally retained on downgrade.
