"""commercial_customers_baseline

Revision ID: b41f7a2c9d13
Revises: ec914090210c
Create Date: 2026-05-25 21:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b41f7a2c9d13"
down_revision: Union[str, None] = "ec914090210c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "commercial_customers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("customer_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sector", sa.String(length=120), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("country", sa.String(length=120), nullable=True),
        sa.Column("status", sa.Enum("active", "inactive", name="customer_status"), nullable=False),
        sa.Column(
            "relationship_stage",
            sa.Enum("lead", "prospect", "customer", name="customer_relationship_stage"),
            nullable=False,
        ),
        sa.Column("opportunity_source", sa.String(length=120), nullable=True),
        sa.Column("estimated_consumption", sa.Numeric(14, 2), nullable=True),
        sa.Column("priority_level", sa.Enum("low", "medium", "high", name="customer_priority_level"), nullable=False),
        sa.Column("assigned_sales_user_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assigned_sales_user_id"], ["foundation_users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["foundation_organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "customer_code", name="uq_commercial_customers_org_code"),
    )
    op.create_index(op.f("ix_commercial_customers_assigned_sales_user_id"), "commercial_customers", ["assigned_sales_user_id"], unique=False)
    op.create_index(op.f("ix_commercial_customers_organization_id"), "commercial_customers", ["organization_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_commercial_customers_organization_id"), table_name="commercial_customers")
    op.drop_index(op.f("ix_commercial_customers_assigned_sales_user_id"), table_name="commercial_customers")
    op.drop_table("commercial_customers")
