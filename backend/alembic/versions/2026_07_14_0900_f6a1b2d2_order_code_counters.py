"""order_code_counters

Revision ID: f6a1b2d2
Revises: f6a1b2d1
Create Date: 2026-07-14 09:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a1b2d2"
down_revision: Union[str, None] = "f6a1b2d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "commercial_order_code_counters",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["foundation_organizations.id"]),
        sa.PrimaryKeyConstraint("organization_id", "year"),
    )
    # Use exec_driver_sql to send raw SQL directly to the DBAPI, bypassing
    # SQLAlchemy's text() parameter parser which misinterprets `:RFS` inside
    # the non-capturing regex group (?:RFS|SO) as a named bind parameter.
    op.get_bind().exec_driver_sql(
        """
        INSERT INTO commercial_order_code_counters (organization_id, year, last_value, updated_at)
        SELECT
            organization_id,
            substring(order_number from '^(?:RFS|SO)-([0-9]{4})-[0-9]+$')::integer AS year,
            COALESCE(MAX(substring(order_number from '^(?:RFS|SO)-[0-9]{4}-([0-9]+)$')::integer), 0),
            now()
        FROM commercial_orders
        WHERE order_number ~ '^(RFS|SO)-[0-9]{4}-[0-9]+$'
        GROUP BY organization_id, substring(order_number from '^(?:RFS|SO)-([0-9]{4})-[0-9]+$')::integer
        """
    )


def downgrade() -> None:
    op.drop_table("commercial_order_code_counters")
