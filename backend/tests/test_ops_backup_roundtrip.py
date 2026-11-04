"""Real local E2E: synthetic DB -> encrypted rclone local -> download -> guarded restore.

Requires Docker and rclone on the HOST; never uses a Docker socket mount.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from tests.core.test_ops_backup import config

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts/backup'))
import ops_backup as ops


@pytest.mark.skipif(os.environ.get('RUN_BACKUP_CONTAINER_TESTS') != '1', reason='Explicit synthetic host drill opt-in')
def test_complete_daily_job_with_local_remote(tmp_path, monkeypatch):
    name = 'iorp-synthetic-source-' + uuid4().hex
    password = uuid4().hex
    source_network = name + '-net'
    def docker(*args):
        return subprocess.run(['docker', *args], check=True, capture_output=True, text=True).stdout.strip()
    docker('network', 'create', '--label', 'iorp.purpose=backup-test', source_network)
    source_id = docker('run', '-d', '--name', name, '--network', source_network, '--label', 'iorp.purpose=backup-test',
                       '--memory', '512m', '--cpus', '0.5', '-p', '127.0.0.1::5432',
                       '-e', 'POSTGRES_PASSWORD=' + password, ops.PG_IMAGE)
    engine = None
    try:
        for _ in range(90):
            try:
                docker('exec', name, 'pg_isready', '-U', 'postgres')
                break
            except subprocess.CalledProcessError:
                time.sleep(1)
        port = docker('port', name, '5432/tcp').rsplit(':', 1)[1]
        url = f'postgresql+psycopg://postgres:{password}@127.0.0.1:{port}/postgres'
        engine = create_engine(url)
        file_key = f'organizations/{uuid4()}/synthetic.txt'
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE alembic_version(version_num text)'))
            connection.execute(text("INSERT INTO alembic_version VALUES ('synthetic')"))
            connection.execute(text('CREATE TABLE documents(id integer, file_path text)'))
            connection.execute(text('INSERT INTO documents VALUES (1, :key)'), {'key': file_key})
        uploads = tmp_path / 'uploads'
        file = uploads / file_key
        file.parent.mkdir(parents=True)
        file.write_text('synthetic sensitive document')
        c = config(tmp_path)
        (tmp_path / 'db.env').write_text('DATABASE_URL=' + url)
        monkeypatch.setenv('IORP_BACKUP_KEY', ops.read_env(tmp_path / 'key.env')['IORP_BACKUP_KEY'])
        monkeypatch.delenv('DOCKER_HOST', raising=False)
        monkeypatch.delenv('DOCKER_CONTEXT', raising=False)
        remote = tmp_path / 'offsite' / 'iorp-backups' / 'staging'
        class SyntheticJob(ops.Job):
            def collect(self):
                self.stage = 'backup'
                if os.environ.get('BACKUP_TEST_IMAGE'):
                    out = self.scratch / 'collect'
                    ops.private_dir(out)
                    # Root local runs use the production UID/700. A non-root CI
                    # runner uses its own UID for this synthetic bind directory.
                    uid = 10001 if os.getuid() == 0 else os.getuid()
                    if os.getuid() == 0:
                        os.chown(out, uid, uid)
                        # Model the production uploads volume's UID 10001 even
                        # when the test process has a private (077) umask.
                        for path in [uploads, *uploads.rglob('*')]:
                            os.chown(path, uid, uid)
                    done = subprocess.run(['docker', 'run', '--rm', '--name', self.collector,
                        '--user', str(uid),
                        '--network', source_network, '--read-only', '--cap-drop', 'ALL',
                        '--security-opt', 'no-new-privileges:true', '--memory', '512m', '--cpus', '0.5',
                        '--tmpfs', '/tmp:size=64m,mode=1777',
                        '--mount', f'type=bind,src={uploads},dst=/var/lib/iorp/uploads,readonly',
                        '--mount', f'type=bind,src={out},dst=/backup-out',
                        '-e', 'DATABASE_URL', '-e', 'IORP_BACKUP_KEY', os.environ['BACKUP_TEST_IMAGE']],
                        env={**self.child_env, 'IORP_BACKUP_KEY': self.key_env['IORP_BACKUP_KEY'],
                                 'DATABASE_URL': f'postgresql+psycopg://postgres:{password}@{name}:5432/postgres'},
                        capture_output=True, text=True, timeout=120)
                    assert done.returncode == 0, done.stderr  # exclusively synthetic fixture diagnostics
                    folder, = out.iterdir()
                    return folder
                return ops.tool.backup(self.scratch / 'collect', source_id, True,
                                       url_override=url, uploads_dir=uploads)
        job = SyntheticJob(c)
        job.remote = 'test:' + str(remote)
        pushes = []
        monkeypatch.setattr(ops, 'push', lambda url, up, msg: pushes.append((up, msg)) or True)
        job.execute()
        assert pushes == [(True, 'restore verified'), (True, 'backup complete')]
        assert not job.scratch.exists()
        folders = list(job.local.iterdir())
        assert len(folders) == 1 and ops.matching_receipt(folders[0])
        manifest = json.loads((folders[0] / 'manifest.json').read_text())
        assert manifest['dump_public_tables'] == len(manifest['table_counts']) == 2
        remote_files = list(remote.rglob('*'))
        assert {p.name for p in remote_files if p.is_file()} == {*ops.PAYLOADS, 'verification.json.enc', 'complete.enc'}
        assert all(b'synthetic sensitive document' not in p.read_bytes() for p in remote_files if p.is_file())
        assert subprocess.run(['docker', 'inspect', job.container], capture_output=True).returncode != 0
        assert subprocess.run(['docker', 'volume', 'inspect', job.volume], capture_output=True).returncode != 0

        # A dump missing a source table must fail before creating a valid manifest.
        original_command = ops.tool.pg_command
        def omitted_table(tool, url, database, container, extra):
            if tool == 'pg_dump':
                extra = [*extra, '--exclude-table=public.documents']
            return original_command(tool, url, database, container, extra)
        monkeypatch.setattr(ops.tool, 'pg_command', omitted_table)
        with pytest.raises(SystemExit, match='table count'):
            ops.tool.backup(tmp_path / 'incomplete', source_id, True, url_override=url, uploads_dir=uploads)
        assert not list((tmp_path / 'incomplete').rglob('manifest.json'))
    finally:
        if engine:
            engine.dispose()
        docker('rm', '-f', '-v', name)
        docker('network', 'rm', source_network)
