"""Upgrade, CHECK and lossless rollback in a disposable PostgreSQL schema."""
import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.core.db import engine

pytestmark = pytest.mark.skipif(os.environ.get('RUN_POSTGRES_TESTS') != '1', reason='Isolated PostgreSQL opt-in')


def test_customer_names_backfill_check_and_lossless_downgrade():
    path = Path(__file__).parents[1] / 'alembic/versions/2026_11_20_0900_f6a1b2p3_customer_names.py'
    spec = importlib.util.spec_from_file_location('customer_names_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    schema = 'test_customer_names_' + uuid4().hex
    with engine.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        with isolated.begin() as connection, Operations.context(MigrationContext.configure(connection)):
            old = sa.Table('commercial_customers', sa.MetaData(),
                sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('name', sa.String(255), nullable=False))
            old.create(connection)
            names = ['عميل عربي', 'English customer', 'Mixed عميل', '\ufb50', '\U0001ee00', '  English  ']
            ids = [uuid4() for _ in names]
            connection.execute(old.insert(), [dict(id=i, name=n) for i, n in zip(ids, names)])
            migration.upgrade()
            customers = sa.Table('commercial_customers', sa.MetaData(), autoload_with=connection)
            for i, name in zip(ids, names):
                row = connection.execute(sa.select(customers).where(customers.c.id == i)).one()
                assert row.name == name
                assert row.name_ar == (name if migration.arabic(name) else None)
                assert row.name_en == (None if migration.arabic(name) else name)
            for ar, en in [(None, None), (' ', ''), ('', ' ')] :
                with pytest.raises(sa.exc.IntegrityError), connection.begin_nested():
                    connection.execute(customers.insert().values(id=uuid4(), name='invalid', name_ar=ar, name_en=en))
            connection.execute(customers.update().where(customers.c.id == ids[0]).values(name_en='Alternative English'))
            migration.downgrade()
            assert {c['name'] for c in sa.inspect(connection).get_columns('commercial_customers')} == {'id', 'name'}
            assert connection.scalar(sa.select(old.c.name).where(old.c.id == ids[0])) == names[0]
            recovery = sa.Table(migration.RECOVERY, sa.MetaData(), autoload_with=connection)
            assert connection.scalar(sa.select(recovery.c.name_en).where(recovery.c.id == ids[0])) == 'Alternative English'
            migration.upgrade()
            assert connection.scalar(sa.select(customers.c.name_en).where(customers.c.id == ids[0])) == 'Alternative English'
            connection.execute(customers.update().where(customers.c.id == ids[0]).values(name_en='Edited English'))
            migration.downgrade()
            assert set(connection.scalars(sa.select(recovery.c.name_en).where(recovery.c.id == ids[0]))) == {'Alternative English', 'Edited English'}
            migration.upgrade()
            assert connection.scalar(sa.select(customers.c.name_en).where(customers.c.id == ids[0])) == 'Edited English'
    finally:
        isolated.dispose()
        with engine.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
