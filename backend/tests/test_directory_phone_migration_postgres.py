import importlib.util
import logging
import os
from pathlib import Path
from uuid import uuid4
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.core.db import engine

pytestmark=pytest.mark.skipif(os.getenv('RUN_POSTGRES_TESTS')!='1',reason='Isolated PostgreSQL opt-in')

def test_phone_migration_preserves_invalid_values_and_logs_ids_only(caplog):
    path=Path(__file__).parents[1]/'alembic/versions/2026_11_23_0900_f6a1b2p6_directory_phone_integrity.py'
    spec=importlib.util.spec_from_file_location('phone_integrity_migration',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    schema='phone_integrity_'+uuid4().hex
    with engine.begin() as c:c.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    try:
        with isolated.begin() as c, Operations.context(MigrationContext.configure(c)):
            grouped={}
            for table,col,size in migration.FIELDS:grouped.setdefault(table,[]).append((col,size))
            for name,columns in grouped.items():
                fields=', '.join(f'{col} varchar({size})' for col,size in columns)
                key='organization_id' if name=='foundation_organization_branding' else 'id'
                c.execute(sa.text(f'CREATE TABLE {name} ({key} uuid PRIMARY KEY, {fields})'))
                if name not in ('commercial_customer_contacts','workforce_members','commercial_customers'):
                    names=', '.join(col for col,_ in columns)
                    values=', '.join("'0551234567'" for _ in columns)
                    c.execute(sa.text(f'INSERT INTO {name} ({key},{names}) VALUES (:id,{values})'),{'id':uuid4()})
            valid,invalid,oversized=uuid4(),uuid4(),uuid4()
            c.execute(sa.text("INSERT INTO commercial_customer_contacts (id,phone) VALUES (:id,'٠٥٥ ١٢٣ ٤٥٦٧')"),{'id':valid})
            secret='unconvertible-private-phone'
            long_secret='unconvertible-private-phone-exceeds-thirty'
            c.execute(sa.text('INSERT INTO workforce_members (id,phone) VALUES (:id,:value)'),{'id':invalid,'value':secret})
            c.execute(sa.text('INSERT INTO commercial_customers (id,phone) VALUES (:id,:value)'),{'id':oversized,'value':long_secret})
            with caplog.at_level(logging.WARNING,logger='alembic.runtime.migration'):migration.upgrade()
            assert c.scalar(sa.text('SELECT phone FROM commercial_customer_contacts'))=='+966551234567'
            assert c.scalar(sa.text('SELECT phone FROM workforce_members'))==secret
            assert c.scalar(sa.text('SELECT phone FROM commercial_customers'))==long_secret
            for name,columns in grouped.items():
                if name not in ('commercial_customer_contacts','workforce_members','commercial_customers'):
                    for column,_ in columns:
                        assert c.scalar(sa.text(f'SELECT {column} FROM {name}'))=='+966551234567'
            assert str(invalid) in caplog.text and str(oversized) in caplog.text
            assert secret not in caplog.text and long_secret not in caplog.text
            migration.downgrade()
            assert c.scalar(sa.text('SELECT phone FROM commercial_customer_contacts'))=='+966551234567'
            migration.upgrade()
    finally:
        isolated.dispose()
        with engine.begin() as c:c.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
