"""sample_decision_pending

Revision ID: f6a1b2d0
Revises: f6a1b2c9
Create Date: 2026-07-13 12:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = "f6a1b2d0"
down_revision: Union[str, None] = "f6a1b2c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL requires committing before adding a new enum value
    op.execute("ALTER TYPE sampledecision_enum ADD VALUE IF NOT EXISTS 'pending'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values without recreating the type
    pass
