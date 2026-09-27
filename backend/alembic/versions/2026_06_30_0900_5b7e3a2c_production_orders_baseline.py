"""production_orders_baseline

Revision ID: 5b7e3a2c
Revises: 8a4d2f6b
Create Date: 2026-06-30 09:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5b7e3a2c"
down_revision: Union[str, None] = "8a4d2f6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "production_orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("production_order_number", sa.String(length=64), nullable=False),
        sa.Column("commercial_order_id", sa.UUID(), nullable=True),
        sa.Column("work_center_id", sa.UUID(), nullable=False),
        sa.Column("shift_definition_id", sa.UUID(), nullable=True),
        sa.Column("product_type", sa.String(length=120), nullable=False),
        sa.Column("target_spec_json", sa.JSON(), nullable=True),
        sa.Column("planned_quantity", sa.Numeric(14, 2), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column(
            "priority",
            sa.Enum("urgent", "normal", "low", name="production_order_priority"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "released",
                "in_progress",
                "completed",
                "cancelled",
                name="production_order_status",
            ),
            nullable=False,
        ),
        sa.Column("planned_start_date", sa.Date(), nullable=False),
        sa.Column("planned_end_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["foundation_users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["foundation_organizations.id"]),
        sa.ForeignKeyConstraint(["shift_definition_id"], ["production_shift_definitions.id"]),
        sa.ForeignKeyConstraint(["work_center_id"], ["production_work_centers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "production_order_number", name="uq_production_orders_org_number"),
    )
    op.create_index(
        op.f("ix_production_orders_commercial_order_id"),
        "production_orders",
        ["commercial_order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_orders_created_by_user_id"),
        "production_orders",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_orders_organization_id"),
        "production_orders",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_orders_shift_definition_id"),
        "production_orders",
        ["shift_definition_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_orders_work_center_id"),
        "production_orders",
        ["work_center_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_production_orders_work_center_id"), table_name="production_orders")
    op.drop_index(op.f("ix_production_orders_shift_definition_id"), table_name="production_orders")
    op.drop_index(op.f("ix_production_orders_organization_id"), table_name="production_orders")
    op.drop_index(op.f("ix_production_orders_created_by_user_id"), table_name="production_orders")
    op.drop_index(op.f("ix_production_orders_commercial_order_id"), table_name="production_orders")
    op.drop_table("production_orders")
