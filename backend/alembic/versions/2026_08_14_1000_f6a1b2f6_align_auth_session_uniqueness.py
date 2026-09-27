"""align auth session JTI uniqueness with metadata

Revision ID: f6a1b2f6
Revises: f6a1b2f5
"""
from collections.abc import Sequence

from alembic import op

revision: str = "f6a1b2f6"
down_revision: str | None = "f6a1b2f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # f6a1b2f5 created both a unique index and a redundant PostgreSQL unique
    # constraint. The index is the canonical metadata representation.
    op.drop_constraint("core_auth_sessions_jti_hash_key", "core_auth_sessions", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint("core_auth_sessions_jti_hash_key", "core_auth_sessions", ["jti_hash"])
