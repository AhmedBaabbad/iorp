"""Separate business decisions from editing. Custom roles receive no implicit new powers."""
from uuid import uuid4
import sqlalchemy as sa
from alembic import op

revision='f6a1b2k7'
down_revision='f6a1b2k6'
branch_labels=None
depends_on=None
BACKUP='rbac_k7_added_grants'
ACTIONS={
    'production:shift_rosters':('close',),
    'shipping:shipments':('ready','reopen','reschedule'),
}


def upgrade():
    bind=op.get_bind()
    op.create_table(BACKUP,sa.Column('id',sa.Uuid(),primary_key=True))
    meta=sa.MetaData()
    orgs=sa.Table('foundation_organizations',meta,autoload_with=bind)
    permissions=sa.Table('foundation_permissions',meta,autoload_with=bind)
    roles=sa.Table('foundation_roles',meta,autoload_with=bind)
    grants=sa.Table('foundation_role_permissions',meta,autoload_with=bind)
    backup=sa.Table(BACKUP,meta,autoload_with=bind)
    # SQLite reflects PostgreSQL UUID declarations as NUMERIC; keep test and production binds typed.
    for table in (orgs,permissions,roles,grants,backup):
        for column in table.c:
            if column.name=='id' or column.name.endswith('_id'): column.type=sa.Uuid()
    from datetime import datetime,timezone
    now=datetime.now(timezone.utc)
    for org in bind.scalars(sa.select(orgs.c.id)):
        for prefix,actions in ACTIONS.items():
            module,resource=prefix.split(':')
            targets={'organization_admin'}
            if module=='commercial': targets.add('commercial_manager')
            if module=='production': targets.update({'factory_manager','production_manager'})
            if module=='quality': targets.update({'factory_manager','quality_manager'})
            if module=='shipping': targets.update({'factory_manager','shipping_manager','warehouse_manager'})
            for action in actions:
                code=prefix+':'+action
                pid=bind.scalar(sa.select(permissions.c.id).where(permissions.c.organization_id==org,permissions.c.code==code))
                if pid is None:
                    pid=uuid4()
                    bind.execute(permissions.insert().values(id=pid,organization_id=org,code=code,name=code,
                        description='Dedicated business action permission',module_name=module,resource_name=resource,
                        action_name=action,created_at=now,updated_at=now))
                for rid in bind.scalars(sa.select(roles.c.id).where(roles.c.organization_id==org,roles.c.is_system.is_(True),roles.c.code.in_(targets))):
                    if bind.scalar(sa.select(grants.c.id).where(grants.c.role_id==rid,grants.c.permission_id==pid)) is None:
                        gid=uuid4()
                        bind.execute(grants.insert().values(id=gid,role_id=rid,permission_id=pid,scope='organization'))
                        bind.execute(backup.insert().values(id=gid))


def downgrade():
    bind=op.get_bind()
    meta=sa.MetaData()
    grants=sa.Table('foundation_role_permissions',meta,autoload_with=bind)
    backup=sa.Table(BACKUP,meta,autoload_with=bind)
    for table in (grants,backup):
        for column in table.c:
            if column.name=='id' or column.name.endswith('_id'): column.type=sa.Uuid()
    bind.execute(grants.delete().where(grants.c.id.in_(sa.select(backup.c.id))))
    op.drop_table(BACKUP)
    # Preserve catalog rows/custom grants; downgrade never grants bundled powers.
