"""customer_interactions_baseline

Revision ID: c72a8bb29d44
Revises: b41f7a2c9d13
Create Date: 2026-05-26 09:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c72a8bb29d44"
down_revision: Union[str, None] = "b41f7a2c9d13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "commercial_customer_interactions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column(
            "interaction_type",
            sa.Enum("call", "visit", "whatsapp", "email", "meeting", name="customer_interaction_type"),
            nullable=False,
        ),
        sa.Column("interaction_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("outcome", sa.String(length=255), nullable=True),
        sa.Column("next_step_hint", sa.String(length=255), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["foundation_users.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["commercial_customers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_commercial_customer_interactions_created_by_user_id"),
        "commercial_customer_interactions",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_commercial_customer_interactions_customer_id"),
        "commercial_customer_interactions",
        ["customer_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_commercial_customer_interactions_customer_id"),
        table_name="commercial_customer_interactions",
    )
    op.drop_index(
        op.f("ix_commercial_customer_interactions_created_by_user_id"),
        table_name="commercial_customer_interactions",
    )
    op.drop_table("commercial_customer_interactions")
