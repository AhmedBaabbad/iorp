"""Host-only operational backup coordinator. Never mount Docker's socket in an image.

All subprocess output is private and discarded on failure; journal messages are fixed
stage names. Importing this module performs no I/O and requires no production secrets.
"""
from __future__ import annotations

import argparse
import contextlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import build_opener, HTTPRedirectHandler, Request
from uuid import uuid4

import iorp_backup as tool

STAMP = re.compile(r'iorp-\d{8}T\d{6}Z\Z')
PAYLOADS = ('database.dump.enc', 'uploads.tar.gz.enc', 'manifest.json.enc')
# Same reviewed PostgreSQL image as deploy/compose.yaml.
PG_IMAGE = 'postgres:16@sha256:ca0bd484cb98bf4b24eb1010e73fb3fcbd6714d240fbc1a10eea5b7dbecb641d'


class Failure(Exception):
    pass


def read_env(path: Path, private: bool = True) -> dict[str, str]:
    if path.is_symlink() or not path.is_file():
        raise Failure('configuration')
    if private and os.name != 'nt' and path.stat().st_mode & 0o077:
        raise Failure('permissions')
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator or not re.fullmatch(r'[A-Z][A-Z0-9_]*', key) or key in values:
            raise Failure('configuration')
        # Deliberately no shell evaluation, expansion or inline comments.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # Push credentials must not follow a redirect to another origin.


def push(url: str, up: bool, message: str) -> bool:
    try:
        parts = urlsplit(url)
        if parts.scheme != 'https' or not parts.netloc or parts.username or parts.fragment:
            return False
        target = urlunsplit((parts.scheme, parts.netloc, parts.path,
                            urlencode({'status': 'up' if up else 'down', 'msg': message}), ''))
        with build_opener(NoRedirect).open(Request(target), timeout=10) as response:
            return response.status == 200
    except Exception:
        return False


def private_dir(path: Path, uid: int | None = None):
    if path.is_symlink():
        raise Failure('directory')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    if uid is not None and os.name != 'nt':
        os.chown(path, uid, uid)


def digest(path: Path) -> str:
    return tool.sha256_file(path)


def check_manifest(folder: Path):
    manifest = json.loads((folder / 'manifest.json').read_text())
    if manifest.get('format') != 'iorp-backup/1' or manifest.get('encrypted') is not True:
        raise Failure('manifest')
    if manifest.get('referenced_but_missing'):
        raise Failure('missing-files')
    for name in ('database.dump', 'uploads.tar.gz'):
        tool.stored_artifact(folder, manifest, name)
    return manifest


def matching_receipt(folder: Path) -> bool:
    try:
        receipt = json.loads((folder / 'verification.json').read_text())
        return receipt.get('ok') is True and receipt['manifest_sha256'] == digest(folder / 'manifest.json')
    except (OSError, ValueError, KeyError):
        return False


def retained(names: list[str], daily=7, weekly=4, monthly=6) -> set[str]:
    dates = {datetime.strptime(n[5:], '%Y%m%dT%H%M%SZ'): n for n in names}
    keep = tool.keep_set(list(dates), daily, weekly, monthly)
    if dates:
        keep.add(max(dates))
    return {dates[d] for d in keep}


