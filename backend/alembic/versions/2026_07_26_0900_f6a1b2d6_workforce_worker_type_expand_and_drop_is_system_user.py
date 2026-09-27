"""workforce_worker_type_expand_and_drop_is_system_user

Revision ID: f6a1b2d6
Revises: f6a1b2d5
Create Date: 2026-07-26 09:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a1b2d6"
down_revision: Union[str, None] = "f6a1b2d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_WORKER_TYPE_VALUES = [
    "factory_manager",
    "maintenance_technician",
    "logistics_coordinator",
    "sales_manager",
    "procurement_officer",
    "hr_officer",
    "accountant",
    "safety_officer",
]


def upgrade() -> None:
    bind = op.get_bind()
    for value in NEW_WORKER_TYPE_VALUES:
        bind.execute(sa.text(f"ALTER TYPE workforce_worker_type ADD VALUE IF NOT EXISTS '{value}'"))

    # "commercial_manager" is intentionally left defined in the PostgreSQL enum type
    # (Postgres has no DROP VALUE) but is no longer part of the Python WorkerType enum
    # and is therefore unreachable from the application. No existing rows used it.

    op.drop_column("workforce_members", "is_system_user")


def downgrade() -> None:
    op.add_column(
        "workforce_members",
        sa.Column("is_system_user", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("workforce_members", "is_system_user", server_default=None)

    # Enum values cannot be removed from a PostgreSQL enum type; the added
    # worker_type values remain defined but unused if downgraded.
