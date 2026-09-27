"""add tenant user token version

Revision ID: f6a1b2e1
Revises: f6a1b2e0
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "f6a1b2e1"
down_revision: str | None = "f6a1b2e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "foundation_users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("foundation_users", "token_version")
