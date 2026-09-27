"""user_status_remove_suspended

Revision ID: f6a1b2d5
Revises: f6a1b2d4
Create Date: 2026-07-25 15:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = "f6a1b2d5"
down_revision: Union[str, None] = "f6a1b2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE foundation_users SET status = 'inactive' WHERE status = 'suspended'")


def downgrade() -> None:
    # Data-only migration: which rows were originally 'suspended' vs 'inactive'
    # is not recoverable, so there is nothing to reverse here.
    pass
