"""Run the frozen migration against a disposable PostgreSQL schema, never production tables."""
import importlib.util
import os
from pathlib import Path
from uuid import uuid4
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.core.db import Base,engine
from app.main import app

pytestmark=pytest.mark.skipif(os.environ.get('RUN_POSTGRES_TESTS')!='1',reason='Isolated PostgreSQL opt-in')

def test_directory_upgrade_downgrade_and_legacy_baseline():
    spec=importlib.util.spec_from_file_location('directory_migration',Path(__file__).parents[1]/'alembic/versions/2026_11_12_0900_f6a1b2o3_reference_directories.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    schema='test_directory_'+uuid4().hex
    with engine.begin() as c:c.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    changes={'shipping_shipments':['driver_id','vehicle_id','carrier_id','driver_affiliation','customer_contact_id','delivery_site_id'],
             'procurement_receipts':['driver_id','vehicle_id','driver_affiliation'],'procurement_purchase_orders':['supplier_contact_id']}
    try:
        Base.metadata.create_all(isolated)
        with isolated.begin() as c,Operations.context(MigrationContext.configure(c)):
            for table in reversed(migration.TABLES):
                c.execute(sa.text(f'DROP TABLE {table}'))
            for table,columns in changes.items():
                for column in columns:c.execute(sa.text(f'ALTER TABLE {table} DROP COLUMN {column}'))
            migration.upgrade()
            assert 'shipping_drivers' in sa.inspect(c).get_table_names()
            migration.downgrade()
            assert 'shipping_drivers' not in sa.inspect(c).get_table_names()
            org=uuid4()
            c.execute(sa.text("INSERT INTO foundation_organizations(id,name,code,status,timezone,default_locale,created_at,updated_at) VALUES (:id,'Test','DIRECTORY','active','UTC','ar',now(),now())"),dict(id=org))
            customer=uuid4();quote=uuid4();user=uuid4()
            c.execute(Base.metadata.tables['foundation_users'].insert().values(id=user,organization_id=org,email='test@example.test',full_name='Tester',password_hash='unused',status='active',is_organization_root=False))
            c.execute(Base.metadata.tables['commercial_customers'].insert().values(id=customer,organization_id=org,customer_code='C1',name='Customer'))
            c.execute(Base.metadata.tables['commercial_quotes'].insert().values(id=quote,organization_id=org,customer_id=customer,created_by_user_id=user,quote_number='Q1',issue_date=sa.func.now(),valid_until=sa.func.now(),status='issued',revision=1,currency='SAR',subtotal_amount=0,tax_amount=0,discount_amount=0,total_amount=0))
            c.execute(Base.metadata.tables['commercial_quote_terms'].insert().values(organization_id=org,title_en='Payment',body_en='Original migration baseline',is_active=True))
            migration.upgrade()
            saved=c.execute(sa.text('SELECT source,terms FROM commercial_quote_terms_snapshots')).one()
            assert saved.source=='legacy_baseline' and saved.terms[0]['body_en']=='Original migration baseline'
            assert c.scalar(sa.text("SELECT count(*) FROM foundation_permissions WHERE code LIKE 'shipping:directory:%'"))==2
            with pytest.raises(RuntimeError,match='discard'):migration.downgrade()
    finally:
        isolated.dispose()
        with engine.begin() as c:c.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
