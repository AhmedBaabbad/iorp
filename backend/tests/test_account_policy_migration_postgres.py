import importlib.util
import os
from pathlib import Path
from uuid import uuid4
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.core.db import Base, engine
from app.main import app
pytestmark=pytest.mark.skipif(os.environ.get('RUN_POSTGRES_TESTS')!='1',reason='Isolated PostgreSQL opt-in')
def test_account_policy_upgrade_downgrade():
    spec=importlib.util.spec_from_file_location('account_migration',Path(__file__).parents[1]/'alembic/versions/2026_11_14_0900_f6a1b2o6_account_ownership.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    schema='test_account_'+uuid4().hex
    with engine.begin() as c:c.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated)
        with isolated.begin() as c,Operations.context(MigrationContext.configure(c)):
            migration.downgrade()
            assert 'foundation_user_email_changes' not in sa.inspect(c).get_table_names()
            migration.upgrade()
            assert 'foundation_user_email_changes' in sa.inspect(c).get_table_names()
            org=uuid4()
            c.execute(Base.metadata.tables['foundation_organizations'].insert().values(id=org,name='Test',code='TEST',status='active',timezone='UTC',default_locale='en'))
            c.execute(Base.metadata.tables['foundation_users'].insert().values(organization_id=org,email='test@example.test',full_name='Tester',password_hash='unused',status='inactive',timezone='Asia/Riyadh'))
            with pytest.raises(RuntimeError,match='discard'):migration.downgrade()
    finally:
        isolated.dispose()
        with engine.begin() as c:c.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
