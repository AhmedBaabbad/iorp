"""waste_records_baseline

Revision ID: 9c4f1a2e
Revises: 8b3e7d2f
Create Date: 2026-07-01 12:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9c4f1a2e"
down_revision: Union[str, None] = "8b3e7d2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "production_waste_records",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("production_order_id", sa.UUID(), nullable=False),
        sa.Column("work_center_id", sa.UUID(), nullable=False),
        sa.Column("shift_report_id", sa.UUID(), nullable=True),
        sa.Column("production_order_item_id", sa.UUID(), nullable=True),
        sa.Column("waste_date", sa.Date(), nullable=False),
        sa.Column("quantity_wasted", sa.Numeric(14, 2), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column(
            "waste_category",
            sa.Enum(
                "startup_loss",
                "trim_loss",
                "setup_loss",
                "rejected_output",
                "breakage",
                "rewinding_loss",
                "end_of_roll_loss",
                "material_loss",
                "contamination_loss",
                "other",
                name="production_waste_category",
            ),
            nullable=False,
        ),
        sa.Column("reason_code", sa.String(length=255), nullable=True),
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
        op.f("ix_production_waste_records_organization_id"),
        "production_waste_records",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_waste_records_production_order_id"),
        "production_waste_records",
        ["production_order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_waste_records_work_center_id"),
        "production_waste_records",
        ["work_center_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_waste_records_shift_report_id"),
        "production_waste_records",
        ["shift_report_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_waste_records_production_order_item_id"),
        "production_waste_records",
        ["production_order_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_waste_records_waste_date"),
        "production_waste_records",
        ["waste_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_waste_records_waste_category"),
        "production_waste_records",
        ["waste_category"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_production_waste_records_waste_category"),
        table_name="production_waste_records",
    )
    op.drop_index(
        op.f("ix_production_waste_records_waste_date"),
        table_name="production_waste_records",
    )
    op.drop_index(
        op.f("ix_production_waste_records_production_order_item_id"),
        table_name="production_waste_records",
    )
    op.drop_index(
        op.f("ix_production_waste_records_shift_report_id"),
        table_name="production_waste_records",
    )
    op.drop_index(
        op.f("ix_production_waste_records_work_center_id"),
        table_name="production_waste_records",
    )
    op.drop_index(
        op.f("ix_production_waste_records_production_order_id"),
        table_name="production_waste_records",
    )
    op.drop_index(
        op.f("ix_production_waste_records_organization_id"),
        table_name="production_waste_records",
    )
    op.drop_table("production_waste_records")
    op.execute("DROP TYPE IF EXISTS production_waste_category")
