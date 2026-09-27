"""add organization audit read permission

Revision ID: f6a1b2f8
Revises: f6a1b2f7
"""
from collections.abc import Sequence
from datetime import datetime, timezone
import uuid

from alembic import op
import sqlalchemy as sa

revision: str = "f6a1b2f8"
down_revision: str | None = "f6a1b2f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind(); now = datetime.now(timezone.utc)
    organizations = connection.execute(sa.text("SELECT id FROM foundation_organizations")).scalars().all()
    for organization_id in organizations:
        permission_id = connection.execute(sa.text("SELECT id FROM foundation_permissions WHERE organization_id=:org AND code='foundation:audit:read'"), {"org": organization_id}).scalar()
        if permission_id is None:
            permission_id = uuid.uuid4()
            connection.execute(sa.text("""INSERT INTO foundation_permissions
                (id, organization_id, code, name, description, module_name, resource_name, action_name, created_at, updated_at)
                VALUES (:id, :org, 'foundation:audit:read', 'Read Audit Log', 'View organization audit trail', 'foundation', 'audit', 'read', :now, :now)"""),
                {"id": permission_id, "org": organization_id, "now": now})
        admin_roles = connection.execute(sa.text("SELECT id FROM foundation_roles WHERE organization_id=:org AND code='organization_admin'"), {"org": organization_id}).scalars().all()
        for role_id in admin_roles:
            exists = connection.execute(sa.text("SELECT 1 FROM foundation_role_permissions WHERE role_id=:role AND permission_id=:permission"), {"role": role_id, "permission": permission_id}).scalar()
            if not exists:
                connection.execute(sa.text("INSERT INTO foundation_role_permissions (id, role_id, permission_id) VALUES (:id, :role, :permission)"), {"id": uuid.uuid4(), "role": role_id, "permission": permission_id})


def downgrade() -> None:
    connection = op.get_bind()
    ids = connection.execute(sa.text("SELECT id FROM foundation_permissions WHERE code='foundation:audit:read'")).scalars().all()
    for permission_id in ids:
        connection.execute(sa.text("DELETE FROM foundation_role_permissions WHERE permission_id=:id"), {"id": permission_id})
        connection.execute(sa.text("DELETE FROM foundation_permissions WHERE id=:id"), {"id": permission_id})
