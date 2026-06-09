"""sample_code_unique_constraint

Revision ID: 3c7f1a9b
Revises: 2a6b8d3f
Create Date: 2026-06-09 11:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "3c7f1a9b"
down_revision: Union[str, None] = "2a6b8d3f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_commercial_samples_customer_code",
        "commercial_samples",
        ["customer_id", "sample_code"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_commercial_samples_customer_code",
        "commercial_samples",
        type_="unique",
    )
