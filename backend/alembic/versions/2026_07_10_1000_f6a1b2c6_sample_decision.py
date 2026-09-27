"""sample_decision

Revision ID: f6a1b2c6
Revises: f6a1b2c5
Create Date: 2026-07-10 10:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f6a1b2c6"
down_revision: Union[str, None] = "f6a1b2c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


sample_decision_enum = postgresql.ENUM(
    "accepted",
    "rejected",
    name="sampledecision_enum",
)


def upgrade() -> None:
    sample_decision_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "commercial_samples",
        sa.Column(
            "sample_decision",
            sample_decision_enum,
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("commercial_samples", "sample_decision")
    sample_decision_enum.drop(op.get_bind(), checkfirst=True)
