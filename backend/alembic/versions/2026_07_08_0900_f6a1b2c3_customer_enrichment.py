"""customer_enrichment

Revision ID: f6a1b2c3
Revises: e5f6a7b8
Create Date: 2026-07-08 09:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6a1b2c3"
down_revision: Union[str, None] = "e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("commercial_customers", sa.Column("phone", sa.String(length=50), nullable=True))
    op.add_column("commercial_customers", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column(
        "commercial_customers",
        sa.Column("sales_owner_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "commercial_customers",
        sa.Column("key_influencer_name", sa.String(length=255), nullable=True),
    )

    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE customer_status ADD VALUE IF NOT EXISTS 'on_hold'")
        op.execute("ALTER TYPE customer_status ADD VALUE IF NOT EXISTS 'archived'")
        op.execute("ALTER TYPE customer_status ADD VALUE IF NOT EXISTS 'blacklisted'")
        op.execute("ALTER TYPE customer_relationship_stage ADD VALUE IF NOT EXISTS 'contacted'")
        op.execute("ALTER TYPE customer_relationship_stage ADD VALUE IF NOT EXISTS 'qualified'")
        op.execute("ALTER TYPE customer_relationship_stage ADD VALUE IF NOT EXISTS 'negotiating'")
        op.execute("ALTER TYPE customer_relationship_stage ADD VALUE IF NOT EXISTS 'trial_customer'")
        op.execute("ALTER TYPE customer_relationship_stage ADD VALUE IF NOT EXISTS 'active_customer'")
        op.execute("ALTER TYPE customer_relationship_stage ADD VALUE IF NOT EXISTS 'repeat_customer'")
        op.execute("ALTER TYPE customer_relationship_stage ADD VALUE IF NOT EXISTS 'strategic_customer'")

    op.execute(
        "UPDATE commercial_customers "
        "SET relationship_stage = 'active_customer' "
        "WHERE relationship_stage = 'customer'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE commercial_customers "
        "SET status = 'inactive' "
        "WHERE status IN ('on_hold', 'archived', 'blacklisted')"
    )
    op.execute(
        "UPDATE commercial_customers "
        "SET relationship_stage = CASE "
        "WHEN relationship_stage = 'active_customer' THEN 'customer' "
        "WHEN relationship_stage = 'prospect' THEN 'prospect' "
        "ELSE 'lead' "
        "END "
        "WHERE relationship_stage IN ("
        "'contacted', 'qualified', 'negotiating', 'trial_customer', "
        "'active_customer', 'repeat_customer', 'strategic_customer'"
        ")"
    )

    op.execute("ALTER TYPE customer_status RENAME TO customer_status_old")
    op.execute("CREATE TYPE customer_status AS ENUM ('active', 'inactive')")
    op.execute(
        "ALTER TABLE commercial_customers "
        "ALTER COLUMN status TYPE customer_status "
        "USING status::text::customer_status"
    )
    op.execute("DROP TYPE customer_status_old")

    op.execute("ALTER TYPE customer_relationship_stage RENAME TO customer_relationship_stage_old")
    op.execute("CREATE TYPE customer_relationship_stage AS ENUM ('lead', 'prospect', 'customer')")
    op.execute(
        "ALTER TABLE commercial_customers "
        "ALTER COLUMN relationship_stage TYPE customer_relationship_stage "
        "USING relationship_stage::text::customer_relationship_stage"
    )
    op.execute("DROP TYPE customer_relationship_stage_old")

    op.drop_column("commercial_customers", "key_influencer_name")
    op.drop_column("commercial_customers", "sales_owner_name")
    op.drop_column("commercial_customers", "email")
    op.drop_column("commercial_customers", "phone")
