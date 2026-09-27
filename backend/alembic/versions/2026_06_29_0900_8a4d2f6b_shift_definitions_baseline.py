"""shift_definitions_baseline

Revision ID: 8a4d2f6b
Revises: 6f2a8c1d
Create Date: 2026-06-29 09:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8a4d2f6b"
down_revision: Union[str, None] = "6f2a8c1d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "production_shift_definitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("work_center_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "shift_type",
            sa.Enum(
                "morning",
                "evening",
                "night",
                "custom",
                name="production_shift_type",
            ),
            nullable=False,
        ),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("duration_hours", sa.Numeric(5, 2), nullable=False),
        sa.Column("crosses_midnight", sa.Boolean(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "inactive",
                name="production_shift_definition_status",
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["foundation_organizations.id"]),
        sa.ForeignKeyConstraint(["work_center_id"], ["production_work_centers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_production_shift_definitions_org_code"),
    )
    op.create_index(
        op.f("ix_production_shift_definitions_organization_id"),
        "production_shift_definitions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_production_shift_definitions_work_center_id"),
        "production_shift_definitions",
        ["work_center_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_production_shift_definitions_work_center_id"),
        table_name="production_shift_definitions",
    )
    op.drop_index(
        op.f("ix_production_shift_definitions_organization_id"),
        table_name="production_shift_definitions",
    )
    op.drop_table("production_shift_definitions")
