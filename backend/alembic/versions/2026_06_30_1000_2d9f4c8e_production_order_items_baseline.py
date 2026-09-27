"""production_order_items_baseline

Revision ID: 2d9f4c8e
Revises: 5b7e3a2c
Create Date: 2026-06-30 10:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2d9f4c8e"
down_revision: Union[str, None] = "5b7e3a2c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "production_order_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("production_order_id", sa.UUID(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("target_spec_json", sa.JSON(), nullable=True),
        sa.Column("planned_quantity", sa.Numeric(14, 2), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["production_order_id"], ["production_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "production_order_id",
            "line_no",
            name="uq_production_order_items_order_line",
        ),
    )
    op.create_index(
        op.f("ix_production_order_items_production_order_id"),
        "production_order_items",
        ["production_order_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_production_order_items_production_order_id"),
        table_name="production_order_items",
    )
    op.drop_table("production_order_items")
