"""work_center_commissioned_date

Revision ID: f6a1b2d3
Revises: f6a1b2d2
Create Date: 2026-07-14 10:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a1b2d3"
down_revision: Union[str, None] = "f6a1b2d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "production_work_centers",
        sa.Column("commissioned_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("production_work_centers", "commissioned_date")
