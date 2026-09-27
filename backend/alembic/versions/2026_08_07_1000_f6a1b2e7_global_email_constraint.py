"""enforce global tenant login email uniqueness

Revision ID: f6a1b2e7
Revises: f6a1b2e6
"""
from collections.abc import Sequence

from alembic import op

revision: str = "f6a1b2e7"
down_revision: str | None = "f6a1b2e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_foundation_users_org_email", "foundation_users", type_="unique")
    op.create_unique_constraint("uq_foundation_users_email_global", "foundation_users", ["email"])
    op.create_index("ix_foundation_users_email_lookup", "foundation_users", ["email"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_foundation_users_email_lookup", table_name="foundation_users")
    op.drop_constraint("uq_foundation_users_email_global", "foundation_users", type_="unique")
    op.create_unique_constraint("uq_foundation_users_org_email", "foundation_users", ["organization_id", "email"])
