"""quality_rejections_baseline

Revision ID: c3d4e5f6
Revises: b2c3d4e5
Create Date: 2026-07-02 11:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6"
down_revision: Union[str, None] = "b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "quality_rejections",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("quality_check_id", sa.UUID(), nullable=True),
        sa.Column("quality_defect_id", sa.UUID(), nullable=True),
        # Optional Production context references: plain UUIDs, no FK constraints.
        sa.Column("production_output_id", sa.UUID(), nullable=True),
        sa.Column("production_order_item_id", sa.UUID(), nullable=True),
        sa.Column("rejection_date", sa.Date(), nullable=False),
        sa.Column(
            "rejection_reason",
            sa.Enum(
                "failed_quality_check",
                "critical_defect",
                "out_of_spec",
                "dimension_failure",
                "surface_failure",
                "packaging_failure",
                "labeling_issue",
                "other",
                name="quality_rejection_reason",
            ),
            nullable=False,
        ),
        sa.Column("rejection_notes", sa.Text(), nullable=False),
        sa.Column(
            "disposition",
            sa.Enum(
                "hold",
                "scrap",
                "rework",
                "return_to_process",
                name="quality_disposition",
            ),
            nullable=False,
        ),
        sa.Column(
            "disposition_status",
            sa.Enum(
                "pending",
                "executed",
                name="quality_disposition_status",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("quantity_rejected", sa.Integer(), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("rejected_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["foundation_organizations.id"]),
        sa.ForeignKeyConstraint(["quality_check_id"], ["quality_checks.id"]),
        sa.ForeignKeyConstraint(["quality_defect_id"], ["quality_defects.id"]),
        sa.ForeignKeyConstraint(["rejected_by_user_id"], ["foundation_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quality_rejections_organization_id", "quality_rejections", ["organization_id"])
    op.create_index("ix_quality_rejections_quality_check_id", "quality_rejections", ["quality_check_id"])
    op.create_index("ix_quality_rejections_quality_defect_id", "quality_rejections", ["quality_defect_id"])
    op.create_index("ix_quality_rejections_production_output_id", "quality_rejections", ["production_output_id"])
    op.create_index("ix_quality_rejections_rejection_date", "quality_rejections", ["rejection_date"])
    op.create_index("ix_quality_rejections_rejection_reason", "quality_rejections", ["rejection_reason"])
    op.create_index("ix_quality_rejections_disposition", "quality_rejections", ["disposition"])
    op.create_index("ix_quality_rejections_disposition_status", "quality_rejections", ["disposition_status"])


def downgrade() -> None:
    op.drop_index("ix_quality_rejections_disposition_status", table_name="quality_rejections")
    op.drop_index("ix_quality_rejections_disposition", table_name="quality_rejections")
    op.drop_index("ix_quality_rejections_rejection_reason", table_name="quality_rejections")
    op.drop_index("ix_quality_rejections_rejection_date", table_name="quality_rejections")
    op.drop_index("ix_quality_rejections_production_output_id", table_name="quality_rejections")
    op.drop_index("ix_quality_rejections_quality_defect_id", table_name="quality_rejections")
    op.drop_index("ix_quality_rejections_quality_check_id", table_name="quality_rejections")
    op.drop_index("ix_quality_rejections_organization_id", table_name="quality_rejections")
    op.drop_table("quality_rejections")
    op.execute("DROP TYPE IF EXISTS quality_rejection_reason")
    op.execute("DROP TYPE IF EXISTS quality_disposition")
    op.execute("DROP TYPE IF EXISTS quality_disposition_status")
