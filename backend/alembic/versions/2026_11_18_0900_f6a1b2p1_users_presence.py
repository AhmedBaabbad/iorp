"""USERS-UX-C: tenant presence and ensure the existing permanent-delete grant."""
from uuid import uuid4
from alembic import op
import sqlalchemy as sa

revision='f6a1b2p1'
down_revision='f6a1b2p0'
branch_labels=None
depends_on=None
CODE='foundation:users:delete'


def upgrade():
    op.add_column('foundation_users',sa.Column('last_seen_at',sa.DateTime(timezone=True),nullable=True))
    c=op.get_bind()
    # Existing successful sign-ins are known activity; do not label these users
    # "never signed in" after adding a previously absent presence column.
    c.execute(sa.text('UPDATE foundation_users SET last_seen_at=last_login_at WHERE last_login_at IS NOT NULL'))
    # The code/labels predate this endpoint; preserve explicit custom-role grants.
    for org in c.execute(sa.text('SELECT id FROM foundation_organizations')).scalars():
        permission=c.scalar(sa.text('SELECT id FROM foundation_permissions WHERE organization_id=:org AND code=:code'),dict(org=org,code=CODE))
        if permission is None:
            permission=uuid4()
            c.execute(sa.text("""INSERT INTO foundation_permissions(id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at)
                VALUES (:id,:org,:code,'Delete a user permanently','Deletes only unused accounts with no history.','foundation','users','delete',now(),now())"""),dict(id=permission,org=org,code=CODE))
        for role in c.execute(sa.text("SELECT id FROM foundation_roles WHERE organization_id=:org AND code='organization_admin'"),dict(org=org)).scalars():
            if not c.scalar(sa.text('SELECT 1 FROM foundation_role_permissions WHERE role_id=:role AND permission_id=:permission'),dict(role=role,permission=permission)):
                c.execute(sa.text('INSERT INTO foundation_role_permissions(id,role_id,permission_id,scope) VALUES (:id,:role,:permission,\'organization\')'),dict(id=uuid4(),role=role,permission=permission))


def downgrade():
    op.drop_column('foundation_users','last_seen_at')
    # Permission and grants existed before this revision; never remove them on rollback.
