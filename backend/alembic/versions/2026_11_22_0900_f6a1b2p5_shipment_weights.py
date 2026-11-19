"""Per-unit net and optional shipment gross; existing weights are never backfilled."""
from alembic import op
import sqlalchemy as sa

revision = 'f6a1b2p5'
down_revision = 'f6a1b2p4'
branch_labels = depends_on = None


def upgrade():
    op.add_column('shipping_shipment_lines', sa.Column('unit_net_weight', sa.Numeric(14, 3), nullable=True))
    op.add_column('shipping_shipments', sa.Column('gross_weight_kg', sa.Numeric(14, 3), nullable=True))


def downgrade():
    op.drop_column('shipping_shipments', 'gross_weight_kg')
    op.drop_column('shipping_shipment_lines', 'unit_net_weight')
