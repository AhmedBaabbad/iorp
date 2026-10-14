"""scope tenant permissions by organization and add catalog metadata

Revision ID: f6a1b2f0
Revises: f6a1b2e9
"""
from collections.abc import Sequence
from datetime import datetime, timezone
import uuid

import sqlalchemy as sa
from alembic import op

from app.foundation.domain.permission_catalog import PERMISSION_BY_CODE

revision: str = "f6a1b2f0"
down_revision: str | None = "f6a1b2e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("foundation_permissions", sa.Column("organization_id", sa.UUID(), nullable=True))
    op.add_column("foundation_permissions", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("foundation_permissions", sa.Column("resource_name", sa.String(80), nullable=True))
    op.add_column("foundation_permissions", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("foundation_permissions", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    # The legacy global uniqueness must be removed before cloning each code
    # into every organization. Composite uniqueness is installed below.
    op.drop_constraint("foundation_permissions_code_key", "foundation_permissions", type_="unique")
    connection = op.get_bind()
    organizations = list(connection.execute(sa.text("SELECT id FROM foundation_organizations ORDER BY created_at, id")).scalars())
    old_permissions = connection.execute(sa.text("SELECT id, code, name, module_name, action_name FROM foundation_permissions ORDER BY code")).mappings().all()
    now = datetime.now(timezone.utc)
    permission_ids: dict[tuple[object, str], object] = {}
    for old in old_permissions:
        definition = PERMISSION_BY_CODE.get(old["code"])
        resource = definition.resource if definition else old["action_name"].split(":", 1)[0]
        action = definition.action if definition else old["action_name"].split(":", 1)[-1]
        description = definition.description_en if definition else old["name"]
        for index, organization_id in enumerate(organizations):
            permission_id = old["id"] if index == 0 else uuid.uuid4()
            permission_ids[(organization_id, old["code"])] = permission_id
            values = {"id": permission_id, "organization_id": organization_id, "code": old["code"], "name": definition.name_en if definition else old["name"], "module": definition.module if definition else old["module_name"], "resource": resource, "action": action, "description": description, "created_at": now, "updated_at": now}
            if index == 0:
                connection.execute(sa.text("UPDATE foundation_permissions SET organization_id=:organization_id, name=:name, module_name=:module, resource_name=:resource, action_name=:action, description=:description, created_at=:created_at, updated_at=:updated_at WHERE id=:id"), values)
            else:
                connection.execute(sa.text("INSERT INTO foundation_permissions (id, organization_id, code, name, module_name, resource_name, action_name, description, created_at, updated_at) VALUES (:id, :organization_id, :code, :name, :module, :resource, :action, :description, :created_at, :updated_at)"), values)
    grants = connection.execute(sa.text("SELECT rp.id, r.organization_id, p.code FROM foundation_role_permissions rp JOIN foundation_roles r ON r.id=rp.role_id JOIN foundation_permissions p ON p.id=rp.permission_id")).mappings().all()
    for grant in grants:
        target = permission_ids.get((grant["organization_id"], grant["code"]))
        if target:
            connection.execute(sa.text("UPDATE foundation_role_permissions SET permission_id=:permission_id WHERE id=:id"), {"permission_id": target, "id": grant["id"]})
    # A fresh installation has no organization yet: the catalog rows seeded earlier belong to none, and each
    # organization receives its own catalog when it is provisioned. Where organizations exist every row was assigned
    # above, so this removes nothing (a database already past this revision never runs it again).
    connection.execute(sa.text("DELETE FROM foundation_role_permissions WHERE permission_id IN "
                               "(SELECT id FROM foundation_permissions WHERE organization_id IS NULL)"))
    connection.execute(sa.text("DELETE FROM foundation_permissions WHERE organization_id IS NULL"))
    op.alter_column("foundation_permissions", "organization_id", nullable=False)
    op.alter_column("foundation_permissions", "description", nullable=False)
    op.alter_column("foundation_permissions", "resource_name", nullable=False)
    op.alter_column("foundation_permissions", "created_at", nullable=False)
    op.alter_column("foundation_permissions", "updated_at", nullable=False)
    op.create_foreign_key("fk_foundation_permissions_organization", "foundation_permissions", "foundation_organizations", ["organization_id"], ["id"], ondelete="CASCADE")
    op.create_unique_constraint("uq_foundation_permissions_org_code", "foundation_permissions", ["organization_id", "code"])
    op.create_index("ix_foundation_permissions_organization_id", "foundation_permissions", ["organization_id"])


def downgrade() -> None:
    connection = op.get_bind()
    duplicate_ids = connection.execute(sa.text("SELECT p.id FROM foundation_permissions p WHERE EXISTS (SELECT 1 FROM foundation_permissions first WHERE first.code=p.code AND first.id < p.id)")).scalars().all()
    if duplicate_ids:
        connection.execute(sa.text("DELETE FROM foundation_role_permissions WHERE permission_id = ANY(:ids)"), {"ids": duplicate_ids})
        connection.execute(sa.text("DELETE FROM foundation_permissions WHERE id = ANY(:ids)"), {"ids": duplicate_ids})
    op.drop_index("ix_foundation_permissions_organization_id", table_name="foundation_permissions")
    op.drop_constraint("uq_foundation_permissions_org_code", "foundation_permissions", type_="unique")
    op.drop_constraint("fk_foundation_permissions_organization", "foundation_permissions", type_="foreignkey")
    op.create_unique_constraint("foundation_permissions_code_key", "foundation_permissions", ["code"])
    op.drop_column("foundation_permissions", "updated_at")
    op.drop_column("foundation_permissions", "created_at")
    op.drop_column("foundation_permissions", "resource_name")
    op.drop_column("foundation_permissions", "description")
    op.drop_column("foundation_permissions", "organization_id")
