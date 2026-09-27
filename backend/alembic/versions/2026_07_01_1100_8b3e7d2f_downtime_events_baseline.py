"""downtime_events_baseline

Revision ID: 8b3e7d2f
Revises: 4a6c9b3d
Create Date: 2026-07-01 11:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8b3e7d2f"
down_revision: Union[str, None] = "4a6c9b3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "production_downtime_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("work_center_id", sa.UUID(), nullable=False),
        sa.Column("shift_report_id", sa.UUID(), nullable=True),
        sa.Column("production_order_id", sa.UUID(), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column(
            "category",
            sa.Enum(
                "machine",
                "material",
                "manpower",
                "quality",
                "utilities",
                "setup",
                "other",
                name="production_downtime_category",
            ),
            nullable=False,
        ),
        sa.Column("reason_code", sa.String(length=255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("open", "closed", name="production_downtime_status"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["foundation_organizations.id"]),
        sa.ForeignKeyConstraint(["work_center_id"], ["production_work_centers.id"]),
        sa.ForeignKeyConstraint(["shift_report_id"], ["production_shift_reports.id"]),
        sa.ForeignKeyConstraint(["production_order_id"], ["production_orders.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["foundation_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_production_downtime_events_organization_id"),
        "production_downtime_events",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_downtime_events_work_center_id"),
        "production_downtime_events",
        ["work_center_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_downtime_events_shift_report_id"),
        "production_downtime_events",
        ["shift_report_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_downtime_events_production_order_id"),
        "production_downtime_events",
        ["production_order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_downtime_events_status"),
        "production_downtime_events",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_downtime_events_category"),
        "production_downtime_events",
        ["category"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_production_downtime_events_category"),
        table_name="production_downtime_events",
    )
    op.drop_index(
        op.f("ix_production_downtime_events_status"),
        table_name="production_downtime_events",
    )
    op.drop_index(
        op.f("ix_production_downtime_events_production_order_id"),
        table_name="production_downtime_events",
    )
    op.drop_index(
        op.f("ix_production_downtime_events_shift_report_id"),
        table_name="production_downtime_events",
    )
    op.drop_index(
        op.f("ix_production_downtime_events_work_center_id"),
        table_name="production_downtime_events",
    )
    op.drop_index(
        op.f("ix_production_downtime_events_organization_id"),
        table_name="production_downtime_events",
    )
    op.drop_table("production_downtime_events")
    op.execute("DROP TYPE IF EXISTS production_downtime_category")
    op.execute("DROP TYPE IF EXISTS production_downtime_status")
