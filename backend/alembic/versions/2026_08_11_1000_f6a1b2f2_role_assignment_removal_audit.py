"""add durable role assignment removal metadata

Revision ID: f6a1b2f2
Revises: f6a1b2f1
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a1b2f2"
down_revision: str | None = "f6a1b2f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "foundation_role_assignment_removals",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.Column("removed_by", sa.UUID(), sa.ForeignKey("foundation_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_foundation_role_assignment_removals_user_id", "foundation_role_assignment_removals", ["user_id"])
    op.create_index("ix_foundation_role_assignment_removals_role_id", "foundation_role_assignment_removals", ["role_id"])
    op.create_index("ix_foundation_role_assignment_removals_removed_by", "foundation_role_assignment_removals", ["removed_by"])


def downgrade() -> None:
    op.drop_table("foundation_role_assignment_removals")
