"""commercial_orders_baseline

Revision ID: 2a6b8d3f
Revises: 9c1d4f70
Create Date: 2026-06-09 10:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2a6b8d3f"
down_revision: Union[str, None] = "9c1d4f70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "commercial_orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("quote_id", sa.UUID(), nullable=True),
        sa.Column("order_number", sa.String(length=64), nullable=False),
        sa.Column("order_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "confirmed",
                "cancelled",
                "converted_to_production",
                name="commercial_order_status",
            ),
            nullable=False,
        ),
        sa.Column("requested_delivery_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["foundation_users.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["commercial_customers.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["foundation_organizations.id"]),
        sa.ForeignKeyConstraint(["quote_id"], ["commercial_quotes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "order_number", name="uq_commercial_orders_org_number"),
    )
    op.create_index(op.f("ix_commercial_orders_created_by_user_id"), "commercial_orders", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_commercial_orders_customer_id"), "commercial_orders", ["customer_id"], unique=False)
    op.create_index(op.f("ix_commercial_orders_organization_id"), "commercial_orders", ["organization_id"], unique=False)
    op.create_index(op.f("ix_commercial_orders_quote_id"), "commercial_orders", ["quote_id"], unique=False)

    op.create_table(
        "commercial_order_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("commercial_order_id", sa.UUID(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("product_type", sa.String(length=120), nullable=False),
        sa.Column("requested_spec_json", sa.JSON(), nullable=True),
        sa.Column("quantity", sa.Numeric(14, 2), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("agreed_unit_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=True),
        sa.ForeignKeyConstraint(["commercial_order_id"], ["commercial_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_commercial_order_items_commercial_order_id"), "commercial_order_items", ["commercial_order_id"], unique=False)


def downgrade() -> None:
    op.drop_index(
        op.f("ix_commercial_order_items_commercial_order_id"),
        table_name="commercial_order_items",
    )
    op.drop_table("commercial_order_items")
    op.drop_index(op.f("ix_commercial_orders_quote_id"), table_name="commercial_orders")
    op.drop_index(op.f("ix_commercial_orders_organization_id"), table_name="commercial_orders")
    op.drop_index(op.f("ix_commercial_orders_customer_id"), table_name="commercial_orders")
    op.drop_index(op.f("ix_commercial_orders_created_by_user_id"), table_name="commercial_orders")
    op.drop_table("commercial_orders")
