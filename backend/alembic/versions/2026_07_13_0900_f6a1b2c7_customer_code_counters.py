"""customer_code_counters

Revision ID: f6a1b2c7
Revises: f6a1b2c6
Create Date: 2026-07-13 09:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6a1b2c7"
down_revision: Union[str, None] = "f6a1b2c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "commercial_customer_code_counters",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["foundation_organizations.id"]),
        sa.PrimaryKeyConstraint("organization_id"),
    )
    op.execute(
        """
        INSERT INTO commercial_customer_code_counters (organization_id, last_value, updated_at)
        SELECT
            organization_id,
            COALESCE(MAX(substring(customer_code from '^CUST-([0-9]+)$')::integer), 0),
            now()
        FROM commercial_customers
        GROUP BY organization_id
        """
    )


def downgrade() -> None:
    op.drop_table("commercial_customer_code_counters")
