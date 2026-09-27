"""add protected organization root flag

Revision ID: f6a1b2e0
Revises: f6a1b2d9
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f6a1b2e0"
down_revision: str | None = "f6a1b2d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "foundation_users",
        sa.Column(
            "is_organization_root",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_index(
        "ix_foundation_users_is_organization_root",
        "foundation_users",
        ["is_organization_root"],
        unique=False,
    )
    op.execute(
        sa.text(
            """
            UPDATE foundation_users AS candidate
            SET is_organization_root = true
            WHERE candidate.id = (
                SELECT first_user.id
                FROM foundation_users AS first_user
                WHERE first_user.organization_id = candidate.organization_id
                ORDER BY first_user.created_at ASC, first_user.id ASC
                LIMIT 1
            )
            """
        )
    )
    op.alter_column(
        "foundation_users",
        "is_organization_root",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_foundation_users_is_organization_root",
        table_name="foundation_users",
    )
    op.drop_column("foundation_users", "is_organization_root")
