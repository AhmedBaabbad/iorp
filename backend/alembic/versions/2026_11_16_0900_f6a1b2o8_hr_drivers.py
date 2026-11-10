"""HR-DRIVERS-001: employee identities and a unified transport driver directory."""
from alembic import op
import sqlalchemy as sa

revision = 'f6a1b2o8'
down_revision = 'f6a1b2o7'
branch_labels = None
depends_on = None


def check_duplicate_identities(bind):
    duplicates = bind.execute(sa.text("""SELECT organization_id, identity_no, count(*) AS total
        FROM shipping_drivers WHERE identity_no IS NOT NULL
        GROUP BY organization_id, identity_no HAVING count(*) > 1
        ORDER BY organization_id, identity_no""")).mappings().all()
    if duplicates:
        values = '; '.join(f"organization={r['organization_id']} identity_no={r['identity_no']!r} count={r['total']}" for r in duplicates)
        raise RuntimeError('Duplicate driver identities must be resolved before HR-DRIVERS-001: ' + values)


def upgrade():
    # Internal personal data belongs to workforce; discard legacy snapshots first.
    op.execute("UPDATE shipping_drivers SET name = '', phone = NULL, identity_no = NULL WHERE affiliation = 'internal'")
    check_duplicate_identities(op.get_bind())
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE workforce_worker_type ADD VALUE IF NOT EXISTS 'driver'")
    op.add_column('workforce_members', sa.Column('national_id', sa.String(40), nullable=True))
    op.create_index('uq_workforce_members_org_national_id', 'workforce_members', ['organization_id', 'national_id'],
                    unique=True, postgresql_where=sa.text('national_id IS NOT NULL'))
    for column in [sa.Column('email', sa.String(255)), sa.Column('license_no', sa.String(40)),
                   sa.Column('license_expiry', sa.Date()), sa.Column('default_vehicle_id', sa.Uuid()),
                   sa.Column('vehicle_type', sa.String(80)), sa.Column('notes', sa.Text())]:
        op.add_column('shipping_drivers', column)
    op.create_foreign_key('fk_driver_default_vehicle', 'shipping_drivers', 'shipping_vehicles', ['default_vehicle_id'], ['id'])
    op.create_index('uq_shipping_drivers_org_identity', 'shipping_drivers', ['organization_id', 'identity_no'],
                    unique=True, postgresql_where=sa.text('identity_no IS NOT NULL'))


def downgrade():
    # Legacy internal personal snapshots are intentionally not restored.
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM workforce_members WHERE worker_type::text = 'driver'")):
        raise RuntimeError('Cannot downgrade HR-DRIVERS-001 while driver employees exist; reclassify them explicitly first')
    op.drop_index('uq_shipping_drivers_org_identity', table_name='shipping_drivers')
    op.drop_constraint('fk_driver_default_vehicle', 'shipping_drivers', type_='foreignkey')
    for name in ['notes', 'vehicle_type', 'default_vehicle_id', 'license_expiry', 'license_no', 'email']:
        op.drop_column('shipping_drivers', name)
    op.drop_index('uq_workforce_members_org_national_id', table_name='workforce_members')
    op.drop_column('workforce_members', 'national_id')
    labels = op.get_bind().scalars(sa.text("SELECT unnest(enum_range(NULL::workforce_worker_type))::text")).all()
    labels = ', '.join("'" + value.replace("'", "''") + "'" for value in labels if value != 'driver')
    op.execute('ALTER TYPE workforce_worker_type RENAME TO workforce_worker_type_before_hr')
    op.execute('CREATE TYPE workforce_worker_type AS ENUM (' + labels + ')')
    op.execute('ALTER TABLE workforce_members ALTER COLUMN worker_type TYPE workforce_worker_type USING worker_type::text::workforce_worker_type')
    op.execute('DROP TYPE workforce_worker_type_before_hr')
