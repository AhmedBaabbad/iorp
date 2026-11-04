"""Operational ordering, secret boundaries and failure-closed retention."""
import io
import json
import os
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest
from cryptography.fernet import Fernet

sys.path.insert(0, str(Path(__file__).parents[2] / 'scripts/backup'))
import ops_backup as ops


def config(tmp_path):
    for name, value in {
        'key.env': 'IORP_BACKUP_KEY=' + Fernet.generate_key().decode(),
        'db.env': 'DATABASE_URL=postgresql+psycopg://app:secret@postgres/iorp',
        'push.env': 'DAILY_PUSH_URL=https://example.invalid/api/push/secret\nRESTORE_PUSH_URL=https://example.invalid/api/push/restore-secret',
        'rclone.conf': '[test]\ntype=local',
    }.items():
        path = tmp_path / name
        path.write_text(value)
        path.chmod(0o600)
    return dict(ENVIRONMENT='staging', ENABLED='yes', PRODUCTION_APPROVED='no',
                STATE_DIR=str(tmp_path / 'state'), KEY_ENV_FILE=str(tmp_path / 'key.env'),
                DATABASE_ENV_FILE=str(tmp_path / 'db.env'), PUSH_ENV_FILE=str(tmp_path / 'push.env'),
                RCLONE_CONFIG=str(tmp_path / 'rclone.conf'), RCLONE_REMOTE='test',
                COMPOSE_FILE='compose.yaml', COMPOSE_ENV_FILE='project.env', MIN_FREE_BYTES='0')


def artifact(folder, missing=False):
    folder.mkdir(parents=True)
    entries = {}
    for name in ('database.dump', 'uploads.tar.gz'):
        path = folder / (name + '.enc')
        path.write_bytes(b'ciphertext')
        entries[name] = {'stored_as': path.name, 'stored_sha256': ops.digest(path)}
    (folder / 'manifest.json').write_text(json.dumps(dict(format='iorp-backup/1', encrypted=True,
        artifacts=entries, referenced_but_missing=['private-name'] if missing else [])))
    (folder / 'verification.json').write_text(json.dumps(dict(ok=True,
        manifest_sha256=ops.digest(folder / 'manifest.json'))))


def test_production_requires_two_explicit_switches(tmp_path):
    c = config(tmp_path)
    c['ENVIRONMENT'] = 'production'
    job = ops.Job(c)
    with pytest.raises(ops.Failure, match='disabled'):
        job.execute()
    assert not job.root.exists()


@pytest.mark.parametrize('stage', ['collect', 'transfer', 'verify', 'receipt', 'retention'])
def test_failures_always_clean_scratch_and_never_advance(tmp_path, monkeypatch, stage):
    job = ops.Job(config(tmp_path))
    calls = []
    sequence = ['collect', 'encrypt_manifest', 'transfer', 'verify', 'receipt', 'retention']
    def operation(name):
        def run(*_):
            calls.append(name)
            if name == stage:
                raise ops.Failure('synthetic')
            return tmp_path
        return run
    for name in sequence:
        monkeypatch.setattr(job, name, operation(name))
    monkeypatch.setattr(ops, 'push', lambda *_: True)
    def cleanup():
        calls.append('cleanup')
        import shutil
        shutil.rmtree(job.scratch)
    monkeypatch.setattr(job, 'cleanup', cleanup)
    with pytest.raises(ops.Failure):
        job.execute()
    assert calls == sequence[:sequence.index(stage) + 1] + ['cleanup']
    assert not job.scratch.exists()


def test_upload_only_allowlisted_ciphertexts_and_reject_download_corruption(tmp_path, monkeypatch):
    job = ops.Job(config(tmp_path))
    source = tmp_path / 'iorp-20261104T233000Z'
    artifact(source)
    job.encrypt_manifest(source)
    calls = []
    def rclone(*args):
        calls.append(args)
        if args[1].startswith('test:'):
            Path(args[2]).write_bytes(b'corrupt')
    monkeypatch.setattr(job, 'rclone', rclone)
    with pytest.raises(ops.Failure, match='remote-checksum'):
        job.transfer(source)
    uploaded = [Path(args[1]).name for args in calls if not args[1].startswith('test:')]
    assert uploaded == list(ops.PAYLOADS)
    assert 'manifest.json' not in uploaded


def test_missing_references_retry_exactly_once(tmp_path, monkeypatch):
    job = ops.Job(config(tmp_path))
    monkeypatch.setattr(ops, 'private_dir', lambda p, uid=None: p.mkdir(parents=True, exist_ok=True))
    count = []
    def compose(*args):
        if args[0] == 'run':
            count.append(True)
            artifact(job.scratch / 'collect' / 'iorp-20261104T233000Z', missing=True)
    monkeypatch.setattr(job, 'compose', compose)
    monkeypatch.setattr(ops.time, 'sleep', lambda _: None)
    with pytest.raises(ops.Failure, match='missing-files'):
        job.collect()
    assert len(count) == 2


