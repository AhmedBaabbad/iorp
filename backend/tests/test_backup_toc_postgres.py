"""Real streaming custom archive regression against the disposable CI server."""
import json
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text
from tests.core.test_backup_tool import tool

pytestmark = pytest.mark.skipif(os.environ.get('RUN_POSTGRES_TESTS') != '1',
                                reason='Requires explicit isolated PostgreSQL')


def test_large_encrypted_backup_counts_real_toc(tmp_path, monkeypatch):
    # Own database: no interference with migrated public tables or other tests.
    url = tool.database_url(os.environ['DATABASE_URL'])
    name = 'test_backup_toc_' + uuid4().hex
    admin = create_engine(url, isolation_level='AUTOCOMMIT')
    engine = None
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        isolated_url = url.set(database=name)
        engine = create_engine(isolated_url)
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE alembic_version(version_num text)'))
            connection.execute(text("INSERT INTO alembic_version VALUES ('synthetic')"))
            connection.execute(text('CREATE TABLE payloads(id integer PRIMARY KEY, payload bytea)'))
            # Random bytes prevent pg_dump compression from hiding the pipe bug.
            connection.execute(text('INSERT INTO payloads VALUES (:id, :payload)'),
                               [{'id': i, 'payload': os.urandom(64 * 1024)} for i in range(40)])
            assert connection.execute(text('SELECT sum(octet_length(payload)) FROM payloads')).scalar_one() >= 2 * 1024 * 1024
        monkeypatch.setattr(tool, 'settings', lambda: SimpleNamespace(uploads_dir=str(tmp_path / 'uploads')))
        key = Fernet.generate_key().decode()
        monkeypatch.setenv('IORP_BACKUP_KEY', key)
        folder = tool.backup(tmp_path / 'backups', None, True,
                             url_override=isolated_url.render_as_string(hide_password=False))
        manifest = json.loads((folder / 'manifest.json').read_text())
        assert manifest['table_counts'] == {'alembic_version': 1, 'payloads': 40}
        assert manifest['dump_public_tables'] == 2
        assert manifest['artifacts']['database.dump']['bytes'] > 2 * 1024 * 1024
        assert tool.dump_table_count(folder / 'database.dump.enc', key, None) == 2
        assert {p.name for p in folder.iterdir()} == {'manifest.json', 'database.dump.enc', 'uploads.tar.gz.enc'}
    finally:
        if engine:
            engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()
