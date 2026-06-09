"""commercial_samples_baseline

Revision ID: 7f3a9c2e
Revises: d83be9fa7120
Create Date: 2026-06-08 12:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7f3a9c2e"
down_revision: Union[str, None] = "d83be9fa7120"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # sample_code uniqueness is enforced at the application layer because
    # samples are organization-scoped through customer_id, not a direct organization_id column.
    op.create_table(
        "commercial_samples",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("sample_code", sa.String(length=64), nullable=False),
        sa.Column("product_type", sa.String(length=120), nullable=False),
        sa.Column("requested_spec_json", sa.JSON(), nullable=True),
        sa.Column("quantity_requested", sa.Numeric(14, 2), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("request_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "requested",
                "in_preparation",
                "delivered",
                "evaluated",
                "cancelled",
                name="sample_status",
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["foundation_users.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["commercial_customers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_commercial_samples_created_by_user_id"), "commercial_samples", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_commercial_samples_customer_id"), "commercial_samples", ["customer_id"], unique=False)
    op.create_index(op.f("ix_commercial_samples_sample_code"), "commercial_samples", ["sample_code"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_commercial_samples_sample_code"), table_name="commercial_samples")
    op.drop_index(op.f("ix_commercial_samples_customer_id"), table_name="commercial_samples")
    op.drop_index(op.f("ix_commercial_samples_created_by_user_id"), table_name="commercial_samples")
    op.drop_table("commercial_samples")
