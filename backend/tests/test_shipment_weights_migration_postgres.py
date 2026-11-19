"""Nullable weight additions preserve history through PostgreSQL upgrade/down/upgrade."""
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


def test_shipment_weights_upgrade_downgrade_upgrade_preserves_legacy():
    path = Path(__file__).parents[1] / 'alembic/versions/2026_11_22_0900_f6a1b2p5_shipment_weights.py'
    spec = importlib.util.spec_from_file_location('shipment_weights_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == 'f6a1b2p4'
    schema = 'test_shipment_weights_' + uuid4().hex
    with engine.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        with isolated.begin() as c, Operations.context(MigrationContext.configure(c)):
            c.execute(sa.text('CREATE TABLE shipping_shipments (id integer PRIMARY KEY)'))
            c.execute(sa.text('CREATE TABLE shipping_shipment_lines (id integer PRIMARY KEY, weight numeric(14,3), weight_unit text)'))
            c.execute(sa.text("INSERT INTO shipping_shipment_lines VALUES (1, 877, 'kg')"))
            c.execute(sa.text('INSERT INTO shipping_shipments VALUES (1)'))
            for _ in range(2):
                migration.upgrade()
                assert c.execute(sa.text('SELECT weight, unit_net_weight FROM shipping_shipment_lines')).one() == (877, None)
                assert c.scalar(sa.text('SELECT gross_weight_kg FROM shipping_shipments')) is None
                columns = {col['name']: col for col in sa.inspect(c).get_columns('shipping_shipment_lines')}
                assert columns['unit_net_weight']['nullable'] and columns['unit_net_weight']['type'].precision == 14
                assert columns['unit_net_weight']['type'].scale == 3
                migration.downgrade()
                assert 'unit_net_weight' not in {col['name'] for col in sa.inspect(c).get_columns('shipping_shipment_lines')}
                assert 'gross_weight_kg' not in {col['name'] for col in sa.inspect(c).get_columns('shipping_shipments')}
                assert c.execute(sa.text('SELECT weight, weight_unit FROM shipping_shipment_lines')).one() == (877, 'kg')
            migration.upgrade()
    finally:
        isolated.dispose()
        with engine.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
