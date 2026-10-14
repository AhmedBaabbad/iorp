"""Exercise frozen complaint DDL only in a disposable PostgreSQL schema."""
import importlib.util
import os
from pathlib import Path
from uuid import uuid4
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.core.db import Base, engine
from app.main import app  # Register all metadata.

pytestmark=pytest.mark.skipif(os.environ.get('RUN_POSTGRES_TESTS')!='1',reason='Isolated PostgreSQL opt-in')


def load(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).parents[1]/f'alembic/versions/{name}.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_complaints_upgrade_downgrade_round_trip():
    migration=load('2026_11_08_0900_f6a1b2n1_customer_complaints')
    second=load('2026_11_08_1000_f6a1b2n2_complaint_history_and_roles')
    third=load('2026_11_08_1100_f6a1b2n3_complaint_simpler_flow')
    schema='test_complaints_'+uuid4().hex
    with engine.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    try:
        tables=[t for t in Base.metadata.sorted_tables if not t.name.startswith('commercial_complaint')]
        Base.metadata.create_all(isolated,tables=tables)
        with isolated.begin() as connection,Operations.context(MigrationContext.configure(connection)):
            org=uuid4()
            connection.execute(sa.text("INSERT INTO foundation_organizations(id,name,code,status,timezone,default_locale,created_at,updated_at) VALUES (:id,'Test','COMPLAINT','active','UTC','ar',now(),now())"),dict(id=org))
            migration.upgrade()
            assert connection.scalar(sa.text("SELECT count(*) FROM foundation_permissions WHERE code LIKE 'commercial:complaints:%'"))==10
            assert len([n for n in sa.inspect(connection).get_table_names() if n.startswith('commercial_complaint')])==5
            migration.downgrade()
            assert connection.scalar(sa.text("SELECT count(*) FROM foundation_permissions WHERE code LIKE 'commercial:complaints:%'"))==0
            migration.upgrade()
            assert connection.scalar(sa.text('SELECT count(*) FROM commercial_complaints'))==0
            # The second step on a complaint whose history was written as one text.
            user,customer,complaint=uuid4(),uuid4(),uuid4()
            connection.execute(sa.text("INSERT INTO foundation_users(id,organization_id,email,full_name,password_hash,status,is_organization_root,created_at,updated_at) "
                                       "VALUES (:u,:o,'c@example.test','Owner','x','active',false,now(),now())"),dict(u=user,o=org))
            connection.execute(Base.metadata.tables['commercial_customers'].insert().values(id=customer,organization_id=org,customer_code='C1',name='Customer'))
            connection.execute(sa.text("INSERT INTO commercial_complaints(id,organization_id,customer_id,number,title,statement,channel,received_date,category,priority,department,status,finding,"
                                       "created_by,version,created_at,updated_at) VALUES (:i,:o,:c,'CMP-1','T','S','email','2026-10-11','quality','medium','commercial','new','pending',:u,1,now(),now())"),
                               dict(i=complaint,o=org,c=customer,u=user))
            old=f'commercial; {user}; 2026-10-12: Follow up'
            connection.execute(sa.text("INSERT INTO commercial_complaint_events(id,organization_id,complaint_id,actor_id,action,notes,created_at) VALUES (:i,:o,:c,:u,'assign',:n,now())"),
                               dict(i=uuid4(),o=org,c=complaint,u=user,n=old))
            second.upgrade()
            details,notes=connection.execute(sa.text('SELECT details,notes FROM commercial_complaint_events')).one()
            assert details==dict(department='commercial',owner_user_id=str(user),due_date='2026-10-12') and notes=='Follow up'
            assert 'commercial_complaint_item_properties' in sa.inspect(connection).get_table_names()
            connection.execute(sa.text("UPDATE commercial_complaints SET status='assessment', waiting_reason='Samples on the way'"))
            third.upgrade()
            assert connection.scalar(sa.text('SELECT status FROM commercial_complaints'))=='processing'
            assert connection.scalar(sa.text("SELECT notes FROM commercial_complaint_events WHERE action='note'"))=='Samples on the way'
            assert 'waiting_reason' not in {c['name'] for c in sa.inspect(connection).get_columns('commercial_complaints')}
            third.downgrade()
            connection.execute(sa.text("DELETE FROM commercial_complaint_events WHERE action='note'"))
            second.downgrade()
            assert connection.scalar(sa.text('SELECT notes FROM commercial_complaint_events'))==old
    finally:
        isolated.dispose()
        with engine.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
