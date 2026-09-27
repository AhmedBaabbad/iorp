"""production_outputs_baseline

Revision ID: 4a6c9b3d
Revises: 7e3a5f1d
Create Date: 2026-07-01 10:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4a6c9b3d"
down_revision: Union[str, None] = "7e3a5f1d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "production_outputs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("production_order_id", sa.UUID(), nullable=False),
        sa.Column("work_center_id", sa.UUID(), nullable=False),
        sa.Column("shift_report_id", sa.UUID(), nullable=True),
        sa.Column("production_order_item_id", sa.UUID(), nullable=True),
        sa.Column("output_date", sa.Date(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quantity_produced", sa.Numeric(14, 2), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column(
            "output_status",
            sa.Enum(
                "recorded",
                "verified",
                "posted",
                name="production_output_status",
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["foundation_organizations.id"]),
        sa.ForeignKeyConstraint(["production_order_id"], ["production_orders.id"]),
        sa.ForeignKeyConstraint(["work_center_id"], ["production_work_centers.id"]),
        sa.ForeignKeyConstraint(["shift_report_id"], ["production_shift_reports.id"]),
        sa.ForeignKeyConstraint(["production_order_item_id"], ["production_order_items.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["foundation_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_production_outputs_organization_id"),
        "production_outputs",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_outputs_production_order_id"),
        "production_outputs",
        ["production_order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_outputs_work_center_id"),
        "production_outputs",
        ["work_center_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_outputs_shift_report_id"),
        "production_outputs",
        ["shift_report_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_outputs_production_order_item_id"),
        "production_outputs",
        ["production_order_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_outputs_output_date"),
        "production_outputs",
        ["output_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_outputs_created_by_user_id"),
        "production_outputs",
        ["created_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_production_outputs_created_by_user_id"),
        table_name="production_outputs",
    )
    op.drop_index(
        op.f("ix_production_outputs_output_date"),
        table_name="production_outputs",
    )
    op.drop_index(
        op.f("ix_production_outputs_production_order_item_id"),
        table_name="production_outputs",
    )
    op.drop_index(
        op.f("ix_production_outputs_shift_report_id"),
        table_name="production_outputs",
    )
    op.drop_index(
        op.f("ix_production_outputs_work_center_id"),
        table_name="production_outputs",
    )
    op.drop_index(
        op.f("ix_production_outputs_production_order_id"),
        table_name="production_outputs",
    )
    op.drop_index(
        op.f("ix_production_outputs_organization_id"),
        table_name="production_outputs",
    )
    op.drop_table("production_outputs")
