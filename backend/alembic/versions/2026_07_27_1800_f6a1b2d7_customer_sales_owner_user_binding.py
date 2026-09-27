"""customer_sales_owner_user_binding

Revision ID: f6a1b2d7
Revises: f6a1b2d6
Create Date: 2026-07-27 18:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6a1b2d7"
down_revision: Union[str, None] = "f6a1b2d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # assigned_sales_user_id was never wired to any eligibility/permission
    # logic and the frontend never actually populated it -- rename it to the
    # name this feature establishes as the real FK, and give it ON DELETE
    # SET NULL so removing a user doesn't block or cascade-delete customers.
    op.drop_constraint(
        "commercial_customers_assigned_sales_user_id_fkey",
        "commercial_customers",
        type_="foreignkey",
    )
    op.alter_column(
        "commercial_customers",
        "assigned_sales_user_id",
        new_column_name="sales_owner_user_id",
    )
    op.create_foreign_key(
        op.f("fk_commercial_customers_sales_owner_user_id_foundation_users"),
        "commercial_customers",
        "foundation_users",
        ["sales_owner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        "ALTER INDEX ix_commercial_customers_assigned_sales_user_id "
        "RENAME TO ix_commercial_customers_sales_owner_user_id"
    )

    # sales_owner_name was the free-text field actually used by the UI.
    # Keep the column (and its data) for reference, but rename it out of the
    # way so it's obviously deprecated and no schema/service code touches it.
    op.alter_column(
        "commercial_customers",
        "sales_owner_name",
        new_column_name="sales_owner_name_legacy",
    )


def downgrade() -> None:
    op.alter_column(
        "commercial_customers",
        "sales_owner_name_legacy",
        new_column_name="sales_owner_name",
    )

    op.execute(
        "ALTER INDEX ix_commercial_customers_sales_owner_user_id "
        "RENAME TO ix_commercial_customers_assigned_sales_user_id"
    )
    op.drop_constraint(
        op.f("fk_commercial_customers_sales_owner_user_id_foundation_users"),
        "commercial_customers",
        type_="foreignkey",
    )
    op.alter_column(
        "commercial_customers",
        "sales_owner_user_id",
        new_column_name="assigned_sales_user_id",
    )
    op.create_foreign_key(
        "commercial_customers_assigned_sales_user_id_fkey",
        "commercial_customers",
        "foundation_users",
        ["assigned_sales_user_id"],
        ["id"],
    )
