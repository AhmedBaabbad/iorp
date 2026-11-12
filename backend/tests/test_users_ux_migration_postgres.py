import importlib.util
import os
from pathlib import Path
from uuid import uuid4
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.core.db import Base,engine
from app.main import app  # noqa: F401

pytestmark=pytest.mark.skipif(os.environ.get('RUN_POSTGRES_TESTS')!='1',reason='Isolated PostgreSQL opt-in')


def test_presence_upgrade_downgrade_and_existing_administrator_grant():
    spec=importlib.util.spec_from_file_location('users_ux_migration',Path(__file__).parents[1]/'alembic/versions/2026_11_18_0900_f6a1b2p1_users_presence.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    schema='test_users_ux_'+uuid4().hex
    with engine.begin() as c:c.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated)
        with isolated.begin() as c,Operations.context(MigrationContext.configure(c)):
            migration.downgrade()
            org=uuid4();admin=uuid4();other=uuid4()
            c.execute(Base.metadata.tables['foundation_organizations'].insert().values(id=org,name='Synthetic',code='USERS-UX',status='active',timezone='UTC',default_locale='en'))
            for identifier,code in ((admin,'organization_admin'),(other,'custom_admin')):
                c.execute(Base.metadata.tables['foundation_roles'].insert().values(id=identifier,organization_id=org,code=code,name=code,description='',is_system=code=='organization_admin',is_protected=False))
            c.execute(sa.text("""INSERT INTO foundation_users(id,organization_id,email,full_name,password_hash,status,is_organization_root,
                last_login_at,failed_login_attempts,token_version,created_at,updated_at)
                VALUES (:id,:org,'known@example.com','Known user','unused','active',false,now()-interval '1 day',0,0,now(),now())"""),{'id':uuid4(),'org':org})
            migration.upgrade()
            col=next(col for col in sa.inspect(c).get_columns('foundation_users') if col['name']=='last_seen_at')
            assert col['nullable'] and col['type'].timezone
            assert c.scalar(sa.text('SELECT last_seen_at=last_login_at FROM foundation_users'))
            permission=c.scalar(sa.text("SELECT id FROM foundation_permissions WHERE organization_id=:org AND code='foundation:users:delete'"),{'org':org})
            assert permission
            assert list(c.execute(sa.text('SELECT role_id FROM foundation_role_permissions WHERE permission_id=:id'),{'id':permission}).scalars())==[admin]
            migration.downgrade()
            assert 'last_seen_at' not in {col['name'] for col in sa.inspect(c).get_columns('foundation_users')}
            migration.upgrade()
            assert c.scalar(sa.text('SELECT count(*) FROM foundation_role_permissions WHERE permission_id=:id'),{'id':permission})==1
    finally:
        isolated.dispose()
        with engine.begin() as c:c.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
