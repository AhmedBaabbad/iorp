"""SALES-001: sales order and quotation lifecycle (status history, revisions), and retry-safe partial transfers of a
confirmed sales order to production demands. Existing records remain unlinked."""
from alembic import op
import sqlalchemy as sa

revision='f6a1b2k5'
down_revision='f6a1b2k4'
branch_labels=None
depends_on=None


def upgrade():
    for column in [sa.Column('confirmed_at',sa.DateTime(timezone=True)),sa.Column('confirmed_by_user_id',sa.Uuid()),
                   sa.Column('revision',sa.Integer(),nullable=False,server_default='1'),sa.Column('currency',sa.String(3)),
                   sa.Column('customer_reference',sa.String(120))]:
        op.add_column('commercial_orders',column)
    for column in [sa.Column('source_order_id',sa.Uuid()),sa.Column('source_order_number',sa.String(64)),sa.Column('transfer_key',sa.Uuid())]:
        op.add_column('production_demands',column)
    op.create_index('ix_production_demands_source_order_id','production_demands',['source_order_id'])
    op.create_unique_constraint('uq_demands_transfer_key','production_demands',['organization_id','transfer_key'])
    op.add_column('production_demand_items',sa.Column('source_order_item_id',sa.Uuid()))
    op.create_index('ix_production_demand_items_source_order_item_id','production_demand_items',['source_order_item_id'])
    op.add_column('commercial_quotes',sa.Column('revision',sa.Integer(),nullable=False,server_default='1'))
    op.create_table('commercial_status_history',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('organization_id',sa.Uuid(),sa.ForeignKey('foundation_organizations.id'),nullable=False),
        sa.Column('entity_type',sa.String(20),nullable=False),
        sa.Column('entity_id',sa.Uuid(),nullable=False),
        sa.Column('action',sa.String(30),nullable=False),
        sa.Column('from_status',sa.String(30)),
        sa.Column('to_status',sa.String(30),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('reason',sa.String(500)),
        sa.Column('actor_user_id',sa.Uuid(),sa.ForeignKey('foundation_users.id',ondelete='SET NULL')),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_commercial_status_history_entity','commercial_status_history',['organization_id','entity_type','entity_id','created_at'])


def downgrade():
    op.drop_index('ix_commercial_status_history_entity',table_name='commercial_status_history')
    op.drop_table('commercial_status_history')
    op.drop_column('commercial_quotes','revision')
    op.drop_index('ix_production_demand_items_source_order_item_id',table_name='production_demand_items')
    op.drop_column('production_demand_items','source_order_item_id')
    op.drop_constraint('uq_demands_transfer_key','production_demands',type_='unique')
    op.drop_index('ix_production_demands_source_order_id',table_name='production_demands')
    for field in ['transfer_key','source_order_number','source_order_id']: op.drop_column('production_demands',field)
    for field in ['customer_reference','currency','revision','confirmed_by_user_id','confirmed_at']: op.drop_column('commercial_orders',field)