def test_no_deletion_if_remote_or_local_receipt_is_invalid(tmp_path, monkeypatch):
    job = ops.Job(config(tmp_path))
    newest = job.local / 'iorp-20261104T233000Z'
    artifact(newest)
    old = job.local / 'iorp-20261001T233000Z'
    artifact(old)
    (old / 'verification.json').write_text('{}')
    monkeypatch.setattr(job, 'remote_catalog', lambda: {newest.name: newest, old.name: old})
    rclone = Mock()
    monkeypatch.setattr(job, 'rclone', rclone)
    with pytest.raises(ops.Failure, match='local-receipt'):
        job.retention(newest)
    rclone.assert_not_called()
    assert old.exists() and newest.exists()


def test_latest_recovery_point_is_always_retained():
    names = ['iorp-20261001T233000Z', 'iorp-20261104T233000Z']
    assert ops.retained(names, 0, 0, 0) == {max(names)}


def test_local_retention_keeps_exactly_newest_three_verified_backups(tmp_path, monkeypatch):
    job = ops.Job(config(tmp_path))
    folders = [job.local / f'iorp-2026110{day}T233000Z' for day in range(1, 5)]
    for folder in folders:
        artifact(folder)
    monkeypatch.setattr(job, 'remote_catalog', lambda: {p.name: p for p in folders})
    delete = Mock()
    monkeypatch.setattr(job, 'rclone', delete)
    job.retention(folders[-1])
    assert not folders[0].exists()
    assert all(p.exists() for p in folders[1:])
    delete.assert_not_called()  # Four days are still within the seven daily slots.


def test_gfs_is_union_of_day_iso_week_and_month_slots():
    names = ['iorp-20260101T233000Z', 'iorp-20260201T233000Z',
             'iorp-20260301T233000Z', 'iorp-20261103T233000Z', 'iorp-20261104T233000Z']
    assert ops.retained(names, 1, 1, 2) == {'iorp-20260301T233000Z', 'iorp-20261104T233000Z'}


@pytest.mark.skipif(os.name == 'nt', reason='POSIX permissions')
def test_secret_permissions_and_symlinks_are_rejected(tmp_path):
    path = tmp_path / 'secret'
    path.write_text('KEY=secret')
    path.chmod(0o644)
    with pytest.raises(ops.Failure, match='permissions'):
        ops.read_env(path)
    link = tmp_path / 'link'
    link.symlink_to(path)
    with pytest.raises(ops.Failure):
        ops.read_env(link)


def test_disk_over_80_percent_sends_down(tmp_path, monkeypatch):
    c = config(tmp_path)
    from collections import namedtuple
    Usage = namedtuple('Usage', 'total used free')
    monkeypatch.setattr(ops.shutil, 'disk_usage', lambda _: Usage(100, 81, 19))
    pushed = Mock(return_value=True)
    monkeypatch.setattr(ops, 'push', pushed)
    with pytest.raises(ops.Failure, match='disk-threshold'):
        ops.disk(c)
    assert pushed.call_args.args[1] is False


def test_push_rejects_insecure_urls_without_network():
    assert ops.push('http://example.invalid/secret', True, 'ok') is False
    assert ops.push('https://user:secret@example.invalid/', True, 'ok') is False


def test_failure_log_never_contains_exception_or_credentials(tmp_path, monkeypatch, capsys):
    c = config(tmp_path)
    file = tmp_path / 'ops.env'
    file.write_text('\n'.join(k + '=' + v for k, v in c.items()))
    file.chmod(0o600)
    monkeypatch.setattr(sys, 'argv', ['ops_backup.py', 'daily', '--config', str(file)])
    monkeypatch.setattr(ops.Job, 'execute', Mock(side_effect=RuntimeError('DATABASE_URL=secret https://push/secret')))
    monkeypatch.setattr(ops, 'push', lambda *_: True)
    mask = os.umask(0o077)
    try:
        assert ops.main() == 1
    finally:
        os.umask(mask)
    output = capsys.readouterr()
    assert output.err == ''
    assert output.out == 'iorp-backup: failed stage=preflight\n'


def test_dump_table_count_uses_actual_toc(tmp_path, monkeypatch):
    dump = tmp_path / 'dump'
    dump.write_bytes(b'synthetic archive')
    class Process:
        def __init__(self, args, stdin, stdout, stderr):
            assert args == ['pg_restore', '--list']
            self.stdin = io.BytesIO()
            stdout.write(b'1; 1259 1 TABLE public one owner\n2; 0 1 TABLE DATA public one owner\n')
        def wait(self):
            return 0
        def poll(self):
            return 0
    monkeypatch.setattr(ops.tool.subprocess, 'Popen', Process)
    assert ops.tool.dump_table_count(dump, None, None) == 1
