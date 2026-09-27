"""follow_up_scheduling_and_assignment

Revision ID: f6a1b2d8
Revises: f6a1b2d7
Create Date: 2026-07-28 09:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6a1b2d8"
down_revision: Union[str, None] = "f6a1b2d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE follow_up_status ADD VALUE IF NOT EXISTS 'in_progress'")
        op.execute("ALTER TYPE follow_up_priority ADD VALUE IF NOT EXISTS 'urgent'")

    # created_by_user_id: new, nullable, backfilled from assigned_user_id
    # (the closest reasonable default -- there is no better historical signal).
    op.add_column(
        "commercial_follow_ups",
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
    )
    op.create_index(
        op.f("ix_commercial_follow_ups_created_by_user_id"),
        "commercial_follow_ups",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_commercial_follow_ups_created_by_user_id_foundation_users"),
        "commercial_follow_ups",
        "foundation_users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        "UPDATE commercial_follow_ups SET created_by_user_id = assigned_user_id "
        "WHERE created_by_user_id IS NULL"
    )

    # updated_at: new, backfilled from created_at.
    op.add_column(
        "commercial_follow_ups",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE commercial_follow_ups SET updated_at = created_at WHERE updated_at IS NULL")
    op.alter_column("commercial_follow_ups", "updated_at", nullable=False)

    # assigned_user_id must become nullable to support ON DELETE SET NULL.
    op.drop_constraint(
        "commercial_follow_ups_assigned_user_id_fkey",
        "commercial_follow_ups",
        type_="foreignkey",
    )
    op.alter_column("commercial_follow_ups", "assigned_user_id", nullable=True)
    op.create_foreign_key(
        op.f("fk_commercial_follow_ups_assigned_user_id_foundation_users"),
        "commercial_follow_ups",
        "foundation_users",
        ["assigned_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # interaction_id: add ON DELETE SET NULL (was unspecified/RESTRICT-like before).
    op.drop_constraint(
        "commercial_follow_ups_interaction_id_fkey",
        "commercial_follow_ups",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_commercial_follow_ups_interaction_id_commercial_customer_interactions"),
        "commercial_follow_ups",
        "commercial_customer_interactions",
        ["interaction_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Worklist query indexes.
    op.create_index(
        op.f("ix_commercial_follow_ups_due_date"),
        "commercial_follow_ups",
        ["due_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_commercial_follow_ups_status"),
        "commercial_follow_ups",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_commercial_follow_ups_status_due_date",
        "commercial_follow_ups",
        ["status", "due_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_commercial_follow_ups_status_due_date", table_name="commercial_follow_ups")
    op.drop_index(op.f("ix_commercial_follow_ups_status"), table_name="commercial_follow_ups")
    op.drop_index(op.f("ix_commercial_follow_ups_due_date"), table_name="commercial_follow_ups")

    op.drop_constraint(
        op.f("fk_commercial_follow_ups_interaction_id_commercial_customer_interactions"),
        "commercial_follow_ups",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "commercial_follow_ups_interaction_id_fkey",
        "commercial_follow_ups",
        "commercial_customer_interactions",
        ["interaction_id"],
        ["id"],
    )

    op.drop_constraint(
        op.f("fk_commercial_follow_ups_assigned_user_id_foundation_users"),
        "commercial_follow_ups",
        type_="foreignkey",
    )
    op.execute(
        "DELETE FROM commercial_follow_ups WHERE assigned_user_id IS NULL"
    )
    op.alter_column("commercial_follow_ups", "assigned_user_id", nullable=False)
    op.create_foreign_key(
        "commercial_follow_ups_assigned_user_id_fkey",
        "commercial_follow_ups",
        "foundation_users",
        ["assigned_user_id"],
        ["id"],
    )

    op.drop_column("commercial_follow_ups", "updated_at")

    op.drop_constraint(
        op.f("fk_commercial_follow_ups_created_by_user_id_foundation_users"),
        "commercial_follow_ups",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_commercial_follow_ups_created_by_user_id"),
        table_name="commercial_follow_ups",
    )
    op.drop_column("commercial_follow_ups", "created_by_user_id")
