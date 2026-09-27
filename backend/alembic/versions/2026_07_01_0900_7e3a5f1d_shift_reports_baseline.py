"""shift_reports_baseline

Revision ID: 7e3a5f1d
Revises: 2d9f4c8e
Create Date: 2026-07-01 09:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7e3a5f1d"
down_revision: Union[str, None] = "2d9f4c8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "production_shift_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("work_center_id", sa.UUID(), nullable=False),
        sa.Column("shift_definition_id", sa.UUID(), nullable=False),
        sa.Column("production_order_id", sa.UUID(), nullable=True),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("shift_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shift_ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "submitted",
                "approved",
                name="production_shift_report_status",
            ),
            nullable=False,
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["foundation_organizations.id"]),
        sa.ForeignKeyConstraint(["work_center_id"], ["production_work_centers.id"]),
        sa.ForeignKeyConstraint(["shift_definition_id"], ["production_shift_definitions.id"]),
        sa.ForeignKeyConstraint(["production_order_id"], ["production_orders.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["foundation_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_production_shift_reports_organization_id"),
        "production_shift_reports",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_shift_reports_work_center_id"),
        "production_shift_reports",
        ["work_center_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_shift_reports_shift_definition_id"),
        "production_shift_reports",
        ["shift_definition_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_shift_reports_production_order_id"),
        "production_shift_reports",
        ["production_order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_shift_reports_report_date"),
        "production_shift_reports",
        ["report_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_shift_reports_created_by_user_id"),
        "production_shift_reports",
        ["created_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_production_shift_reports_created_by_user_id"),
        table_name="production_shift_reports",
    )
    op.drop_index(
        op.f("ix_production_shift_reports_report_date"),
        table_name="production_shift_reports",
    )
    op.drop_index(
        op.f("ix_production_shift_reports_production_order_id"),
        table_name="production_shift_reports",
    )
    op.drop_index(
        op.f("ix_production_shift_reports_shift_definition_id"),
        table_name="production_shift_reports",
    )
    op.drop_index(
        op.f("ix_production_shift_reports_work_center_id"),
        table_name="production_shift_reports",
    )
    op.drop_index(
        op.f("ix_production_shift_reports_organization_id"),
        table_name="production_shift_reports",
    )
    op.drop_table("production_shift_reports")
