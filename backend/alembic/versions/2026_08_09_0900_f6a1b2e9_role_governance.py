"""add organization role governance flags

Revision ID: f6a1b2e9
Revises: f6a1b2e8
"""
from collections.abc import Sequence
from datetime import datetime, timezone
import uuid

import sqlalchemy as sa
from alembic import op
from app.foundation.domain.system_roles import SYSTEM_ROLES, permission_matches

revision: str = "f6a1b2e9"
down_revision: str | None = "f6a1b2e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("foundation_roles", sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("foundation_roles", sa.Column("is_protected", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("foundation_roles", sa.Column("is_editable", sa.Boolean(), nullable=False, server_default=sa.true()))
    connection = op.get_bind()
    organizations = connection.execute(sa.text("SELECT id, default_locale FROM foundation_organizations")).mappings().all()
    permissions = connection.execute(sa.text("SELECT id, code FROM foundation_permissions")).mappings().all()
    now = datetime.now(timezone.utc)
    for organization in organizations:
        for definition in SYSTEM_ROLES:
            code = str(definition["code"])
            role_id = connection.execute(
                sa.text("SELECT id FROM foundation_roles WHERE organization_id = :organization_id AND code = :code"),
                {"organization_id": organization["id"], "code": code},
            ).scalar_one_or_none()
            if role_id is None:
                role_id = uuid.uuid4()
                locale = organization["default_locale"] if organization["default_locale"] in {"ar", "en"} else "en"
                connection.execute(sa.text("""
                    INSERT INTO foundation_roles
                    (id, organization_id, name, code, description, is_system, is_protected, is_editable, created_at, updated_at)
                    VALUES (:id, :organization_id, :name, :code, :description, true, :is_protected, false, :created_at, :updated_at)
                """), {"id": role_id, "organization_id": organization["id"], "name": definition[f"name_{locale}"], "code": code, "description": definition[f"description_{locale}"], "is_protected": bool(definition.get("is_protected", False)), "created_at": now, "updated_at": now})
            else:
                connection.execute(sa.text("UPDATE foundation_roles SET is_system = true, is_protected = :is_protected, is_editable = false WHERE id = :id"), {"id": role_id, "is_protected": bool(definition.get("is_protected", False))})
            existing_permission_ids = set(connection.execute(sa.text("SELECT permission_id FROM foundation_role_permissions WHERE role_id = :role_id"), {"role_id": role_id}).scalars())
            for permission in permissions:
                if permission["id"] not in existing_permission_ids and any(permission_matches(permission["code"], pattern) for pattern in definition["permissions"]):
                    connection.execute(sa.text("INSERT INTO foundation_role_permissions (id, role_id, permission_id) VALUES (:id, :role_id, :permission_id)"), {"id": uuid.uuid4(), "role_id": role_id, "permission_id": permission["id"]})


def downgrade() -> None:
    op.drop_column("foundation_roles", "is_editable")
    op.drop_column("foundation_roles", "is_protected")
    op.drop_column("foundation_roles", "is_system")
