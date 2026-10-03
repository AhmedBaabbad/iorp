import importlib.util
import os
from pathlib import Path
from uuid import uuid4
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.core.db import Base, engine

pytestmark=pytest.mark.skipif(os.environ.get('RUN_POSTGRES_TESTS')!='1',reason='Isolated PostgreSQL test opt-in')

def test_branding_reporting_upgrade_downgrade_preserves_existing_logo():
    path=Path(__file__).parents[1]/'alembic/versions/2026_10_08_0900_f6a1b2h8_reporting_branding.py'
    spec=importlib.util.spec_from_file_location('reporting_migration',path);migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    schema='test_reporting_'+uuid4().hex
    with engine.begin() as c:c.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated)
        later=Path(__file__).parents[1]/'alembic/versions/2026_10_14_0900_f6a1b2i4_remove_report_audit.py'
        spec=importlib.util.spec_from_file_location('remove_report_audit',later);i4=importlib.util.module_from_spec(spec);spec.loader.exec_module(i4)
        with isolated.begin() as c,Operations.context(MigrationContext.configure(c)):
            i4.downgrade()  # today's models no longer have the audit tables that h8 created
            migration.downgrade()
            oid=uuid4()
            c.execute(sa.text("INSERT INTO foundation_organizations(id,name,code,status,timezone,default_locale,logo_path,created_at,updated_at) VALUES (:id,'Test','test','active','UTC','ar','organizations/existing/logo.png',now(),now())"),dict(id=oid))
            migration.upgrade()
            assert c.scalar(sa.text('SELECT count(*) FROM foundation_stored_assets'))==1
            assert c.scalar(sa.text('SELECT count(*) FROM foundation_organization_branding WHERE logo_asset_id IS NOT NULL'))==1
            assert c.scalar(sa.text("SELECT count(*) FROM foundation_permissions WHERE code LIKE 'reports:%'"))==5
            migration.downgrade()
            assert c.scalar(sa.text('SELECT logo_path FROM foundation_organizations'))=='organizations/existing/logo.png'
            migration.upgrade()
            c.execute(sa.text("INSERT INTO report_exports(id,organization_id,report_key,reference_no,params_json,format,status) VALUES (:id,:org,'test','RPT-TEST-2026-1','{}','html','success')"),dict(id=uuid4(),org=oid))
            with pytest.raises(RuntimeError,match='preserve'):
                migration.downgrade()
    finally:
        isolated.dispose()
        with engine.begin() as c:c.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))


def test_report_audit_removal_round_trip():
    path=Path(__file__).parents[1]/'alembic/versions/2026_10_14_0900_f6a1b2i4_remove_report_audit.py'
    spec=importlib.util.spec_from_file_location('remove_report_audit',path);migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    schema='test_report_audit_'+uuid4().hex
    with engine.begin() as c:c.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated)
        with isolated.begin() as c,Operations.context(MigrationContext.configure(c)):
            assert 'report_exports' not in sa.inspect(c).get_table_names()
            migration.downgrade()
            assert {'report_exports','report_counters'}<=set(sa.inspect(c).get_table_names())
            migration.upgrade()
            assert not {'report_exports','report_counters'}&set(sa.inspect(c).get_table_names())
    finally:
        isolated.dispose()
        with engine.begin() as c:c.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))

