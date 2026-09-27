"""work_centers_baseline

Revision ID: 6f2a8c1d
Revises: 3c7f1a9b
Create Date: 2026-06-28 09:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6f2a8c1d"
down_revision: Union[str, None] = "3c7f1a9b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "production_work_centers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "center_type",
            sa.Enum(
                "extrusion",
                "rewinding",
                "packing",
                "quality_station",
                "generic",
                name="production_work_center_type",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "inactive",
                "under_maintenance",
                name="production_work_center_status",
            ),
            nullable=False,
        ),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["foundation_organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_production_work_centers_org_code"),
    )
    op.create_index(
        op.f("ix_production_work_centers_organization_id"),
        "production_work_centers",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_production_work_centers_organization_id"),
        table_name="production_work_centers",
    )
    op.drop_table("production_work_centers")
