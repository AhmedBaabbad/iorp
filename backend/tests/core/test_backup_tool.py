"""OPS-BACKUP-001: the backup tool's safety rules, without a PostgreSQL server.

The full backup → restore drill runs against PostgreSQL (docs/operations/BACKUP_AND_RECOVERY.md); here: it never
restores over a real database, encryption round-trips and detects tampering, retention keeps the right copies, and a
hostile uploads archive is refused.
"""
import importlib.util
import io
import tarfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("iorp_backup", Path(__file__).parents[2] / "scripts/backup/iorp_backup.py")
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


@pytest.mark.parametrize("name", ["iorp", "postgres", "iorp_restore", "iorp_restore_verify_X; drop", "something_else"])
def test_a_restore_never_targets_anything_but_a_new_verification_database(name):
    with pytest.raises(SystemExit):
        tool.verification_name("iorp", name)


def test_a_restore_never_targets_the_source_even_with_the_prefix():
    with pytest.raises(SystemExit):
        tool.verification_name("iorp_restore_verify_1", "iorp_restore_verify_1")
    assert tool.verification_name("iorp").startswith("iorp_restore_verify_")


def test_encryption_round_trips_and_a_changed_byte_is_detected(tmp_path):
    from cryptography.fernet import Fernet, InvalidToken
    key = Fernet.generate_key().decode()
    plain = tmp_path / "plain.bin"
    plain.write_bytes(b"x" * (tool.CHUNK + 10))  # more than one chunk
    sealed, opened = tmp_path / "sealed", tmp_path / "opened"
    tool.encrypt_file(plain, sealed, key)
    assert b"xxxx" not in sealed.read_bytes()[:200]
    tool.decrypt_file(sealed, opened, key)
    assert opened.read_bytes() == plain.read_bytes()
    damaged = bytearray(sealed.read_bytes())
    damaged[50] ^= 1
    sealed.write_bytes(bytes(damaged))
    with pytest.raises(InvalidToken):
        tool.decrypt_file(sealed, tmp_path / "again", key)


def test_backup_refuses_without_a_key(tmp_path, monkeypatch):
    monkeypatch.delenv("IORP_BACKUP_KEY", raising=False)
    with pytest.raises(SystemExit):
        tool.backup(tmp_path, None, encrypt=True)
    assert not any(tmp_path.iterdir())  # nothing was touched


def test_retention_keeps_daily_weekly_and_monthly_copies():
    now = datetime(2026, 10, 14, 2)
    stamps = [now - timedelta(days=d) for d in range(400)]
    keep = tool.keep_set(stamps, daily=7, weekly=4, monthly=12)
    assert all(now - timedelta(days=d) in keep for d in range(7))  # the last 7 days
    assert len({(s.year, s.month) for s in keep}) == 12  # one per month for 12 months
    assert len(keep) < 7 + 4 + 12 + 1
    assert now - timedelta(days=399) not in keep


def _archive(tmp_path, name, data=b"x", kind=tarfile.REGTYPE):
    path = tmp_path / "a.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        info = tarfile.TarInfo(name)
        info.type = kind
        info.size = len(data) if kind == tarfile.REGTYPE else 0
        if kind == tarfile.SYMTYPE:
            info.linkname = "/etc/passwd"
        archive.addfile(info, io.BytesIO(data) if kind == tarfile.REGTYPE else None)
    return path


@pytest.mark.parametrize("name,kind", [("../escape.txt", tarfile.REGTYPE), ("uploads/link", tarfile.SYMTYPE)])
def test_a_hostile_uploads_archive_is_refused(tmp_path, name, kind):
    with pytest.raises(SystemExit):
        tool.safe_extract(_archive(tmp_path, name, kind=kind), tmp_path / "out")
    assert not (tmp_path / "escape.txt").exists()


