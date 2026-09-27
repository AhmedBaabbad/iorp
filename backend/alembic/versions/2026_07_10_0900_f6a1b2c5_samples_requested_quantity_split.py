"""samples_requested_quantity_split

Revision ID: f6a1b2c5
Revises: f6a1b2c4
Create Date: 2026-07-10 09:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6a1b2c5"
down_revision: Union[str, None] = "f6a1b2c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "commercial_samples",
        sa.Column(
            "is_sample_requested",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "commercial_samples",
        sa.Column("requested_sample_quantity", sa.Numeric(14, 2), nullable=True),
    )
    op.execute(
        """
        UPDATE commercial_samples
        SET requested_sample_quantity = quantity_requested,
            is_sample_requested = CASE
                WHEN quantity_requested IS NULL THEN false
                ELSE true
            END
        """
    )
    op.alter_column("commercial_samples", "is_sample_requested", server_default=None)
    op.drop_column("commercial_samples", "quantity_requested")


def downgrade() -> None:
    op.add_column(
        "commercial_samples",
        sa.Column("quantity_requested", sa.Numeric(14, 2), nullable=True),
    )
    op.execute(
        """
        UPDATE commercial_samples
        SET quantity_requested = requested_sample_quantity
        WHERE is_sample_requested = true
        """
    )
    op.drop_column("commercial_samples", "requested_sample_quantity")
    op.drop_column("commercial_samples", "is_sample_requested")
