"""Keep allocation-time specifications independently of later demand corrections."""
import logging
from alembic import op
import sqlalchemy as sa

revision = 'f6a1b2p9'
down_revision = 'f6a1b2p8'
branch_labels = depends_on = None
log = logging.getLogger('alembic.runtime.migration')


def upgrade():
    op.add_column('production_allocations', sa.Column('target_spec_json_snapshot', sa.JSON(), nullable=True))
    op.add_column('production_allocations', sa.Column('product_type_snapshot', sa.String(100), nullable=True))
    op.create_index('ix_foundation_activity_record_history', 'foundation_activity_log',
                    ['organization_id', 'entity_type', 'entity_id', 'created_at', 'id'])
    # unit already is an immutable allocation-time snapshot. Preserve it.
    # Released rows use the order line if available, otherwise the demand item.
    # Alembic's enclosing transaction covers both statuses; no commits here.
    for status in ('active', 'released'):
        result = op.get_bind().execute(sa.text('''
            UPDATE production_allocations a SET target_spec_json_snapshot=s.spec,
                product_type_snapshot=s.product
            FROM (
                SELECT old.id,
                    CASE WHEN old.status='released' AND oi.id IS NOT NULL
                        THEN oi.target_spec_json ELSE di.target_spec_json END AS spec,
                    CASE WHEN old.status='released' AND oi.id IS NOT NULL
                        THEN po.product_type ELSE di.product_type END AS product
                FROM production_allocations old
                JOIN production_demand_items di ON di.id=old.production_demand_item_id
                JOIN production_orders po ON po.id=old.production_order_id AND po.organization_id=old.organization_id
                LEFT JOIN production_order_items oi ON oi.id=old.production_order_item_id AND oi.production_order_id=po.id
                WHERE old.status=:status
            ) s WHERE a.id=s.id
        '''), {'status': status})
        log.info('Allocation snapshots backfilled: status=%s rows=%s', status, result.rowcount)


def downgrade():
    op.drop_index('ix_foundation_activity_record_history', table_name='foundation_activity_log')
    op.drop_column('production_allocations', 'product_type_snapshot')
    op.drop_column('production_allocations', 'target_spec_json_snapshot')