class Job:
    def __init__(self, config: dict[str, str]):
        self.c = config
        self.env = config['ENVIRONMENT']
        if self.env not in ('staging', 'production'):
            raise Failure('environment')
        raw_root = Path(config['STATE_DIR']).absolute()
        self.root = raw_root.resolve()
        if self.root == Path('/') or self.root != raw_root:
            raise Failure('state-directory')
        self.scratch = self.root / 'scratch'
        self.local = self.root / 'local'
        self.stage = 'preflight'
        self.container = 'iorp-backup-verify-' + uuid4().hex
        self.collector = 'iorp-backup-collect-' + uuid4().hex
        self.volume = self.container + '-data'
        self.network = self.container + '-net'
        self.active_db = False
        self.deadline = time.monotonic() + int(config.get('MAX_SECONDS', '7200'))
        self.child_env = {k: v for k, v in os.environ.items()
                          if k in ('PATH', 'HOME', 'SYSTEMROOT', 'DOCKER_CONFIG')}
        self.key_env = read_env(Path(config['KEY_ENV_FILE']))
        self.db_env = read_env(Path(config['DATABASE_ENV_FILE']))
        self.monitors = read_env(Path(config['PUSH_ENV_FILE']))
        tool._fernet(self.key_env.get('IORP_BACKUP_KEY'))
        if not self.db_env.get('DATABASE_URL'):
            raise Failure('database-configuration')
        rc = Path(config['RCLONE_CONFIG'])
        if rc.is_symlink() or not rc.is_file() or (os.name != 'nt' and rc.stat().st_mode & 0o077):
            raise Failure('rclone-permissions')
        if not re.fullmatch(r'[a-zA-Z0-9_-]+', config['RCLONE_REMOTE']):
            raise Failure('remote-name')
        self.remote = config['RCLONE_REMOTE'] + ':iorp-backups/' + self.env

    def budget(self):
        if time.monotonic() > self.deadline:
            raise Failure('timeout')
        if shutil.disk_usage(self.root).free < int(self.c.get('MIN_FREE_BYTES', str(2 * 1024**3))):
            raise Failure('free-space')
        size = sum(p.stat().st_size for p in self.scratch.rglob('*') if p.is_file())
        if size > int(self.c.get('MAX_SCRATCH_BYTES', str(8 * 1024**3))):
            raise Failure('scratch-size')
        if self.active_db:
            result = subprocess.run(['docker', 'exec', self.container, 'du', '-sk', '/var/lib/postgresql/data'],
                                    env=self.child_env, capture_output=True, timeout=10)
            if result.returncode or int(result.stdout.split()[0]) * 1024 > int(self.c.get('MAX_PG_BYTES', str(8 * 1024**3))):
                raise Failure('postgres-size')

    def run(self, args: list[str], env=None) -> str:
        # No shell, no subprocess errors or captured secrets reach the journal.
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            process = subprocess.Popen(args, stdout=stdout, stderr=stderr, env=env or self.child_env)
            try:
                while process.poll() is None:
                    self.budget()
                    time.sleep(0.5)
                if process.returncode:
                    raise Failure(self.stage)
                stdout.seek(0)
                data = stdout.read(1024 * 1024 + 1)
                if len(data) > 1024 * 1024:
                    raise Failure('output-size')
                return data.decode().strip()
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=15)

    def rclone(self, *args):
        return self.run(['rclone', '--config', self.c['RCLONE_CONFIG'], '--retries', '2',
                         '--contimeout', '15s', '--timeout', '2m', '--transfers', '1',
                         '--checkers', '1', '--bwlimit', self.c.get('BANDWIDTH', '8M'), *args])

    def compose(self, *args):
        return self.run(['docker', 'compose', '--env-file', self.c['COMPOSE_ENV_FILE'],
                         '-f', self.c['COMPOSE_FILE'], '--profile', 'backup', *args],
                        env={**self.child_env,
                             'IORP_BACKUP_DATABASE_ENV_FILE': self.c['DATABASE_ENV_FILE'],
                             'IORP_BACKUP_KEY_ENV_FILE': self.c['KEY_ENV_FILE'],
                             'IORP_BACKUP_OUT_DIR': str(self.scratch / 'collect')})

    def collect(self) -> Path:
        self.stage = 'backup'
        self.compose('pull', 'backup')
        out = self.scratch / 'collect'
        for attempt in range(2):
            private_dir(out, 10001)
            self.compose('run', '--rm', '--no-deps', '--name', self.collector, 'backup')
            folders = list(out.iterdir())
            if len(folders) != 1 or not STAMP.fullmatch(folders[0].name) or folders[0].is_symlink():
                raise Failure('backup-layout')
            folder = folders[0]
            private_dir(folder, 10001)
            try:
                check_manifest(folder)
                return folder
            except Failure as exc:
                if str(exc) != 'missing-files' or attempt:
                    raise
                shutil.rmtree(out)
                time.sleep(1)  # unique timestamp for the only allowed retry
        raise Failure('backup')

    def encrypt_manifest(self, folder):
        tool.encrypt_file(folder / 'manifest.json', folder / 'manifest.json.enc', self.key_env['IORP_BACKUP_KEY'])

    def transfer(self, folder: Path) -> Path:
        self.stage = 'upload'
        remote = self.remote + '/' + folder.name
        # Exact allowlist: neither manifest.json nor a receipt can leak in plaintext.
        for name in PAYLOADS:
            self.rclone('copyto', str(folder / name), remote + '/' + name, '--immutable')
        self.stage = 'download'
        downloaded = self.scratch / 'download' / folder.name
        private_dir(downloaded)
        for name in PAYLOADS:
            self.rclone('copyto', remote + '/' + name, str(downloaded / name))
            if digest(downloaded / name) != digest(folder / name):
                raise Failure('remote-checksum')
        tool.decrypt_file(downloaded / 'manifest.json.enc', downloaded / 'manifest.json', self.key_env['IORP_BACKUP_KEY'])
        check_manifest(downloaded)
        return downloaded

    def verify(self, folder: Path):
        self.stage = 'restore'
        self.run(['docker', 'pull', PG_IMAGE])
        # A separate bridge is required for a published loopback port (an internal
        # Docker network can suppress port publication). No app/db network joins.
        self.run(['docker', 'network', 'create', '--opt', 'com.docker.network.bridge.enable_icc=false',
                  '--label', 'iorp.purpose=backup-test', self.network])
        self.run(['docker', 'volume', 'create', '--label', 'iorp.purpose=backup-test', self.volume])
        password = uuid4().hex
        # Password passes through the environment, not argv, and is synthetic.
        container_id = self.run(['docker', 'run', '-d', '--name', self.container,
             '--label', 'iorp.purpose=backup-test', '--network', self.network,
             '--memory', '768m', '--memory-swap', '768m', '--cpus', '0.5', '--pids-limit', '128',
             '--security-opt', 'no-new-privileges:true', '-p', '127.0.0.1::5432',
             '--mount', 'type=volume,src=' + self.volume + ',dst=/var/lib/postgresql/data',
             '-e', 'POSTGRES_PASSWORD', PG_IMAGE], env={**self.child_env, 'POSTGRES_PASSWORD': password})
        self.active_db = True
        for _ in range(90):
            self.budget()
            ready = subprocess.run(['docker', 'exec', self.container, 'pg_isready', '-U', 'postgres'],
                                   env=self.child_env, capture_output=True, timeout=10)
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise Failure('postgres-start')
        port = self.run(['docker', 'port', self.container, '5432/tcp']).removeprefix('127.0.0.1:')
        if not port.isdigit():
            raise Failure('restore-port')
        scratch = self.scratch / 'restore'
        private_dir(scratch)
        target = f'postgresql+psycopg://postgres:{password}@127.0.0.1:{port}/iorp_restore_verify_target'
        env = {**self.child_env, 'APP_ENV': 'test', 'DATABASE_URL': self.db_env['DATABASE_URL'],
               'IORP_BACKUP_KEY': self.key_env['IORP_BACKUP_KEY'],
               'IORP_RESTORE_DATABASE_URL': target, 'IORP_RESTORE_CONTAINER_ID': container_id,
               'IORP_RESTORE_SCRATCH': str(scratch)}
        self.run([sys.executable, str(Path(tool.__file__)), 'verify', '--backup', str(folder),
                  '--docker-container', container_id], env=env)
        if not matching_receipt(folder):
            raise Failure('receipt')

    def receipt(self, source: Path, downloaded: Path):
        self.stage = 'receipt'
        shutil.copyfile(downloaded / 'verification.json', source / 'verification.json')
        receipt = source / 'verification.json.enc'
        tool.encrypt_file(source / 'verification.json', receipt, self.key_env['IORP_BACKUP_KEY'])
        remote = self.remote + '/' + source.name
        self.rclone('copyto', str(receipt), remote + '/verification.json.enc', '--immutable')
        back = self.scratch / 'receipt.enc'
        self.rclone('copyto', remote + '/verification.json.enc', str(back))
        if digest(back) != digest(receipt):
            raise Failure('receipt-checksum')
        # Publishing this encrypted completion record is the final remote write.
        marker = source / 'complete.json'
        marker.write_text(json.dumps({name: digest(source / name) for name in (*PAYLOADS, 'verification.json.enc')}))
        tool.encrypt_file(marker, source / 'complete.enc', self.key_env['IORP_BACKUP_KEY'])
        marker.unlink()
        self.rclone('copyto', str(source / 'complete.enc'), remote + '/complete.enc', '--immutable')
        self.rclone('copyto', remote + '/complete.enc', str(self.scratch / 'complete.enc'))
        if digest(self.scratch / 'complete.enc') != digest(source / 'complete.enc'):
            raise Failure('completion-checksum')
        destination = self.local / source.name
        if destination.exists():
            raise Failure('duplicate-backup')
        shutil.move(str(source), destination)
        return destination

    def remote_catalog(self) -> dict[str, Path]:
        catalog = {}
        names = self.rclone('lsf', self.remote, '--dirs-only').splitlines()
        if len(names) > 1000:
            raise Failure('catalog-size')
        for raw in names:
            name = raw.rstrip('/')
            if not STAMP.fullmatch(name):
                raise Failure('remote-layout')
            remote = self.remote + '/' + name
            entries = self.rclone('lsf', remote).splitlines()
            if 'complete.enc' not in entries:
                continue  # interrupted uploads are never recovery points or deletion candidates
            if set(entries) != {*PAYLOADS, 'verification.json.enc', 'complete.enc'}:
                raise Failure('remote-layout')
            folder = self.scratch / 'catalog' / name
            private_dir(folder)
            for item in entries:
                self.rclone('copyto', remote + '/' + item, str(folder / item))
            tool.decrypt_file(folder / 'complete.enc', folder / 'complete.json', self.key_env['IORP_BACKUP_KEY'])
            expected = json.loads((folder / 'complete.json').read_text())
            if set(expected) != {*PAYLOADS, 'verification.json.enc'}:
                raise Failure('remote-completion')
            if any(digest(folder / n) != expected[n] for n in expected):
                raise Failure('remote-checksum')
            for stem in ('manifest.json', 'verification.json'):
                tool.decrypt_file(folder / (stem + '.enc'), folder / stem, self.key_env['IORP_BACKUP_KEY'])
            check_manifest(folder)
            if not matching_receipt(folder):
                raise Failure('remote-receipt')
            catalog[name] = folder
            # Bound scratch across long retention histories; validation is complete.
            shutil.rmtree(folder)
        return catalog

    def retention(self, newest: Path):
        self.stage = 'retention'
        if not matching_receipt(newest):
            raise Failure('receipt')
        # Validate every remote candidate before deleting anything, including local files.
        catalog = self.remote_catalog()
        if not catalog or max(catalog) != newest.name:
            raise Failure('newest-remote')
        keep = retained(list(catalog))
        local = []
        for folder in self.local.iterdir():
            if folder.is_symlink() or not folder.is_dir() or not STAMP.fullmatch(folder.name):
                raise Failure('local-layout')
            check_manifest(folder)
            if not matching_receipt(folder) or folder.name not in catalog:
                raise Failure('local-receipt')
            local.append(folder)
        for name in sorted(set(catalog) - keep):
            # Exact generated paths only; never purge a parent or an unknown directory.
            self.rclone('purge', self.remote + '/' + name)
        for folder in sorted(local, key=lambda p: p.name, reverse=True)[3:]:
            if folder != newest:
                shutil.rmtree(folder)

    def cleanup(self):
        self.active_db = False
        try:
            daemon = subprocess.run(['docker', 'info', '--format', '{{.ServerVersion}}'],
                                    env=self.child_env, capture_output=True, timeout=15)
            ok = daemon.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            ok = False
        for kind, name, args in (
                ('container', self.collector, ['rm', '-f', '-v', self.collector]),
                ('container', self.container, ['rm', '-f', '-v', self.container]),
                ('volume', self.volume, ['volume', 'rm', '-f', self.volume]),
                ('network', self.network, ['network', 'rm', self.network])):
            # Resources are random, job-owned names; no global Docker prune.
            try:
                exists = subprocess.run(['docker', kind, 'inspect', name], env=self.child_env,
                                        capture_output=True, timeout=30)
                if exists.returncode == 0:
                    result = subprocess.run(['docker', *args], env=self.child_env, capture_output=True, timeout=30)
                    ok = ok and result.returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                ok = False
        if self.scratch.exists():
            shutil.rmtree(self.scratch)
        if not ok:
            raise Failure('cleanup')

    def execute(self):
        if self.c.get('ENABLED') != 'yes' or (self.env == 'production' and self.c.get('PRODUCTION_APPROVED') != 'yes'):
            raise Failure('disabled')
        private_dir(self.root)
        private_dir(self.local)
        if self.scratch.exists():
            raise Failure('stale-scratch')  # owner investigates interrupted host/power loss
        private_dir(self.scratch)
        try:
            self.budget()
            source = self.collect()
            self.encrypt_manifest(source)
            downloaded = self.transfer(source)
            self.verify(downloaded)
            newest = self.receipt(source, downloaded)
            self.retention(newest)
        finally:
            self.cleanup()
        self.stage = 'restore-push'
        if not push(self.monitors.get('RESTORE_PUSH_URL', ''), True, 'restore verified'):
            raise Failure('restore-push')
        self.stage = 'daily-push'
        if not push(self.monitors.get('DAILY_PUSH_URL', ''), True, 'backup complete'):
            raise Failure('daily-push')

    def drill(self):
        """Manual restore from the latest completed REMOTE recovery point only."""
        if self.c.get('ENABLED') != 'yes' or (self.env == 'production' and self.c.get('PRODUCTION_APPROVED') != 'yes'):
            raise Failure('disabled')
        private_dir(self.root)
        if self.scratch.exists():
            raise Failure('stale-scratch')
        private_dir(self.scratch)
        try:
            self.stage = 'download'
            catalog = self.remote_catalog()
            if not catalog:
                raise Failure('no-remote-backup')
            name = max(catalog)
            folder = self.scratch / 'download' / name
            private_dir(folder)
            for item in PAYLOADS:
                self.rclone('copyto', self.remote + '/' + name + '/' + item, str(folder / item))
            tool.decrypt_file(folder / 'manifest.json.enc', folder / 'manifest.json', self.key_env['IORP_BACKUP_KEY'])
            check_manifest(folder)
            self.verify(folder)
            receipts = self.root / 'manual-receipts'
            private_dir(receipts)
            target = receipts / (name + '-' + uuid4().hex + '.json')
            shutil.copyfile(folder / 'verification.json', target)
        finally:
            self.cleanup()
        if not push(self.monitors.get('RESTORE_PUSH_URL', ''), True, 'restore verified'):
            raise Failure('restore-push')


