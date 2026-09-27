"""add optional user preferred locale

Revision ID: f6a1b2e8
Revises: f6a1b2e7
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a1b2e8"
down_revision: str | None = "f6a1b2e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("foundation_users", sa.Column("preferred_locale", sa.String(length=10), nullable=True))
    op.create_check_constraint(
        "ck_foundation_users_preferred_locale",
        "foundation_users",
        "preferred_locale IS NULL OR preferred_locale IN ('ar', 'en')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_foundation_users_preferred_locale", "foundation_users", type_="check")
    op.drop_column("foundation_users", "preferred_locale")
