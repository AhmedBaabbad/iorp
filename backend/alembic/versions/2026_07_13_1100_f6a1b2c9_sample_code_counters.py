"""sample_code_counters

Revision ID: f6a1b2c9
Revises: f6a1b2c8
Create Date: 2026-07-13 11:00:00.000000+00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f6a1b2c9"
down_revision: Union[str, None] = "f6a1b2c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "commercial_sample_code_counters",
        sa.Column("organization_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["foundation_organizations.id"],
        ),
        sa.PrimaryKeyConstraint("organization_id", "year"),
    )

    # Initialize counters from existing sample codes matching RFS-YYYY-NNN format
    op.execute(
        """
        INSERT INTO commercial_sample_code_counters (organization_id, year, last_value)
        SELECT
            c.organization_id,
            CAST(substring(s.sample_code FROM '^RFS-([0-9]{4})-[0-9]+$') AS INTEGER) AS year,
            MAX(CAST(substring(s.sample_code FROM '^RFS-[0-9]{4}-([0-9]+)$') AS INTEGER)) AS last_value
        FROM commercial_samples s
        JOIN commercial_customers c ON c.id = s.customer_id
        WHERE s.sample_code ~ '^RFS-[0-9]{4}-[0-9]+$'
        GROUP BY c.organization_id, year
        ON CONFLICT (organization_id, year) DO UPDATE
            SET last_value = GREATEST(
                commercial_sample_code_counters.last_value,
                EXCLUDED.last_value
            )
        """
    )


def downgrade() -> None:
    op.drop_table("commercial_sample_code_counters")
