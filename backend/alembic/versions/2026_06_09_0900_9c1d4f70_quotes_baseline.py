"""quotes_baseline

Revision ID: 9c1d4f70
Revises: 4b8e2a91
Create Date: 2026-06-09 09:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9c1d4f70"
down_revision: Union[str, None] = "4b8e2a91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "commercial_quotes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("sample_id", sa.UUID(), nullable=True),
        sa.Column("quote_number", sa.String(length=64), nullable=False),
        sa.Column("issue_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "issued", "accepted", "rejected", "expired", name="quote_status"),
            nullable=False,
        ),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("subtotal_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["foundation_users.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["commercial_customers.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["foundation_organizations.id"]),
        sa.ForeignKeyConstraint(["sample_id"], ["commercial_samples.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "quote_number", name="uq_commercial_quotes_org_number"),
    )
    op.create_index(op.f("ix_commercial_quotes_created_by_user_id"), "commercial_quotes", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_commercial_quotes_customer_id"), "commercial_quotes", ["customer_id"], unique=False)
    op.create_index(op.f("ix_commercial_quotes_organization_id"), "commercial_quotes", ["organization_id"], unique=False)
    op.create_index(op.f("ix_commercial_quotes_sample_id"), "commercial_quotes", ["sample_id"], unique=False)

    op.create_table(
        "commercial_quote_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("quote_id", sa.UUID(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("product_type", sa.String(length=120), nullable=False),
        sa.Column("requested_spec_json", sa.JSON(), nullable=True),
        sa.Column("quantity", sa.Numeric(14, 2), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.ForeignKeyConstraint(["quote_id"], ["commercial_quotes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_commercial_quote_items_quote_id"), "commercial_quote_items", ["quote_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_commercial_quote_items_quote_id"), table_name="commercial_quote_items")
    op.drop_table("commercial_quote_items")
    op.drop_index(op.f("ix_commercial_quotes_sample_id"), table_name="commercial_quotes")
    op.drop_index(op.f("ix_commercial_quotes_organization_id"), table_name="commercial_quotes")
    op.drop_index(op.f("ix_commercial_quotes_customer_id"), table_name="commercial_quotes")
    op.drop_index(op.f("ix_commercial_quotes_created_by_user_id"), table_name="commercial_quotes")
    op.drop_table("commercial_quotes")
