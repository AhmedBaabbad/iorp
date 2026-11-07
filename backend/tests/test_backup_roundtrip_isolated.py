"""Opt-in real PostgreSQL drill; creates its own server, never reads app DB URL."""
import os
import subprocess
import time
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from cryptography.fernet import Fernet
from tests.core.test_backup_tool import tool


@pytest.mark.skipif(os.environ.get('RUN_BACKUP_CONTAINER_TESTS') != '1', reason='Explicit disposable Docker drill opt-in')
def test_encrypted_backup_restore_and_retention_on_disposable_server(tmp_path, monkeypatch):
    name = 'iorp-backup-test-' + uuid4().hex
    password = uuid4().hex
    def docker(*args, timeout=None):
        return subprocess.run(['docker', *args], check=True, capture_output=True, text=True, timeout=timeout).stdout.strip()
    container_id = docker('run', '-d', '--name', name, '--label', 'iorp.purpose=backup-test',
           '-p', '127.0.0.1::5432', '-e', 'POSTGRES_PASSWORD=' + password, 'postgres:16')
    engine = None
    try:
        monkeypatch.setenv('APP_ENV', 'test')
        monkeypatch.setenv('DATABASE_URL', 'postgresql+psycopg://unused:unused@127.0.0.1:1/unused')
        monkeypatch.setenv('IORP_RESTORE_CONTAINER_ID', container_id)
        startup_deadline = time.monotonic() + 60
        for _ in range(60):
            remaining = startup_deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError('postgres-start')
            try:
                docker('exec', name, 'pg_isready', '-h', '127.0.0.1', '-p', '5432', '-U', 'postgres',
                       timeout=min(10, remaining))
                break
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                time.sleep(min(1, max(0, startup_deadline - time.monotonic())))
        else:
            raise RuntimeError('postgres-start')
        port = docker('port', name, '5432/tcp').rsplit(':', 1)[1]
        url = f'postgresql+psycopg://postgres:{password}@127.0.0.1:{port}/postgres'
        tool.wait_postgres_connection(url, min(startup_deadline, time.monotonic() + 30))
        engine = create_engine(url)
        tenant = str(uuid4())
        file_key = f'organizations/{tenant}/example.txt'
        with engine.begin() as conn:
            conn.execute(text('CREATE TABLE alembic_version(version_num text)'))
            conn.execute(text("INSERT INTO alembic_version VALUES ('synthetic')"))
            conn.execute(text('CREATE TABLE documents(id integer PRIMARY KEY, file_path text)'))
            conn.execute(text('INSERT INTO documents VALUES (1, :key)'), {'key': file_key})
        uploads = tmp_path / 'uploads'
        attachment = uploads / file_key
        attachment.parent.mkdir(parents=True)
        attachment.write_text('synthetic private document')
        monkeypatch.setattr(tool, 'settings', lambda: SimpleNamespace(uploads_dir=str(uploads)))
        monkeypatch.setenv('IORP_BACKUP_KEY', Fernet.generate_key().decode())
        scratch = tmp_path / 'scratch'
        scratch.mkdir()
        monkeypatch.setenv('IORP_RESTORE_SCRATCH', str(scratch))
        out = tmp_path / 'backups'
        folder = tool.backup(out, name, True, url_override=url)
        assert not (folder / 'database.dump').exists()
        assert not (folder / 'uploads.tar.gz').exists()
        target_url = url.rsplit('/', 1)[0] + '/iorp_restore_verify_target'
        result = tool.verify(folder, name, False, url_override=target_url)
        assert result['ok'] is True and result['files'] == 1 and result['rows'] == 2
        assert result['database_dropped'] is True
        assert tool.prune(out, 0, 0, 0, True) == []
        assert folder.is_dir()
        assert not list(scratch.iterdir())
    finally:
        if engine:
            engine.dispose()
        if docker('inspect', '--format', '{{index .Config.Labels "iorp.purpose"}}', name) != 'backup-test':
            raise RuntimeError('Refusing cleanup of unexpected container')
        docker('rm', '-f', '-v', name)