def disk(config):
    monitors = read_env(Path(config['PUSH_ENV_FILE']))
    usage = shutil.disk_usage(config['STATE_DIR'])
    healthy = (usage.total - usage.free) / usage.total <= 0.80
    if not push(monitors.get('DISK_PUSH_URL', ''), healthy, 'disk ok' if healthy else 'disk over 80 percent'):
        raise Failure('disk-push')
    if not healthy:
        raise Failure('disk-threshold')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('daily', 'drill', 'disk'))
    parser.add_argument('--config', required=True, type=Path)
    args = parser.parse_args()
    job = None
    config = None
    os.umask(0o077)
    def interrupted(*_):
        raise Failure('interrupted')
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        config = read_env(args.config)
        if args.command == 'disk':
            disk(config)
        else:
            # Linux host, same lock for manual and systemd executions, both environments.
            import fcntl
            with open('/run/lock/iorp-backup.lock', 'a') as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise Failure('busy') from None
                job = Job(config)
                job.execute() if args.command == 'daily' else job.drill()
        print('iorp-backup: success', flush=True)
        return 0
    except BaseException:
        # Never print the exception, argv, URLs, DB details or library traceback.
        stage = job.stage if job else 'configuration'
        if config and args.command in ('daily', 'drill'):
            with contextlib.suppress(Exception):
                monitors = read_env(Path(config['PUSH_ENV_FILE']))
                push(monitors.get('DAILY_PUSH_URL', ''), False, 'backup failed')
                if stage == 'restore':
                    push(monitors.get('RESTORE_PUSH_URL', ''), False, 'restore failed')
        print('iorp-backup: failed stage=' + stage, flush=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
