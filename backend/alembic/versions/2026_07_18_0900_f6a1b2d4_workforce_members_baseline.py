"""workforce_members_baseline

Revision ID: f6a1b2d4
Revises: f6a1b2d3
Create Date: 2026-07-18 09:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f6a1b2d4"
down_revision: Union[str, None] = "f6a1b2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


worker_type_enum = postgresql.ENUM(
    "operator",
    "technician",
    "supervisor",
    "helper",
    "sales_rep",
    "quality_inspector",
    "production_manager",
    "commercial_manager",
    "admin_support",
    "warehouse_staff",
    name="workforce_worker_type",
    create_type=False,
)
employment_type_enum = postgresql.ENUM(
    "employee",
    "contractor",
    "temporary",
    name="workforce_employment_type",
    create_type=False,
)
member_status_enum = postgresql.ENUM(
    "active",
    "inactive",
    "suspended",
    "terminated",
    name="workforce_member_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    worker_type_enum.create(bind, checkfirst=True)
    employment_type_enum.create(bind, checkfirst=True)
    member_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "workforce_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_code", sa.String(length=20), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("worker_type", worker_type_enum, nullable=False),
        sa.Column("employment_type", employment_type_enum, nullable=False),
        sa.Column("status", member_status_enum, nullable=False),
        sa.Column("is_system_user", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("primary_skill", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["foundation_organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["foundation_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "employee_code",
            name="uq_workforce_members_org_code",
        ),
        sa.UniqueConstraint("user_id", name="uq_workforce_members_user_id"),
    )
    op.create_index(
        op.f("ix_workforce_members_organization_id"),
        "workforce_members",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workforce_members_user_id"),
        "workforce_members",
        ["user_id"],
        unique=False,
    )
    op.alter_column("workforce_members", "is_system_user", server_default=None)
    op.create_table(
        "workforce_code_counters",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["foundation_organizations.id"]),
        sa.PrimaryKeyConstraint("organization_id"),
    )


def downgrade() -> None:
    op.drop_table("workforce_code_counters")
    op.drop_index(op.f("ix_workforce_members_user_id"), table_name="workforce_members")
    op.drop_index(op.f("ix_workforce_members_organization_id"), table_name="workforce_members")
    op.drop_table("workforce_members")

    bind = op.get_bind()
    member_status_enum.drop(bind, checkfirst=True)
    employment_type_enum.drop(bind, checkfirst=True)
    worker_type_enum.drop(bind, checkfirst=True)
