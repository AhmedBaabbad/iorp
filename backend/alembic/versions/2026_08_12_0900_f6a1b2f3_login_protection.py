"""add login attempt tracking and temporary lockout

Revision ID: f6a1b2f3
Revises: f6a1b2f2
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a1b2f3"
down_revision: str | None = "f6a1b2f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_columns(table: str) -> None:
    op.add_column(table, sa.Column("failed_login_attempts", sa.Integer(), server_default="0", nullable=False))
    op.add_column(table, sa.Column("auto_locked_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table, sa.Column("last_failed_login_at", sa.DateTime(timezone=True), nullable=True))


def upgrade() -> None:
    _add_columns("foundation_users")
    _add_columns("system_platform_accounts")


def _drop_columns(table: str) -> None:
    op.drop_column(table, "last_failed_login_at")
    op.drop_column(table, "auto_locked_until")
    op.drop_column(table, "failed_login_attempts")


def downgrade() -> None:
    _drop_columns("system_platform_accounts")
    _drop_columns("foundation_users")
