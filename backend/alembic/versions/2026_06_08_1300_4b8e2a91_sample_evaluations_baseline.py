"""sample_evaluations_baseline

Revision ID: 4b8e2a91
Revises: 7f3a9c2e
Create Date: 2026-06-08 13:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4b8e2a91"
down_revision: Union[str, None] = "7f3a9c2e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "commercial_sample_evaluations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("sample_id", sa.UUID(), nullable=False),
        sa.Column("evaluation_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "result_status",
            sa.Enum(
                "accepted",
                "rejected",
                "needs_modification",
                name="sample_evaluation_result_status",
            ),
            nullable=False,
        ),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column(
            "next_action",
            sa.Enum(
                "proceed_to_quote",
                "revise_sample",
                "close_request",
                "further_review",
                name="sample_evaluation_next_action",
            ),
            nullable=False,
        ),
        sa.Column("evaluated_by_user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["evaluated_by_user_id"], ["foundation_users.id"]),
        sa.ForeignKeyConstraint(["sample_id"], ["commercial_samples.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_commercial_sample_evaluations_evaluated_by_user_id"), "commercial_sample_evaluations", ["evaluated_by_user_id"], unique=False)
    op.create_index(op.f("ix_commercial_sample_evaluations_sample_id"), "commercial_sample_evaluations", ["sample_id"], unique=False)


def downgrade() -> None:
    op.drop_index(
        op.f("ix_commercial_sample_evaluations_sample_id"),
        table_name="commercial_sample_evaluations",
    )
    op.drop_index(
        op.f("ix_commercial_sample_evaluations_evaluated_by_user_id"),
        table_name="commercial_sample_evaluations",
    )
    op.drop_table("commercial_sample_evaluations")
