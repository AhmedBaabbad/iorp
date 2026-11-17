"""Opt-in numeric specification ranges and shipment/return thickness upper bounds."""
from alembic import op
import sqlalchemy as sa

revision = 'f6a1b2p4'
down_revision = 'f6a1b2p3'
branch_labels = depends_on = None

TABLES = ('shipping_shipment_lines', 'shipping_return_lines')


def upgrade():
    op.add_column("quality_certificates", sa.Column("product_specification", sa.JSON(), nullable=True))
    op.add_column('masterdata_product_properties', sa.Column('allows_range', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_check_constraint('ck_product_property_range_number', 'masterdata_product_properties', "NOT allows_range OR kind = 'number'")
    for table in TABLES:
        op.add_column(table, sa.Column('thickness_max_mm', sa.Numeric(10, 3), nullable=True))
        op.create_check_constraint('ck_' + table + '_thickness_range', table,
            'thickness_max_mm IS NULL OR (thickness_mm IS NOT NULL AND thickness_max_mm >= thickness_mm)')


def downgrade():
    op.drop_column("quality_certificates", "product_specification")
    for table in reversed(TABLES):
        op.drop_constraint('ck_' + table + '_thickness_range', table, type_='check')
        op.drop_column(table, 'thickness_max_mm')
    op.drop_constraint('ck_product_property_range_number', 'masterdata_product_properties', type_='check')
    op.drop_column('masterdata_product_properties', 'allows_range')
