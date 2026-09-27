"""non_conformance_reports_baseline

Revision ID: d4e5f6a7
Revises: c3d4e5f6
Create Date: 2026-07-02 12:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7"
down_revision: Union[str, None] = "c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "non_conformance_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("report_number", sa.String(length=32), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column(
            "source_type",
            sa.Enum(
                "internal_production",
                "incoming_material",
                "supplier",
                "warehouse",
                "customer_return",
                "other",
                name="quality_ncr_source_type",
            ),
            nullable=False,
        ),
        sa.Column(
            "report_type",
            sa.Enum(
                "material_non_conformance",
                "product_non_conformance",
                "process_non_conformance",
                "packaging_non_conformance",
                "documentation_non_conformance",
                "other",
                name="quality_ncr_report_type",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "open",
                "under_review",
                "closed",
                name="quality_ncr_status",
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reference_code", sa.String(length=255), nullable=True),
        sa.Column("quality_check_id", sa.UUID(), nullable=True),
        sa.Column("quality_rejection_id", sa.UUID(), nullable=True),
        sa.Column("detected_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["foundation_organizations.id"]),
        sa.ForeignKeyConstraint(["detected_by_user_id"], ["foundation_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "report_number",
            name="uq_non_conformance_reports_org_report_number",
        ),
    )
    op.create_index("ix_non_conformance_reports_organization_id", "non_conformance_reports", ["organization_id"])
    op.create_index("ix_non_conformance_reports_report_date", "non_conformance_reports", ["report_date"])
    op.create_index("ix_non_conformance_reports_source_type", "non_conformance_reports", ["source_type"])
    op.create_index("ix_non_conformance_reports_report_type", "non_conformance_reports", ["report_type"])
    op.create_index("ix_non_conformance_reports_status", "non_conformance_reports", ["status"])
    op.create_index("ix_non_conformance_reports_quality_check_id", "non_conformance_reports", ["quality_check_id"])
    op.create_index(
        "ix_non_conformance_reports_quality_rejection_id",
        "non_conformance_reports",
        ["quality_rejection_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_non_conformance_reports_quality_rejection_id", table_name="non_conformance_reports")
    op.drop_index("ix_non_conformance_reports_quality_check_id", table_name="non_conformance_reports")
    op.drop_index("ix_non_conformance_reports_status", table_name="non_conformance_reports")
    op.drop_index("ix_non_conformance_reports_report_type", table_name="non_conformance_reports")
    op.drop_index("ix_non_conformance_reports_source_type", table_name="non_conformance_reports")
    op.drop_index("ix_non_conformance_reports_report_date", table_name="non_conformance_reports")
    op.drop_index("ix_non_conformance_reports_organization_id", table_name="non_conformance_reports")
    op.drop_table("non_conformance_reports")
    op.execute("DROP TYPE IF EXISTS quality_ncr_source_type")
    op.execute("DROP TYPE IF EXISTS quality_ncr_report_type")
    op.execute("DROP TYPE IF EXISTS quality_ncr_status")
