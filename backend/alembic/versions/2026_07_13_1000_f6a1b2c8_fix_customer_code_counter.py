"""fix_customer_code_counter

Revision ID: f6a1b2c8
Revises: f6a1b2c7
Create Date: 2026-07-13 10:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f6a1b2c8"
down_revision: Union[str, None] = "f6a1b2c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Re-calculate counter using case-insensitive match (catches Cust-NNN variants)
    op.execute(
        """
        UPDATE commercial_customer_code_counters cc
        SET last_value = GREATEST(
            cc.last_value,
            COALESCE((
                SELECT MAX(
                    CAST(substring(lower(customer_code) FROM '^cust-([0-9]+)$') AS INTEGER)
                )
                FROM commercial_customers
                WHERE organization_id = cc.organization_id
            ), 0)
        )
        """
    )


def downgrade() -> None:
    pass
