"""add tenant user password reset permission

Revision ID: f6a1b2f4
Revises: f6a1b2f3
"""
from collections.abc import Sequence
from datetime import datetime, timezone
import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "f6a1b2f4"
down_revision: str | None = "f6a1b2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CODE = "foundation:users:reset_password"


def upgrade() -> None:
    connection = op.get_bind()
    now = datetime.now(timezone.utc)
    organizations = connection.execute(sa.text("SELECT id FROM foundation_organizations")).scalars().all()
    for organization_id in organizations:
        permission_id = uuid.uuid4()
        connection.execute(sa.text("""
            INSERT INTO foundation_permissions
                (id, organization_id, code, name, module_name, resource_name, action_name, description, created_at, updated_at)
            VALUES
                (:id, :organization_id, :code, :name, 'foundation', 'users', 'reset_password', :description, :now, :now)
        """), {
            "id": permission_id,
            "organization_id": organization_id,
            "code": CODE,
            "name": "Reset Password for Users",
            "description": "Allows the account to reset passwords for non-root users.",
            "now": now,
        })
        admin_roles = connection.execute(sa.text("""
            SELECT id FROM foundation_roles
            WHERE organization_id = :organization_id AND code = 'organization_admin'
        """), {"organization_id": organization_id}).scalars().all()
        for role_id in admin_roles:
            connection.execute(sa.text("""
                INSERT INTO foundation_role_permissions (id, role_id, permission_id)
                VALUES (:id, :role_id, :permission_id)
            """), {"id": uuid.uuid4(), "role_id": role_id, "permission_id": permission_id})


def downgrade() -> None:
    connection = op.get_bind()
    permission_ids = connection.execute(
        sa.text("SELECT id FROM foundation_permissions WHERE code = :code"), {"code": CODE}
    ).scalars().all()
    for permission_id in permission_ids:
        connection.execute(
            sa.text("DELETE FROM foundation_role_permissions WHERE permission_id = :permission_id"),
            {"permission_id": permission_id},
        )
    connection.execute(sa.text("DELETE FROM foundation_permissions WHERE code = :code"), {"code": CODE})
