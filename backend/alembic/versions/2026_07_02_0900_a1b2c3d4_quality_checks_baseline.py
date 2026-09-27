"""quality_checks_baseline

Revision ID: a1b2c3d4
Revises: 9c4f1a2e
Create Date: 2026-07-02 09:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4"
down_revision: Union[str, None] = "9c4f1a2e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "quality_checks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("inspection_code", sa.String(length=32), nullable=False),
        # Production context references — plain UUIDs, no FK constraints (ADR-004).
        sa.Column("production_order_id", sa.UUID(), nullable=True),
        sa.Column("production_order_item_id", sa.UUID(), nullable=True),
        sa.Column("production_output_id", sa.UUID(), nullable=True),
        sa.Column("shift_report_id", sa.UUID(), nullable=True),
        sa.Column("check_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "check_type",
            sa.Enum(
                "in_process_inspection",
                "finished_product_inspection",
                "sample_inspection",
                "reinspection",
                "issue_triggered",
                "general",
                name="quality_check_type",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "open",
                "under_inspection",
                "closed",
                name="quality_check_status",
            ),
            nullable=False,
            server_default="open",
        ),
        sa.Column(
            "result",
            sa.Enum(
                "accepted",
                "rejected",
                "conditional_accept",
                "needs_reinspection",
                name="quality_check_result",
            ),
            nullable=True,
        ),
        sa.Column("qty_inspected", sa.Integer(), nullable=False),
        sa.Column("qty_accepted", sa.Integer(), nullable=False),
        sa.Column("qty_rejected", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("checked_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["foundation_organizations.id"]),
        sa.ForeignKeyConstraint(["checked_by_user_id"], ["foundation_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "inspection_code",
            name="uq_quality_checks_org_inspection_code",
        ),
    )
    op.create_index(
        "ix_quality_checks_organization_id",
        "quality_checks",
        ["organization_id"],
    )
    op.create_index(
        "ix_quality_checks_production_order_id",
        "quality_checks",
        ["production_order_id"],
    )
    op.create_index(
        "ix_quality_checks_production_output_id",
        "quality_checks",
        ["production_output_id"],
    )
    op.create_index(
        "ix_quality_checks_shift_report_id",
        "quality_checks",
        ["shift_report_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_quality_checks_shift_report_id", table_name="quality_checks")
    op.drop_index("ix_quality_checks_production_output_id", table_name="quality_checks")
    op.drop_index("ix_quality_checks_production_order_id", table_name="quality_checks")
    op.drop_index("ix_quality_checks_organization_id", table_name="quality_checks")
    op.drop_table("quality_checks")
    op.execute("DROP TYPE IF EXISTS quality_check_type")
    op.execute("DROP TYPE IF EXISTS quality_check_status")
    op.execute("DROP TYPE IF EXISTS quality_check_result")
