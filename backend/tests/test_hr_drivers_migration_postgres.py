"""Exercise migration preflight on isolated PostgreSQL schemas, never project data."""
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


def migration():
    path = Path(__file__).parents[1] / 'alembic/versions/2026_11_16_0900_f6a1b2o8_hr_drivers.py'
    spec = importlib.util.spec_from_file_location('hr_drivers_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_duplicate_identity_preflight_fails_without_modifying_existing_records():
    schema = 'test_hr_drivers_' + uuid4().hex
    with engine.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        org = uuid4()
        with isolated.begin() as connection:
            connection.execute(sa.text('CREATE TABLE shipping_drivers (organization_id uuid, identity_no text)'))
            connection.execute(sa.text("INSERT INTO shipping_drivers VALUES (:org, 'DUPLICATE-ID'), (:org, 'DUPLICATE-ID')"), {'org': org})
        with isolated.begin() as connection, Operations.context(MigrationContext.configure(connection)):
            with pytest.raises(RuntimeError, match='DUPLICATE-ID') as error:
                migration().upgrade()
            assert str(org) in str(error.value)
            assert connection.scalar(sa.text('SELECT count(*) FROM shipping_drivers')) == 2
            assert 'email' not in {c['name'] for c in sa.inspect(connection).get_columns('shipping_drivers')}
    finally:
        isolated.dispose()
        with engine.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
