"""customer_created_by

Revision ID: f6a1b2c4
Revises: f6a1b2c3
Create Date: 2026-07-09 09:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6a1b2c4"
down_revision: Union[str, None] = "f6a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "commercial_customers",
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
    )
    op.create_index(
        op.f("ix_commercial_customers_created_by_user_id"),
        "commercial_customers",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_commercial_customers_created_by_user_id_foundation_users"),
        "commercial_customers",
        "foundation_users",
        ["created_by_user_id"],
        ["id"],
    )
    op.execute(
        """
        UPDATE commercial_customers AS customer
        SET created_by_user_id = (
            SELECT foundation_users.id
            FROM foundation_users
            WHERE foundation_users.organization_id = customer.organization_id
            ORDER BY foundation_users.created_at ASC
            LIMIT 1
        )
        WHERE customer.created_by_user_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_commercial_customers_created_by_user_id_foundation_users"),
        "commercial_customers",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_commercial_customers_created_by_user_id"),
        table_name="commercial_customers",
    )
    op.drop_column("commercial_customers", "created_by_user_id")
