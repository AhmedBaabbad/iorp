"""quote_code_counters

Revision ID: f6a1b2d1
Revises: f6a1b2d0
Create Date: 2026-07-13 13:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a1b2d1"
down_revision: Union[str, None] = "f6a1b2d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "commercial_quote_code_counters",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["foundation_organizations.id"]),
        sa.PrimaryKeyConstraint("organization_id", "year"),
    )
    op.execute(
        """
        INSERT INTO commercial_quote_code_counters (organization_id, year, last_value, updated_at)
        SELECT
            organization_id,
            substring(quote_number from '^RFQ-([0-9]{4})-[0-9]+$')::integer AS year,
            COALESCE(MAX(substring(quote_number from '^RFQ-[0-9]{4}-([0-9]+)$')::integer), 0),
            now()
        FROM commercial_quotes
        WHERE quote_number ~ '^RFQ-[0-9]{4}-[0-9]+$'
        GROUP BY organization_id, substring(quote_number from '^RFQ-([0-9]{4})-[0-9]+$')::integer
        """
    )


def downgrade() -> None:
    op.drop_table("commercial_quote_code_counters")
