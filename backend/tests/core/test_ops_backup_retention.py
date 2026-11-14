"""Synthetic retention crash states, native MD5 format and redacted diagnostics."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import Mock

import pytest
from tests.core.test_ops_backup import ops, config, artifact, isolated_lock  # noqa: F401


class LocalRemote:
    """Filesystem-only rclone double; no account, host or cloud credentials."""
    def __init__(self, job, root):
        self.job, self.root, self.calls = job, root, []
        root.mkdir()

    def path(self, value):
        if value == self.job.remote:
            return self.root
        if value.startswith(self.job.remote + '/'):
            return self.root / value[len(self.job.remote) + 1:]
        return Path(value)

    def __call__(self, *args):
        self.calls.append(args)
        if args[0] == 'copyto':
            source, target = map(self.path, args[1:3])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            return ''
        if args[0] == 'lsf':
            items = sorted(self.path(args[1]).iterdir())
            if '--dirs-only' in args:
                items = [p for p in items if p.is_dir()]
            return '\n'.join(p.name + ('/' if p.is_dir() else '') for p in items)
        if args[:2] == ('hashsum', 'MD5'):
            assert '--download' not in args
            folder = self.path(args[2])
            return '\n'.join(ops.checksums(p)['md5'] + '  ' + p.relative_to(folder).as_posix()
                             for p in sorted(folder.rglob('*')) if p.is_file())
        assert args[0] == 'purge'
        target = self.path(args[1])
        assert target.parent == self.root and ops.backup_name(target.name)
        shutil.rmtree(target)
        return ''


@pytest.fixture
def store(tmp_path, monkeypatch):
    job = ops.Job(config(tmp_path))
    ops.private_dir(job.local); ops.private_dir(job.scratch)
    remote = LocalRemote(job, tmp_path / 'synthetic-remote')
    monkeypatch.setattr(job, 'rclone', remote)
    def publish(day, hour=23):
        source = tmp_path / 'source' / f'iorp-202601{day:02}T{hour:02}3000Z'
        artifact(source); job.encrypt_manifest(source)
        downloaded = tmp_path / 'downloaded' / source.name
        shutil.copytree(source, downloaded)
        for name in ops.PAYLOADS:
            remote('copyto', str(source / name), job.remote + '/' + source.name + '/' + name)
        return job.receipt(source, downloaded)
    return job, remote, publish


def test_receipted_local_orphan_is_quarantined_and_good_old_copies_are_pruned(store):
    job, remote, publish = store
    good = [publish(day) for day in range(2, 7)]
    orphan = job.local / 'iorp-20260101T233000Z'
    artifact(orphan)
    before = {p.name:p.read_bytes() for p in orphan.iterdir()}
    remote.calls.clear(); job.retention(good[-1])
    preserved, = job.quarantine.glob('*/' + orphan.name)
    assert {p.name:p.read_bytes() for p in preserved.iterdir()} == before
    assert job.local_quarantined and not orphan.exists()
    assert {p.name for p in job.local.iterdir()} == {p.name for p in good[-3:]}
    assert not any(c[0]=='purge' and c[1].endswith(orphan.name) for c in remote.calls)


def test_incomplete_remote_upload_is_not_a_recovery_point_or_deletion_candidate(store):
    job, remote, publish = store
    good = [publish(day) for day in range(2, 7)]
    partial = remote.root / 'iorp-20260101T233000Z'; partial.mkdir()
    (partial / 'database.dump.enc').write_bytes(b'interrupted synthetic upload')
    remote.calls.clear(); job.retention(good[-1])
    assert partial.exists() and (partial/'database.dump.enc').read_bytes()==b'interrupted synthetic upload'
    assert not any(c[0]=='purge' and c[1].endswith(partial.name) for c in remote.calls)
    assert not job.local_quarantined


@pytest.mark.parametrize('entry', ['manual-receipts', '.hidden', 'notes.txt', 'iorp-20261399T999999Z'])
def test_unexpected_local_entries_are_preserved_not_fatal(store, entry):
    job, remote, publish = store
    good = [publish(day) for day in range(1, 6)]
    extra = job.local / entry
    if entry in ('manual-receipts','iorp-20261399T999999Z'):
        extra.mkdir(); (extra/'original.txt').write_bytes(b'preserve me')
    else:
        extra.write_bytes(b'preserve me')
    job.retention(good[-1])
    saved, = job.quarantine.glob('*/' + entry)
    assert (saved/'original.txt' if saved.is_dir() else saved).read_bytes()==b'preserve me'
    assert len(list(job.local.iterdir()))==3


@pytest.mark.parametrize('damage', ['manifest-json','receipt-json','payload','missing-payload'])
def test_corrupt_local_backup_is_quarantined_without_blocking_retention(store, damage):
    job, remote, publish = store
    good = [publish(day) for day in range(1, 6)]
    old = good[0]
    if damage=='manifest-json':(old/'manifest.json').write_text('{')
    elif damage=='receipt-json':(old/'verification.json').write_text('[]')
    elif damage=='payload':(old/'database.dump.enc').write_bytes(b'damaged')
    else:(old/'database.dump.enc').unlink()
    job.retention(good[-1])
    assert list(job.quarantine.glob('*/' + old.name))
    assert {p.name for p in job.local.iterdir()}=={p.name for p in good[-3:]}


@pytest.mark.skipif(os.name=='nt',reason='POSIX symlink fixture')
def test_quarantining_symlink_never_moves_or_deletes_its_target(store,tmp_path):
    job, remote, publish = store
    newest=publish(16)
    outside=tmp_path/'outside';outside.mkdir();(outside/'keep').write_bytes(b'untouched')
    link=job.local/'untrusted';link.symlink_to(outside,target_is_directory=True)
    job.retention(newest)
    saved,=job.quarantine.glob('*/untrusted')
    assert saved.is_symlink() and (outside/'keep').read_bytes()==b'untouched'


def test_sixteen_accumulated_local_backups_keep_three_and_apply_remote_gfs(store):
    job, remote, publish = store
    folders=[publish(day) for day in range(1,17)]
    remote.calls.clear();job.retention(folders[-1])
    assert {p.name for p in job.local.iterdir()}=={p.name for p in folders[-3:]}
    # Latest seven days plus Jan 4 (ISO week 1); week/month slots overlap.
    assert {p.name for p in remote.root.iterdir()}=={f'iorp-202601{day:02}T233000Z' for day in [4,*range(10,17)]}
    assert not job.local_quarantined
    downloads=[c[1] for c in remote.calls if c[0]=='copyto' and c[1].startswith(job.remote)]
    assert len(downloads)==16*3
    assert all(Path(name).name in {'complete.enc','manifest.json.enc','verification.json.enc'} for name in downloads)


def test_interruption_after_remote_prune_recovers_via_local_quarantine(store,monkeypatch):
    job, remote, publish=store
    folders=[publish(day) for day in range(1,17)]
    removed=[]
    def interrupted(*args):
        if args[0]=='purge':
            if removed:raise ops.Failure('interrupted')
            removed.append(Path(args[1]).name)
        return remote(*args)
    monkeypatch.setattr(job,'rclone',interrupted)
    with pytest.raises(ops.Failure,match='^interrupted$'):job.retention(folders[-1])
    assert len(list(job.local.iterdir()))==16 and len(removed)==1
    monkeypatch.setattr(job,'rclone',remote)
    job.retention(folders[-1])
    assert list(job.quarantine.glob('*/'+removed[0]))
    assert {p.name for p in job.local.iterdir()}=={p.name for p in folders[-3:]}


def test_normal_same_day_gfs_prune_cannot_poison_subsequent_daily_jobs(store):
    job, remote, publish=store
    morning,noon,night=[publish(1,hour) for hour in [8,12,23]]
    job.retention(night)
    assert {p.name for p in job.local.iterdir()}=={morning.name,noon.name,night.name}
    assert {p.name for p in remote.root.iterdir()}=={night.name}
    # Old code raises local-receipt here, before it can ever prune local copies.
    tomorrow=publish(2)
    job.retention(tomorrow)
    assert list(job.quarantine.glob('*/'+morning.name)) and list(job.quarantine.glob('*/'+noon.name))
    assert {p.name for p in job.local.iterdir()}=={night.name,tomorrow.name}
    next_day=publish(3)
    job.retention(next_day)
    assert {p.name for p in job.local.iterdir()}=={night.name,tomorrow.name,next_day.name}


def test_entire_remote_catalog_must_validate_before_any_prune_or_quarantine(store):
    job, remote, publish = store
    good=[publish(day) for day in range(1,17)]
    (remote.root/good[-1].name/'manifest.json.enc').write_bytes(b'broken ciphertext')
    stray=job.local/'.stray';stray.write_bytes(b'preserve')
    remote.calls.clear()
    with pytest.raises(ops.Failure,match='^remote-checksum$'):job.retention(good[-1])
    assert not any(c[0]=='purge' for c in remote.calls)
    assert len(list(job.local.iterdir()))==17 and stray.exists() and not job.quarantine.exists()


@pytest.mark.parametrize('name', ['manual-receipts','iorp-20261301T233000Z','iorp-20260101T250000Z'])
def test_unknown_or_invalid_calendar_remote_directory_fails_closed(store,name):
    job, remote, publish=store;newest=publish(16)
    (remote.root/name).mkdir();remote.calls.clear()
    with pytest.raises(ops.Failure,match='^remote-layout$'):job.retention(newest)
    assert not any(c[0]=='purge' for c in remote.calls)


def test_loose_remote_files_are_ignored_without_purging_the_environment_root(store):
    job, remote, publish=store;newest=publish(16)
    extra=remote.root/'.note';extra.write_bytes(b'keep')
    job.retention(newest)
    assert extra.read_bytes()==b'keep'


def test_subdirectories_in_a_completed_backup_fail_closed(store):
    job, remote, publish=store;newest=publish(16)
    nested=remote.root/newest.name/'nested';nested.mkdir();(nested/'unexpected.enc').write_bytes(b'x')
    remote.calls.clear()
    with pytest.raises(ops.Failure,match='^remote-layout$'):job.retention(newest)
    assert not any(c[0]=='purge' for c in remote.calls)


@pytest.mark.parametrize('line', ['a'*32+' file.enc', 'UNSUPPORTED  file.enc', 'a'*32+'  ', 'a'*32+'  file.enc\n'+'a'*32+'  file.enc'])
def test_md5_malformed_or_duplicate_rows_have_safe_reason(line):
    with pytest.raises(ops.Failure,match='^remote-hash-format$'):ops.md5_listing(line)


def test_native_md5_text_format_preserves_relative_paths_and_spaces():
    assert ops.md5_listing('A'*32+'  database.dump.enc\n'+'b'*32+'  nested/file with spaces.enc\n')=={
        'database.dump.enc':'a'*32,'nested/file with spaces.enc':'b'*32}


@pytest.mark.skipif(not shutil.which('rclone'),reason='Real rclone is installed in backup roundtrip CI')
def test_real_rclone_md5_and_depth_one_dirs_only(tmp_path):
    rc=tmp_path/'rclone.conf';rc.write_text('[synthetic]\ntype=local\n');rc.chmod(0o600)
    root=tmp_path/'remote';root.mkdir()
    for name in ['iorp-20260101T233000Z','unrelated']:(root/name).mkdir()
    (root/'loose.txt').write_bytes(b'root file')
    nested=root/'iorp-20260101T233000Z'/'nested';nested.mkdir()
    (nested/'with spaces.enc').write_bytes(b'synthetic bytes')
    def run(*args):return subprocess.run(['rclone','--config',str(rc),*args],capture_output=True,text=True,check=True).stdout
    listing=run('lsf',str(root),'--dirs-only','--max-depth','1').splitlines()
    assert set(listing)=={'iorp-20260101T233000Z/','unrelated/'}
    hashes=ops.md5_listing(run('hashsum','MD5',str(root)))
    assert hashes['iorp-20260101T233000Z/nested/with spaces.enc']==hashlib.md5(b'synthetic bytes',usedforsecurity=False).hexdigest()
    assert set(hashes)=={'loose.txt','iorp-20260101T233000Z/nested/with spaces.enc'}


@pytest.mark.parametrize('operation,code', [('root','remote-list'),('entries','remote-entries'),('metadata','remote-metadata-read'),('hashes','remote-hashes')])
@pytest.mark.parametrize('failure', [RuntimeError('synthetic private path'),ops.Failure('retention'),subprocess.CalledProcessError(1,['synthetic'],stderr=b'private')])
def test_catalog_command_failures_have_location_codes(store,monkeypatch,operation,code,failure):
    job, remote, publish=store;newest=publish(16)
    def broken(*args):
        which='root' if args[0]=='lsf' and args[1]==job.remote else 'entries' if args[0]=='lsf' else 'metadata' if args[0]=='copyto' else 'hashes' if args[0]=='hashsum' else ''
        if which==operation:raise failure
        return remote(*args)
    monkeypatch.setattr(job,'rclone',broken)
    with pytest.raises(ops.Failure,match='^'+code+'$'):job.retention(newest)
    assert newest.exists() and not any(c[0]=='purge' for c in remote.calls)


def test_invalid_json_completion_becomes_remote_catalog_read(store):
    job, remote, publish=store;newest=publish(16)
    plain=job.scratch/'invalid.json';plain.write_text('{')
    ops.tool.encrypt_file(plain,remote.root/newest.name/'complete.enc',job.key_env['IORP_BACKUP_KEY'])
    with pytest.raises(ops.Failure,match='^remote-catalog-read$'):job.retention(newest)


@pytest.mark.parametrize('error',[KeyError('private'),ValueError('private'),TypeError('private'),SystemExit('private')])
def test_unexpected_catalog_exceptions_are_converted_at_read_boundary(store,monkeypatch,error):
    job, remote, publish=store;newest=publish(16)
    monkeypatch.setattr(job,'_remote_catalog',Mock(side_effect=error))
    with pytest.raises(ops.Failure,match='^remote-catalog-read$'):job.retention(newest)
    assert newest.exists()


def test_remote_purge_error_is_location_specific_and_keeps_local_backups(store,monkeypatch):
    job, remote, publish=store;folders=[publish(day) for day in range(1,17)]
    def fail(*args):
        if args[0]=='purge':raise RuntimeError('private remote diagnostic')
        return remote(*args)
    monkeypatch.setattr(job,'rclone',fail)
    with pytest.raises(ops.Failure,match='^remote-prune$'):job.retention(folders[-1])
    assert len(list(job.local.iterdir()))==16


def test_local_delete_error_has_location_code(store,monkeypatch):
    job, remote, publish=store;folders=[publish(day) for day in range(1,5)]
    original=shutil.rmtree
    def fail(path,*args,**kwargs):
        if Path(path).parent==job.local:raise OSError('private filesystem diagnostic')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(shutil,'rmtree',fail)
    with pytest.raises(ops.Failure,match='^local-prune$'):job.retention(folders[-1])
    assert folders[-1].exists()


def test_unexpected_retention_planning_exception_has_safe_code(store,monkeypatch):
    job, remote, publish=store;newest=publish(16)
    monkeypatch.setattr(ops,'retained',Mock(side_effect=ValueError('private date diagnostic')))
    with pytest.raises(ops.Failure,match='^retention-plan$'):job.retention(newest)
    assert newest.exists() and not any(c[0]=='purge' for c in remote.calls)


def test_local_directory_read_error_has_safe_location_code(store,monkeypatch):
    job, remote, publish=store;newest=publish(16)
    original=Path.iterdir
    def broken(path):
        if path==job.local:raise OSError('synthetic private path')
        return original(path)
    monkeypatch.setattr(Path,'iterdir',broken)
    with pytest.raises(ops.Failure,match='^local-scan$'):job.retention(newest)


def test_quarantine_rename_failure_preserves_original_and_prevents_pruning(store,monkeypatch):
    job, remote, publish=store;newest=publish(16)
    stray=job.local/'.stray';stray.write_bytes(b'keep')
    monkeypatch.setattr(Path,'rename',Mock(side_effect=OSError('private path')))
    with pytest.raises(ops.Failure,match='^local-quarantine$'):job.retention(newest)
    assert stray.read_bytes()==b'keep' and newest.exists()
    assert not any(c[0]=='purge' for c in remote.calls)


@pytest.mark.parametrize('environment',['staging','test',''])
def test_nonproduction_jobs_and_disk_checks_are_rejected_before_io(environment,tmp_path):
    with pytest.raises(ops.Failure,match='^production-only$'):ops.Job({'ENVIRONMENT':environment})
    with pytest.raises(ops.Failure,match='^production-only$'):ops.disk({'ENVIRONMENT':environment})


def test_main_rejects_staging_before_lock_secrets_or_push(tmp_path,monkeypatch,capsys,isolated_lock):
    file=tmp_path/'ops.env';file.write_text('ENVIRONMENT=staging\n');file.chmod(0o600)
    monkeypatch.setattr(sys,'argv',['ops_backup.py','daily','--config',str(file)])
    original=ops.read_env;reads=[]
    def read(path,*args,**kwargs):
        reads.append(path);assert path==file
        return original(path,*args,**kwargs)
    monkeypatch.setattr(ops,'read_env',read)
    lock=Mock(side_effect=AssertionError('Nonproduction must not acquire a host lock'))
    monkeypatch.setattr(ops,'open',lock)
    pushed=Mock();monkeypatch.setattr(ops,'push',pushed)
    mask=os.umask(0o077)
    try:assert ops.main()==1
    finally:os.umask(mask)
    assert reads==[file];lock.assert_not_called();pushed.assert_not_called()
    assert capsys.readouterr().out=='iorp-backup: failed stage=configuration reason=production-only\n'


@pytest.mark.parametrize('failure,reason', [
    (ops.Failure('local-scan'),'local-scan'),(ops.Failure('a'+'0'*40),'a'+'0'*40),
    (ops.Failure('a'+'0'*41),'unexpected'),(ops.Failure('Invalid'),'unexpected'),
    (ops.Failure('https://example.invalid/private'),'unexpected'),(ops.Failure('/private/path'),'unexpected'),
    (ops.Failure('bad\nline'),'unexpected'),(ops.Failure('safe','extra'),'unexpected'),
    (ops.Failure(42),'unexpected'),(ops.Failure(),'unexpected'),
    (ValueError('secret token'),'unexpected'),(ValueError('local-scan'),'unexpected'),
])
def test_main_prints_only_safe_stage_and_reason_and_pushes_same_reason(tmp_path,monkeypatch,capsys,isolated_lock,failure,reason):
    c=config(tmp_path);file=tmp_path/'ops.env';file.write_text('\n'.join(k+'='+v for k,v in c.items()));file.chmod(0o600)
    monkeypatch.setattr(sys,'argv',['ops_backup.py','daily','--config',str(file)])
    def fail(job):job.stage='retention';raise failure
    monkeypatch.setattr(ops.Job,'execute',fail)
    pushed=Mock(return_value=True);monkeypatch.setattr(ops,'push',pushed)
    mask=os.umask(0o077)
    try:assert ops.main()==1
    finally:os.umask(mask)
    output=capsys.readouterr()
    assert output.err=='' and output.out==f'iorp-backup: failed stage=retention reason={reason}\n'
    assert pushed.call_args.args[1:]==(False,'backup failed: '+reason)
    assert str(tmp_path) not in output.out and 'Traceback' not in output.out


def test_daily_quarantine_notice_is_fixed_and_safe(tmp_path,monkeypatch,isolated_lock,capsys):
    c=config(tmp_path);file=tmp_path/'ops.env';file.write_text('\n'.join(k+'='+v for k,v in c.items()));file.chmod(0o600)
    monkeypatch.setattr(sys,'argv',['ops_backup.py','daily','--config',str(file)])
    for method in ['collect','transfer','receipt']:monkeypatch.setattr(ops.Job,method,lambda *_:tmp_path)
    for method in ['encrypt_manifest','verify','cleanup']:monkeypatch.setattr(ops.Job,method,lambda *_:None)
    monkeypatch.setattr(ops.Job,'budget',lambda *_:None)
    monkeypatch.setattr(ops.Job,'retention',lambda job,*_:setattr(job,'local_quarantined',True))
    pushed=Mock(return_value=True);monkeypatch.setattr(ops,'push',pushed)
    mask=os.umask(0o077)
    try:assert ops.main()==0
    finally:os.umask(mask)
    assert pushed.call_args.args[1:]==(True,'backup complete: local-quarantined')
    assert capsys.readouterr().out=='iorp-backup: warning reason=local-quarantined\niorp-backup: success\n'