def test_a_plain_uploads_archive_is_extracted(tmp_path):
    tool.safe_extract(_archive(tmp_path, "uploads/organizations/a.png", b"png"), tmp_path / "out")
    assert (tmp_path / "out/uploads/organizations/a.png").read_bytes() == b"png"


def _snapshot(root, stamp, verified=True):
    import json
    folder = root / ('iorp-' + stamp)
    folder.mkdir()
    artifacts = {}
    for name in ('database.dump', 'uploads.tar.gz'):
        (folder / name).write_bytes(b'synthetic archive')
        artifacts[name] = {'stored_as': name, 'stored_sha256': tool.sha256_file(folder / name)}
    manifest = {'format': 'iorp-backup/1', 'encrypted': False, 'artifacts': artifacts}
    (folder / 'manifest.json').write_text(json.dumps(manifest))
    if verified:
        (folder / 'verification.json').write_text(json.dumps({'ok': True, 'manifest_sha256': tool.sha256_file(folder / 'manifest.json')}))
    return folder


def test_retention_never_deletes_last_verified_backup_even_with_zero_policy(tmp_path):
    old = _snapshot(tmp_path, '20261001T000000Z')
    newest = _snapshot(tmp_path, '20261002T000000Z')
    assert tool.prune(tmp_path, 0, 0, 0, True) == [old]
    assert not old.exists()
    assert newest.is_dir()


@pytest.mark.parametrize('failure', ['corrupt', 'unverified', 'changed_manifest'])
def test_retention_failure_preserves_all_backups(tmp_path, failure):
    old = _snapshot(tmp_path, '20261001T000000Z')
    newest = _snapshot(tmp_path, '20261002T000000Z', verified=failure != 'unverified')
    if failure == 'corrupt':
        (newest / 'database.dump').write_bytes(b'corruption')
    if failure == 'changed_manifest':
        with (newest / 'manifest.json').open('a') as stream:
            stream.write(' ')
    with pytest.raises(SystemExit):
        tool.prune(tmp_path, 0, 0, 0, True)
    assert old.is_dir() and newest.is_dir()


def test_streamed_encryption_roundtrip_without_plaintext_file(tmp_path):
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    sealed = tmp_path / 'stream.enc'
    with sealed.open('wb') as handle:
        sink = tool.BackupSink(handle, key)
        sink.write(b'one')
        sink.write(b'two')
    assert list(tmp_path.iterdir()) == [sealed]
    tool.decrypt_file(sealed, tmp_path / 'decoded', key)
    assert (tmp_path / 'decoded').read_bytes() == b'onetwo'
    assert sink.size == 6


def test_verify_cannot_default_to_application_database(tmp_path):
    import json
    (tmp_path / 'manifest.json').write_text(json.dumps({'source_database': 'production'}))
    with pytest.raises(SystemExit, match='explicit isolated target'):
        tool.verify(tmp_path, None, False)


def test_artifact_path_escape_is_rejected(tmp_path):
    manifest = {'encrypted': False, 'artifacts': {'database.dump': {'stored_as': '../secret'}}}
    with pytest.raises(SystemExit, match='Unsafe artifact'):
        tool.stored_artifact(tmp_path, manifest, 'database.dump')


def test_extract_refuses_existing_destination(tmp_path):
    target = tmp_path / 'existing'
    target.mkdir()
    with pytest.raises(SystemExit, match='must not exist'):
        tool.safe_extract(_archive(tmp_path, 'uploads/test.txt'), target)
    assert not list(target.iterdir())


@pytest.mark.parametrize('content', [b'\x00', b'\xff\xff\xff\xff', b'\x00\x00\x00\x20short'])
def test_decrypt_refuses_invalid_or_truncated_frames(tmp_path, content):
    from cryptography.fernet import Fernet
    source = tmp_path / 'invalid.enc'
    source.write_bytes(content)
    with pytest.raises(SystemExit):
        tool.decrypt_file(source, tmp_path / 'plain', Fernet.generate_key().decode())
