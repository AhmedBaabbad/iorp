"""follow_ups_baseline

Revision ID: d83be9fa7120
Revises: c72a8bb29d44
Create Date: 2026-05-26 10:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d83be9fa7120"
down_revision: Union[str, None] = "c72a8bb29d44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "commercial_follow_ups",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("interaction_id", sa.UUID(), nullable=True),
        sa.Column("assigned_user_id", sa.UUID(), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("priority", sa.Enum("low", "medium", "high", name="follow_up_priority"), nullable=False),
        sa.Column("status", sa.Enum("pending", "completed", "cancelled", name="follow_up_status"), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["foundation_users.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["commercial_customers.id"]),
        sa.ForeignKeyConstraint(["interaction_id"], ["commercial_customer_interactions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_commercial_follow_ups_assigned_user_id"), "commercial_follow_ups", ["assigned_user_id"], unique=False)
    op.create_index(op.f("ix_commercial_follow_ups_customer_id"), "commercial_follow_ups", ["customer_id"], unique=False)
    op.create_index(op.f("ix_commercial_follow_ups_interaction_id"), "commercial_follow_ups", ["interaction_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_commercial_follow_ups_interaction_id"), table_name="commercial_follow_ups")
    op.drop_index(op.f("ix_commercial_follow_ups_customer_id"), table_name="commercial_follow_ups")
    op.drop_index(op.f("ix_commercial_follow_ups_assigned_user_id"), table_name="commercial_follow_ups")
    op.drop_table("commercial_follow_ups")
