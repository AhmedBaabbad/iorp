"""Specification range upgrade/downgrade/re-upgrade on isolated PostgreSQL."""
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


def test_spec_ranges_upgrade_downgrade_upgrade_and_constraints():
    path = Path(__file__).parents[1] / 'alembic/versions/2026_11_21_0900_f6a1b2p4_spec_ranges.py'
    spec = importlib.util.spec_from_file_location('spec_ranges_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    schema = 'test_spec_ranges_' + uuid4().hex
    with engine.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        with isolated.begin() as c, Operations.context(MigrationContext.configure(c)):
            metadata = sa.MetaData()
            sa.Table('masterdata_product_properties', metadata, sa.Column('id', sa.Integer(), primary_key=True), sa.Column('kind', sa.String(8)))
            sa.Table('quality_certificates', metadata, sa.Column('id', sa.Integer(), primary_key=True))
            for table in migration.TABLES:
                sa.Table(table, metadata, sa.Column('id', sa.Integer(), primary_key=True), sa.Column('thickness_mm', sa.Numeric(10, 3)))
            metadata.create_all(c)
            c.execute(metadata.tables['masterdata_product_properties'].insert().values(id=1, kind='number'))
            for table in migration.TABLES:
                c.execute(metadata.tables[table].insert().values(id=1, thickness_mm='.550'))
            for _ in range(2):
                migration.upgrade()
                properties = sa.Table('masterdata_product_properties', sa.MetaData(), autoload_with=c)
                assert c.scalar(sa.select(properties.c.allows_range)) is False
                for table in migration.TABLES:
                    lines = sa.Table(table, sa.MetaData(), autoload_with=c)
                    assert c.scalar(sa.select(lines.c.thickness_max_mm)) is None
                    assert str(c.scalar(sa.select(lines.c.thickness_mm))) == '0.550'
                    with pytest.raises(sa.exc.IntegrityError), c.begin_nested():
                        c.execute(lines.update().values(thickness_max_mm='.500'))
                    c.execute(lines.update().values(thickness_max_mm='.600'))
                    assert str(c.scalar(sa.select(lines.c.thickness_max_mm))) == '0.600'
                with pytest.raises(sa.exc.IntegrityError), c.begin_nested():
                    c.execute(properties.insert().values(id=2, kind='text', allows_range=True))
                migration.downgrade()
                assert 'allows_range' not in {x['name'] for x in sa.inspect(c).get_columns(properties.name)}
                for table in migration.TABLES:
                    assert 'thickness_max_mm' not in {x['name'] for x in sa.inspect(c).get_columns(table)}
            migration.upgrade()
    finally:
        isolated.dispose()
        with engine.begin() as c:
            c.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
