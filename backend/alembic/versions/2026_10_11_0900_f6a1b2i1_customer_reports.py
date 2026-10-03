"""Customer report permissions. No customer or production business data changes."""
from uuid import uuid4
import sqlalchemy as sa
from alembic import op

revision='f6a1b2i1'
down_revision='f6a1b2i0'
branch_labels=None
depends_on=None
KEYS=('customer_profile','directory','activity_summary','quotations_report','demand_fulfillment','growth_retention','customer_statement','internal_audience')
SALES=('customer_profile','customer_statement','demand_fulfillment','internal_audience')
BACKUP='customer_report_i1_added_grants'


def upgrade():
    bind=op.get_bind()
    op.create_table(BACKUP,sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('role_id',sa.Uuid(),nullable=False),sa.Column('permission_id',sa.Uuid(),nullable=False))
    for org in bind.scalars(sa.text('SELECT id FROM foundation_organizations')):
        for key in KEYS:
            code='reports:customers:'+key
            bind.execute(sa.text('INSERT INTO foundation_permissions(id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) VALUES (:id,:org,:code,:name,:description,\'reports\',\'customers\',:action,now(),now()) ON CONFLICT (organization_id,code) DO NOTHING'),
                dict(id=uuid4(),org=org,code=code,name=key,description='Generate customer report: '+key,action=key))
            pid=bind.scalar(sa.text('SELECT id FROM foundation_permissions WHERE organization_id=:org AND code=:code'),dict(org=org,code=code))
            roles=['organization_admin','commercial_manager']+(['sales_rep'] if key in SALES else [])
            for rid in bind.scalars(sa.text('SELECT id FROM foundation_roles WHERE organization_id=:org AND is_system AND code IN :roles').bindparams(sa.bindparam('roles',expanding=True)),dict(org=org,roles=roles)):
                added=bind.scalar(sa.text('INSERT INTO foundation_role_permissions(id,role_id,permission_id,scope) VALUES (:id,:role,:permission,\'organization\') ON CONFLICT (role_id,permission_id) DO NOTHING RETURNING id'),dict(id=uuid4(),role=rid,permission=pid))
                if added:
                    bind.execute(sa.text(f'INSERT INTO {BACKUP}(id,role_id,permission_id) VALUES (:id,:role,:permission)'),dict(id=added,role=rid,permission=pid))
        # Existing export audit permission: explicit system role grant, recorded for downgrade.
        pid=bind.scalar(sa.text("SELECT id FROM foundation_permissions WHERE organization_id=:org AND code='reports:exports:read'"),dict(org=org))
        if pid:
            for rid in bind.scalars(sa.text("SELECT id FROM foundation_roles WHERE organization_id=:org AND is_system AND code IN ('organization_admin','commercial_manager')"),dict(org=org)):
                added=bind.scalar(sa.text("INSERT INTO foundation_role_permissions(id,role_id,permission_id,scope) VALUES (:id,:role,:permission,'organization') ON CONFLICT (role_id,permission_id) DO NOTHING RETURNING id"),dict(id=uuid4(),role=rid,permission=pid))
                if added:
                    bind.execute(sa.text(f'INSERT INTO {BACKUP}(id,role_id,permission_id) VALUES (:id,:role,:permission)'),dict(id=added,role=rid,permission=pid))


def downgrade():
    bind=op.get_bind()
    bind.execute(sa.text(f'DELETE FROM foundation_role_permissions WHERE id IN (SELECT id FROM {BACKUP})'))
    op.drop_table(BACKUP)
    # Keep catalog rows and export audit; administrator-created grants are not removed.
