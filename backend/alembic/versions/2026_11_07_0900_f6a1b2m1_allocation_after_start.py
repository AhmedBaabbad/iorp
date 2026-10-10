"""PROD-QUALITY-FIX-001 item 1: allocations may be added, changed and released while the production order is open
(draft, released, in progress, on hold). Each allocation records the order's status when it was made, so reports can
show quantities added after execution started.

Existing allocations were all made on draft orders (adding was allowed on drafts only), so they are filled with "draft".
"""
from alembic import op
import sqlalchemy as sa

revision = "f6a1b2m1"
down_revision = "f6a1b2k9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("production_allocations", sa.Column("order_status_at_allocation", sa.String(20)))
    filled = op.get_bind().execute(sa.text(
        "UPDATE production_allocations SET order_status_at_allocation = 'draft' WHERE order_status_at_allocation IS NULL")).rowcount
    print(f"production_allocations: order_status_at_allocation = 'draft' on {filled} existing allocation(s)")
    with op.batch_alter_table("production_allocations") as batch:
        batch.alter_column("order_status_at_allocation", existing_type=sa.String(20), nullable=False, server_default="draft")


def downgrade():
    with op.batch_alter_table("production_allocations") as batch:
        batch.drop_column("order_status_at_allocation")
