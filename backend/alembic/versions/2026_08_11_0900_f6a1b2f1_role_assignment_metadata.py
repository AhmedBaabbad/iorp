"""add role assignment metadata

Revision ID: f6a1b2f1
Revises: f6a1b2f0
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a1b2f1"
down_revision: str | None = "f6a1b2f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("foundation_user_roles", sa.Column("assigned_by", sa.UUID(), nullable=True))
    op.add_column("foundation_user_roles", sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_foreign_key("fk_foundation_user_roles_assigned_by", "foundation_user_roles", "foundation_users", ["assigned_by"], ["id"], ondelete="SET NULL")
    op.create_index("ix_foundation_user_roles_assigned_by", "foundation_user_roles", ["assigned_by"])


def downgrade() -> None:
    op.drop_index("ix_foundation_user_roles_assigned_by", table_name="foundation_user_roles")
    op.drop_constraint("fk_foundation_user_roles_assigned_by", "foundation_user_roles", type_="foreignkey")
    op.drop_column("foundation_user_roles", "assigned_at")
    op.drop_column("foundation_user_roles", "assigned_by")
