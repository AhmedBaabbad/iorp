"""quality_defects_baseline

Revision ID: b2c3d4e5
Revises: a1b2c3d4
Create Date: 2026-07-02 10:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5"
down_revision: Union[str, None] = "a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "quality_defects",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("quality_check_id", sa.UUID(), nullable=False),
        # Optional Production context references: plain UUIDs, no FK constraints.
        sa.Column("production_order_id", sa.UUID(), nullable=True),
        sa.Column("production_order_item_id", sa.UUID(), nullable=True),
        sa.Column("production_output_id", sa.UUID(), nullable=True),
        sa.Column("defect_date", sa.Date(), nullable=False),
        sa.Column(
            "defect_category",
            sa.Enum(
                "dimension",
                "thickness",
                "surface",
                "color",
                "strength",
                "winding",
                "weight",
                "packaging",
                "labeling",
                "finish",
                "other",
                name="quality_defect_category",
            ),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.Enum(
                "minor",
                "major",
                "critical",
                name="quality_defect_severity",
            ),
            nullable=False,
        ),
        sa.Column("defect_count", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("detected_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["foundation_organizations.id"]),
        sa.ForeignKeyConstraint(["quality_check_id"], ["quality_checks.id"]),
        sa.ForeignKeyConstraint(["detected_by_user_id"], ["foundation_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quality_defects_organization_id", "quality_defects", ["organization_id"])
    op.create_index("ix_quality_defects_quality_check_id", "quality_defects", ["quality_check_id"])
    op.create_index("ix_quality_defects_production_order_id", "quality_defects", ["production_order_id"])
    op.create_index("ix_quality_defects_production_output_id", "quality_defects", ["production_output_id"])
    op.create_index("ix_quality_defects_defect_date", "quality_defects", ["defect_date"])
    op.create_index("ix_quality_defects_defect_category", "quality_defects", ["defect_category"])
    op.create_index("ix_quality_defects_severity", "quality_defects", ["severity"])


def downgrade() -> None:
    op.drop_index("ix_quality_defects_severity", table_name="quality_defects")
    op.drop_index("ix_quality_defects_defect_category", table_name="quality_defects")
    op.drop_index("ix_quality_defects_defect_date", table_name="quality_defects")
    op.drop_index("ix_quality_defects_production_output_id", table_name="quality_defects")
    op.drop_index("ix_quality_defects_production_order_id", table_name="quality_defects")
    op.drop_index("ix_quality_defects_quality_check_id", table_name="quality_defects")
    op.drop_index("ix_quality_defects_organization_id", table_name="quality_defects")
    op.drop_table("quality_defects")
    op.execute("DROP TYPE IF EXISTS quality_defect_category")
    op.execute("DROP TYPE IF EXISTS quality_defect_severity")
