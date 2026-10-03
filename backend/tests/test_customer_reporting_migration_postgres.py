"""Real PostgreSQL migration test in a unique disposable schema, never the dev tenant."""
import importlib.util
import os
from pathlib import Path
from uuid import uuid4
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.core.db import Base, engine

pytestmark=pytest.mark.skipif(os.environ.get('RUN_POSTGRES_TESTS')!='1',reason='Isolated PostgreSQL opt-in')


def test_customer_permissions_upgrade_downgrade():
    path=Path(__file__).parents[1]/'alembic/versions/2026_10_11_0900_f6a1b2i1_customer_reports.py'
    spec=importlib.util.spec_from_file_location('customer_report_migration',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    schema='test_cust_report_'+uuid4().hex
    with engine.begin() as c:c.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated)
        with isolated.begin() as c,Operations.context(MigrationContext.configure(c)):
            oid,rid=uuid4(),uuid4()
            c.execute(sa.text("INSERT INTO foundation_organizations(id,name,code,status,timezone,default_locale,created_at,updated_at) VALUES (:id,'Test','CUST','active','UTC','ar',now(),now())"),dict(id=oid))
            c.execute(sa.text("INSERT INTO foundation_roles(id,organization_id,name,code,is_system,is_editable,is_protected,created_at,updated_at) VALUES (:id,:org,'Manager','commercial_manager',true,false,false,now(),now())"),dict(id=rid,org=oid))
            migration.upgrade()
            assert c.scalar(sa.text("SELECT count(*) FROM foundation_permissions WHERE code LIKE 'reports:customers:%'"))==8
            assert c.scalar(sa.text('SELECT count(*) FROM foundation_role_permissions'))==8
            migration.downgrade()
            assert c.scalar(sa.text('SELECT count(*) FROM foundation_role_permissions'))==0
            migration.upgrade()
            assert c.scalar(sa.text('SELECT count(*) FROM foundation_role_permissions'))==8
    finally:
        isolated.dispose()
        with engine.begin() as c:c.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))


def test_export_history_permission_removal_round_trip():
    path=Path(__file__).parents[1]/'alembic/versions/2026_10_12_0900_f6a1b2i2_remove_report_export_history.py'
    spec=importlib.util.spec_from_file_location('remove_export_history',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    schema='test_exports_perm_'+uuid4().hex
    with engine.begin() as c:c.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated)
        with isolated.begin() as c,Operations.context(MigrationContext.configure(c)):
            oid,rid,pid,gid=uuid4(),uuid4(),uuid4(),uuid4()
            c.execute(sa.text("INSERT INTO foundation_organizations(id,name,code,status,timezone,default_locale,created_at,updated_at) VALUES (:id,'Test','EXP','active','UTC','ar',now(),now())"),dict(id=oid))
            c.execute(sa.text("INSERT INTO foundation_roles(id,organization_id,name,code,is_system,is_editable,is_protected,created_at,updated_at) VALUES (:id,:org,'Manager','production_manager',true,false,false,now(),now())"),dict(id=rid,org=oid))
            c.execute(sa.text("INSERT INTO foundation_permissions(id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) VALUES (:id,:org,'reports:exports:read','Read','Read','reports','exports','read',now(),now())"),dict(id=pid,org=oid))
            c.execute(sa.text("INSERT INTO foundation_role_permissions(id,role_id,permission_id,scope) VALUES (:id,:role,:permission,'own')"),dict(id=gid,role=rid,permission=pid))
            before=c.execute(sa.text('SELECT id,role_id,permission_id,scope FROM foundation_role_permissions')).all()
            migration.upgrade()
            assert c.scalar(sa.text("SELECT count(*) FROM foundation_permissions WHERE code='reports:exports:read'"))==0
            assert c.scalar(sa.text('SELECT count(*) FROM foundation_role_permissions'))==0
            migration.downgrade()
            assert c.execute(sa.text('SELECT id,role_id,permission_id,scope FROM foundation_role_permissions')).all()==before
            assert c.scalar(sa.text("SELECT id FROM foundation_permissions WHERE code='reports:exports:read'"))==pid
    finally:
        isolated.dispose()
        with engine.begin() as c:c.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))



def test_quotation_document_migration_round_trip():
    path=Path(__file__).parents[1]/'alembic/versions/2026_10_13_0900_f6a1b2i3_quotation_document.py'
    spec=importlib.util.spec_from_file_location('quotation_document',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    schema='test_quote_doc_'+uuid4().hex
    with engine.begin() as c:c.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated)
        with isolated.begin() as c,Operations.context(MigrationContext.configure(c)):
            # The schema starts from today's models: remove what the migration adds, then run it.
            for table in ('commercial_quote_settings','commercial_quote_terms','foundation_bank_accounts'):
                c.execute(sa.text(f'DROP TABLE {table}'))
            for table,column in (('commercial_quotes','tax_rate'),('commercial_quotes','attention'),('commercial_quotes','subject'),
                                 ('commercial_quote_items','description_ar'),('commercial_quote_items','description_en')):
                c.execute(sa.text(f'ALTER TABLE {table} DROP COLUMN {column}'))
            oid,rid,other=uuid4(),uuid4(),uuid4()
            c.execute(sa.text("INSERT INTO foundation_organizations(id,name,code,status,timezone,default_locale,created_at,updated_at) VALUES (:id,'Test','QD','active','UTC','ar',now(),now())"),dict(id=oid))
            c.execute(sa.text("INSERT INTO foundation_roles(id,organization_id,name,code,is_system,is_editable,is_protected,created_at,updated_at) VALUES (:id,:org,'Manager','commercial_manager',true,false,false,now(),now())"),dict(id=rid,org=oid))
            c.execute(sa.text("INSERT INTO foundation_roles(id,organization_id,name,code,is_system,is_editable,is_protected,created_at,updated_at) VALUES (:id,:org,'Rep','sales_rep',true,false,false,now(),now())"),dict(id=other,org=oid))
            migration.upgrade()
            names={t for t in sa.inspect(c).get_table_names()}
            assert {'commercial_quote_settings','commercial_quote_terms','foundation_bank_accounts'}<=names
            assert {'tax_rate','attention','subject'}<={col['name'] for col in sa.inspect(c).get_columns('commercial_quotes')}
            granted=c.execute(sa.text("SELECT r.code,p.code FROM foundation_role_permissions rp JOIN foundation_roles r ON r.id=rp.role_id JOIN foundation_permissions p ON p.id=rp.permission_id")).all()
            assert sorted(granted)==[('commercial_manager','commercial:quote_settings:read'),('commercial_manager','commercial:quote_settings:update')]
            migration.downgrade()
            assert c.scalar(sa.text('SELECT count(*) FROM foundation_role_permissions'))==0
            assert 'commercial_quote_terms' not in sa.inspect(c).get_table_names()
            assert 'tax_rate' not in {col['name'] for col in sa.inspect(c).get_columns('commercial_quotes')}
    finally:
        isolated.dispose()
        with engine.begin() as c:c.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
