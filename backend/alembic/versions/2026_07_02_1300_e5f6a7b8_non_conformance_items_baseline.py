"""non_conformance_items_baseline

Revision ID: e5f6a7b8
Revises: d4e5f6a7
Create Date: 2026-07-02 13:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8"
down_revision: Union[str, None] = "d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "non_conformance_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("non_conformance_report_id", sa.UUID(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("item_reference", sa.String(length=255), nullable=True),
        sa.Column("item_name", sa.String(length=255), nullable=False),
        sa.Column("quantity_affected", sa.Numeric(14, 2), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("issue_description", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["non_conformance_report_id"], ["non_conformance_reports.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "non_conformance_report_id",
            "line_no",
            name="uq_non_conformance_items_report_line_no",
        ),
    )
    op.create_index(
        "ix_non_conformance_items_non_conformance_report_id",
        "non_conformance_items",
        ["non_conformance_report_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_non_conformance_items_non_conformance_report_id",
        table_name="non_conformance_items",
    )
    op.drop_table("non_conformance_items")
