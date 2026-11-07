"""IORP backup, restore-verification and retention (OPS-BACKUP-001).

    python scripts/backup/iorp_backup.py backup  --out DIR [--docker-container NAME] [--no-encrypt]
    python scripts/backup/iorp_backup.py verify  --backup DIR/<stamp> [--docker-container NAME] [--keep-database]
    python scripts/backup/iorp_backup.py prune   --out DIR [--daily 7 --weekly 4 --monthly 12] [--apply]

A backup is one folder `iorp-<UTC stamp>/`:
    database.dump[.enc]   pg_dump custom format, taken inside an exported REPEATABLE READ snapshot
    uploads.tar.gz[.enc]  the UPLOADS_DIR tree
    manifest.json         checksums, Alembic revision, row count of every table (same snapshot), the upload files
                          (path, size, sha256) and the stored file keys the database references but the disk lacks

It only READS the source database and the uploads folder. `verify` restores into a NEW database whose name must start
with `iorp_restore_verify_` (never the source, never an existing one) on an explicitly supplied test server, compares it with the
manifest, unpacks the uploads into a temporary folder, checks every file, and drops that new database afterwards
(unless --keep-database). Encryption: Fernet (AES-128-CBC + HMAC-SHA256) in 16 MB chunks, the key in IORP_BACKUP_KEY
(`python scripts/backup/iorp_backup.py new-key` prints one; keep it apart from the backups).
Verification requires IORP_RESTORE_DATABASE_URL (database component starting
iorp_restore_verify_) and a dedicated private IORP_RESTORE_SCRATCH directory.
It never defaults to the application's database. Prune requires a matching
successful verification receipt for the newest intact backup and always keeps it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

VERIFY_PREFIX = "iorp_restore_verify_"
CHUNK = 16 * 1024 * 1024
KEY_PATTERN = re.compile(r"^organizations/[0-9a-fA-F-]{36}/")


def wait_postgres_connection(url, deadline, budget=lambda: None):
    """Confirm the published host endpoint, retrying transient startup failures.

    Never propagate connection diagnostics: they may contain credentials.
    The caller supplies a monotonic deadline bounded by its startup/job budget.
    """
    while True:
        budget()
        remaining = deadline - time.monotonic()
        # Allow libpq's two-second minimum timeout plus the one-second query.
        if remaining < 3:
            raise TimeoutError('postgres-start') from None
        engine = create_engine(url, connect_args={'connect_timeout': 2, 'options': '-c statement_timeout=1000'})
        try:
            with engine.connect() as connection:
                connection.execute(text('SELECT 1'))
            if time.monotonic() >= deadline:
                raise TimeoutError('postgres-start') from None
            budget()
            return
        except OperationalError:
            pass
        finally:
            engine.dispose()
        time.sleep(min(1, max(0, deadline - time.monotonic())))


# ── small helpers ────────────────────────────────────────────────────────────────────────────────

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fernet(key: str | None):
    if not key:
        raise SystemExit("IORP_BACKUP_KEY is not set (or pass --no-encrypt for a local, unprotected copy).")
    from cryptography.fernet import Fernet
    return Fernet(key.encode())


def encrypt_file(source: Path, target: Path, key: str) -> None:
    """Chunked: [4-byte length][token]…, so a large dump never sits whole in memory."""
    fernet = _fernet(key)
    with source.open("rb") as src, target.open("wb") as dst:
        for block in iter(lambda: src.read(CHUNK), b""):
            token = fernet.encrypt(block)
            dst.write(len(token).to_bytes(4, "big") + token)


def decrypt_file(source: Path, target: Path, key: str) -> None:
    fernet = _fernet(key)
    with source.open("rb") as src, target.open("wb") as dst:
        while header := src.read(4):
            length = int.from_bytes(header, "big")
            if len(header) != 4 or not 1 <= length <= CHUNK * 2:
                raise SystemExit('Invalid encrypted frame length')
            token = src.read(length)
            if len(token) != length:
                raise SystemExit('Truncated encrypted backup')
            dst.write(fernet.decrypt(token))


def dump_table_count(dump: Path, key: str | None, container: str | None) -> int:
    """Inspect the actual archive TOC, not merely the source catalog/manifest.

    Stream decrypted data into pg_restore; only its metadata listing uses a private
    temporary file, preventing pipe deadlocks for schemas with many tables.
    """
    command = (["docker", "exec", "-i", container] if container else []) + ["pg_restore", "--list"]
    with tempfile.TemporaryFile() as listing, dump.open('rb') as source:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=listing, stderr=subprocess.DEVNULL)
        try:
            try:
                _feed_dump(process.stdin, source, key)
            except BrokenPipeError:
                # --list exits after the TOC without consuming the table data.
                pass
            finally:
                try:
                    process.stdin.close()
                except BrokenPipeError:
                    pass
            if process.wait() != 0:
                raise SystemExit('Cannot inspect dump table coverage')
            listing.seek(0)
            return sum(bool(re.match(rb'^\d+; \d+ \d+ TABLE public ', line)) for line in listing)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()


def _feed_dump(stdin, source, key):
    if key:
        fernet = _fernet(key)
        while header := source.read(4):
            length = int.from_bytes(header, 'big')
            if len(header) != 4 or not 1 <= length <= CHUNK * 2:
                raise SystemExit('Invalid encrypted dump frame')
            token = source.read(length)
            if len(token) != length:
                raise SystemExit('Truncated encrypted dump')
            stdin.write(fernet.decrypt(token))
    else:
        shutil.copyfileobj(source, stdin, CHUNK)


class BackupSink:
    """Write encrypted frames directly; never persist a plaintext dump first."""
    def __init__(self, handle, key):
        self.handle = handle
        self.fernet = _fernet(key) if key else None
        self.digest = hashlib.sha256()
        self.size = 0

    def write(self, data):
        self.digest.update(data)
        self.size += len(data)
        for offset in range(0, len(data), CHUNK):
            block = data[offset:offset + CHUNK]
            if self.fernet:
                block = self.fernet.encrypt(block)
                self.handle.write(len(block).to_bytes(4, 'big'))
            self.handle.write(block)
        return len(data)

    def flush(self):
        self.handle.flush()


def stored_artifact(folder, manifest, name):
    entry = manifest['artifacts'][name]
    expected_name = name + ('.enc' if manifest['encrypted'] else '')
    if entry['stored_as'] != expected_name:
        raise SystemExit('Unsafe artifact name')
    path = folder / expected_name
    if path.is_symlink() or path.resolve().parent != folder.resolve():
        raise SystemExit('Artifact is outside backup directory')
    if not path.is_file() or sha256_file(path) != entry['stored_sha256']:
        raise SystemExit('Backup artifact missing or corrupt')
    return path


def settings():
    from app.core.config import get_settings
    return get_settings()


def database_url(override: str | None = None):
    return make_url(override or settings().database_url)


def pg_command(tool: str, url, database: str, container: str | None, extra: list[str]) -> tuple[list[str], dict]:
    """pg_dump / pg_restore either on this machine or inside the PostgreSQL container (the same server version)."""
    if container:
        return ["docker", "exec", "-i", container, tool, "-U", url.username, "-d", database, *extra], dict(os.environ)
    env = dict(os.environ, PGPASSWORD=url.password or "")
    return [tool, "-h", url.host or "localhost", "-p", str(url.port or 5432), "-U", url.username, "-d", database, *extra], env


def table_counts(connection) -> dict[str, int]:
    names = connection.execute(text(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")).scalars().all()
    return {name: connection.execute(text(f'SELECT count(*) FROM "{name}"')).scalar_one() for name in names}


def referenced_keys(connection) -> set[str]:
    """Every stored file key (organizations/<org>/…) held in a text column — the links between rows and files."""
    columns = connection.execute(text(
        "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public' "
        "AND data_type IN ('character varying', 'text') "
        "AND (column_name LIKE '%path%' OR column_name LIKE '%key%' OR column_name LIKE '%file%')")).all()
    keys: set[str] = set()
    for table, column in columns:
        values = connection.execute(text(
            f'SELECT DISTINCT "{column}" FROM "{table}" WHERE "{column}" LIKE \'organizations/%\'')).scalars().all()
        keys.update(value for value in values if value and KEY_PATTERN.match(value))
    return keys


def upload_inventory(root: Path) -> dict[str, dict]:
    if not root.is_dir():
        return {}
    root = root.resolve()
    files = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise SystemExit('Linked uploads are not supported by safe backup')
        if path.is_file():
            files[path.relative_to(root).as_posix()] = {'size': path.stat().st_size, 'sha256': sha256_file(path)}
    return files


# ── backup ───────────────────────────────────────────────────────────────────────────────────────

def backup(out: Path, container: str | None, encrypt: bool, url_override: str | None = None,
           uploads_dir: Path | None = None) -> Path:
    key = os.environ.get("IORP_BACKUP_KEY") if encrypt else None
    if encrypt:
        _fernet(key)  # refuse before touching anything
    url = database_url(url_override)
    uploads = (uploads_dir if uploads_dir is not None else BACKEND / settings().uploads_dir).resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = out / f"iorp-{stamp}"
    folder.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    engine = create_engine(url.render_as_string(hide_password=False))
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            snapshot = connection.execute(text("SELECT pg_export_snapshot()")).scalar_one()
            counts = table_counts(connection)
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
            keys = referenced_keys(connection)
            command, env = pg_command("pg_dump", url, url.database, container, ["-Fc", f"--snapshot={snapshot}"])
            stored_dump = folder / ("database.dump.enc" if encrypt else "database.dump")
            with stored_dump.open("xb") as handle:
                sink = BackupSink(handle, key)
                # stderr is not logged: client errors can contain connection details.
                with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env) as process:
                    for block in iter(lambda: process.stdout.read(CHUNK), b""):
                        sink.write(block)
                    if process.wait() != 0:
                        raise SystemExit("pg_dump failed; incomplete backup must not be retained as valid")
                sink.flush()
                dump_info = {"sha256": sink.digest.hexdigest(), "bytes": sink.size,
                             "stored_as": stored_dump.name, "stored_sha256": sha256_file(stored_dump)}
    engine.dispose()
    archived_tables = dump_table_count(stored_dump, key, container)
    if archived_tables != len(counts):
        raise SystemExit('Dump table count differs from pg_tables; refusing incomplete backup')
    files = upload_inventory(uploads)
    stored_tar = folder / ("uploads.tar.gz.enc" if encrypt else "uploads.tar.gz")
    with stored_tar.open("xb") as handle:
        sink = BackupSink(handle, key)
        with tarfile.open(fileobj=sink, mode="w|gz") as archive:
            if uploads.is_dir():
                archive.add(uploads, arcname="uploads")
        sink.flush()
        tar_info = {"sha256": sink.digest.hexdigest(), "bytes": sink.size,
                    "stored_as": stored_tar.name, "stored_sha256": sha256_file(stored_tar)}
    missing = sorted(key for key in keys if key not in files)
    artifacts = {"database.dump": dump_info, "uploads.tar.gz": tar_info}
    manifest = {
        "format": "iorp-backup/1", "created_at": stamp, "encrypted": encrypt, "source_database": url.database,
        "alembic_revision": revision, "table_counts": counts, "artifacts": artifacts,
        "uploads": {"root": "uploads", "files": files, "file_count": len(files), "bytes": sum(f["size"] for f in files.values())},
        "referenced_file_keys": len(keys), "referenced_but_missing": missing,
        "dump_public_tables": archived_tables,
        "seconds": round(time.monotonic() - started, 2),
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"backup": str(folder), "tables": len(counts), "rows": sum(counts.values()),
                      "files": len(files), "seconds": manifest["seconds"]}, ensure_ascii=False))
    return folder


# ── restore verification ─────────────────────────────────────────────────────────────────────────

def safe_extract(tar: Path, target: Path) -> None:
    """Only plain files and folders, each inside `target` (no links, devices nor `..`) — whatever Python's version."""
    target = target.resolve()
    if target.exists():
        raise SystemExit('Restore extraction destination must not exist')
    with tarfile.open(tar, "r:gz") as archive:
        members = archive.getmembers()
        for member in members:
            destination = (target / member.name).resolve()
            if ':' in member.name or not (member.isfile() or member.isdir()) or (destination != target and target not in destination.parents):
                raise SystemExit(f"Unsafe entry in the uploads archive: {member.name}")
        archive.extractall(target, members=members)


def verification_name(source: str, requested: str | None = None) -> str:
    name = requested or f"{VERIFY_PREFIX}{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    if not name.startswith(VERIFY_PREFIX) or name == source or not re.fullmatch(r"[a-z0-9_]{1,63}", name):
        raise SystemExit(f"Refusing to restore into '{name}': only a new database named {VERIFY_PREFIX}… is allowed.")
    return name


def _artifact(folder: Path, manifest: dict, name: str, work: Path) -> Path:
    entry = manifest["artifacts"][name]
    stored = folder / entry["stored_as"]
    if sha256_file(stored) != entry["stored_sha256"]:
        raise SystemExit(f"{stored.name}: checksum mismatch — the backup is damaged.")
    if not manifest["encrypted"]:
        return stored
    plain = work / name
    decrypt_file(stored, plain, os.environ.get("IORP_BACKUP_KEY"))
    if sha256_file(plain) != entry["sha256"]:
        raise SystemExit(f"{name}: decrypted content does not match the manifest.")
    return plain


def validate_restore_destination(url, container: str | None) -> None:
    """Only an explicitly identified disposable local Docker server may be restored.

    Verify Docker's actual published endpoint, not just the requested DB name.
    Remote daemons, URL connection overrides and host-mounted data fail closed.
    """
    expected = os.environ.get("IORP_RESTORE_CONTAINER_ID", "")
    if os.environ.get("APP_ENV") != "test" or not container or not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise SystemExit("Restore requires APP_ENV=test and the full disposable IORP_RESTORE_CONTAINER_ID")
    if url.host != "127.0.0.1" or not url.port or url.query:
        raise SystemExit("Restore URL must use the verified loopback port without connection overrides")
    if os.environ.get("DOCKER_HOST") or os.environ.get("DOCKER_CONTEXT"):
        raise SystemExit("Restore refuses Docker endpoint environment overrides")
    try:
        application = make_url(os.environ.get("DATABASE_URL") or settings().database_url)
    except Exception as exc:  # the application's server must be known to be excluded
        raise SystemExit("Cannot determine the application database to exclude it") from exc
    if application.host in {"127.0.0.1", "localhost", "::1"} and (application.port or 5432) == url.port:
        raise SystemExit("Restore destination is the application database server")
    try:
        context = json.loads(subprocess.check_output(["docker", "context", "inspect"], stderr=subprocess.PIPE))[0]
        endpoint = context["Endpoints"]["docker"]["Host"]
        if not endpoint.startswith(("npipe://", "unix://")):
            raise ValueError("remote daemon")
        info = json.loads(subprocess.check_output(["docker", "inspect", container], stderr=subprocess.PIPE))[0]
        bindings = info["NetworkSettings"]["Ports"].get("5432/tcp") or []
        if (info["Id"] != expected or not info["State"]["Running"]
                or info["Config"].get("Labels", {}).get("iorp.purpose") != "backup-test"
                or info["HostConfig"].get("NetworkMode") in {"host", "container"}
                or any(m.get("Type") == "bind" for m in info.get("Mounts", []))
                or bindings != [{"HostIp": "127.0.0.1", "HostPort": str(url.port)}]):
            raise ValueError("destination identity mismatch")
    except (subprocess.SubprocessError, OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise SystemExit("Cannot independently confirm disposable restore destination") from exc


def verify(folder: Path, container: str | None, keep: bool, target: str | None = None, url_override: str | None = None) -> dict:
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if not url_override:
        raise SystemExit("Restore verification requires an explicit isolated target URL; never defaults to application database")
    url = database_url(url_override)
    validate_restore_destination(url, container)
    if not url.database or not url.database.startswith(VERIFY_PREFIX):
        raise SystemExit("Target connection database must identify an isolated verification server")
    name = verification_name(manifest["source_database"], target)
    scratch = os.environ.get('IORP_RESTORE_SCRATCH')
    if not scratch or not Path(scratch).is_dir():
        raise SystemExit('Set IORP_RESTORE_SCRATCH to a dedicated private scratch directory')
    started = time.monotonic()
    admin = create_engine(url.set(database="postgres").render_as_string(hide_password=False), isolation_level="AUTOCOMMIT")
    report: dict = {"backup": folder.name, "database": name}
    with tempfile.TemporaryDirectory(prefix="iorp-verify-", dir=scratch) as temp:
        work = Path(temp)
        dump = _artifact(folder, manifest, "database.dump", work)
        tar = _artifact(folder, manifest, "uploads.tar.gz", work)
        with admin.connect() as connection:
            if connection.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": name}).first():
                raise SystemExit(f"'{name}' already exists; refusing to overwrite it.")
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        try:
            command, env = pg_command("pg_restore", url, name, container, ["--no-owner", "--exit-on-error", "--single-transaction"])
            with dump.open("rb") as handle:
                done = subprocess.run(command, stdin=handle, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            if done.returncode != 0:
                raise SystemExit(f"pg_restore failed: {done.stderr.decode(errors='replace')[:500]}")
            restored = create_engine(url.set(database=name).render_as_string(hide_password=False))
            with restored.connect() as connection:
                counts = table_counts(connection)
                revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
                keys = referenced_keys(connection)
            restored.dispose()
            unpacked = work / "unpacked"
            safe_extract(tar, unpacked)
            files = upload_inventory(unpacked / "uploads")
            problems = []
            if counts != manifest["table_counts"]:
                diff = {t: (manifest["table_counts"].get(t), counts.get(t))
                        for t in set(counts) | set(manifest["table_counts"]) if counts.get(t) != manifest["table_counts"].get(t)}
                problems.append({"table_counts": diff})
            if revision != manifest["alembic_revision"]:
                problems.append({"alembic_revision": [manifest["alembic_revision"], revision]})
            if files != manifest["uploads"]["files"]:
                problems.append({"uploads": "file list, sizes or checksums differ"})
            missing = sorted(key for key in keys if key not in files)
            if missing != manifest["referenced_but_missing"]:
                problems.append({"file_links": {"backup": manifest["referenced_but_missing"], "restored": missing}})
            report.update(ok=not problems, problems=problems, tables=len(counts), rows=sum(counts.values()),
                          files=len(files), file_links=len(keys), links_without_file=len(missing),
                          alembic_revision=revision, seconds=round(time.monotonic() - started, 2))
        finally:
            if not keep:
                with admin.connect() as connection:
                    connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
                report["database_dropped"] = True
    admin.dispose()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report.get("ok"):
        raise SystemExit(1)
    receipt = {"ok": True, "manifest_sha256": sha256_file(folder / "manifest.json"),
               "verified_at": datetime.now(timezone.utc).isoformat()}
    (folder / "verification.json").write_text(json.dumps(receipt), encoding="utf-8")
    return report


# ── retention ────────────────────────────────────────────────────────────────────────────────────

def keep_set(stamps: list[datetime], daily: int, weekly: int, monthly: int) -> set[datetime]:
    """Grandfather-father-son: the newest backup of each of the last `daily` days, `weekly` ISO weeks, `monthly` months."""
    keep: set[datetime] = set()
    for count, bucket in ((daily, lambda d: d.date()), (weekly, lambda d: d.isocalendar()[:2]), (monthly, lambda d: (d.year, d.month))):
        seen = []
        for stamp in sorted(stamps, reverse=True):
            label = bucket(stamp)
            if label not in seen:
                seen.append(label)
                if len(seen) > count:
                    break
                keep.add(stamp)
    return keep


def prune(out: Path, daily: int, weekly: int, monthly: int, apply: bool) -> list[Path]:
    if min(daily, weekly, monthly) < 0:
        raise SystemExit('Retention counts cannot be negative')
    out = out.resolve(strict=True)
    folders = {}
    for p in out.glob('iorp-*'):
        if p.is_symlink() or p.resolve().parent != out:
            raise SystemExit('Refusing retention outside backup root')
        if not p.is_dir():
            continue
        try:
            stamp = datetime.strptime(p.name[5:], '%Y%m%dT%H%M%SZ')
            manifest = json.loads((p / 'manifest.json').read_text(encoding='utf-8'))
            if manifest.get('format') != 'iorp-backup/1':
                raise ValueError('Unknown format')
            for artifact in ('database.dump', 'uploads.tar.gz'):
                stored_artifact(p, manifest, artifact)
        except (OSError, ValueError, KeyError) as exc:
            raise SystemExit('Retention stopped: incomplete or invalid backup') from exc
        folders[stamp] = p
    if not folders:
        return []
    newest = max(folders)
    try:
        receipt = json.loads((folders[newest] / 'verification.json').read_text(encoding='utf-8'))
        verified = receipt.get('ok') is True and receipt.get('manifest_sha256') == sha256_file(folders[newest] / 'manifest.json')
    except (OSError, ValueError):
        verified = False
    if not verified:
        raise SystemExit('Retention stopped: newest backup has no matching successful restore verification')
    keep = keep_set(list(folders), daily, weekly, monthly)
    keep.add(newest)  # Never delete the last verified recovery point, even with 0/0/0.
    drop = [folders[s] for s in sorted(folders) if s not in keep]
    for folder in drop:
        print(("deleting " if apply else "would delete ") + folder.name)
        if apply:
            shutil.rmtree(folder)
    return drop


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("backup"); b.add_argument("--out", required=True, type=Path)
    b.add_argument("--docker-container"); b.add_argument("--no-encrypt", action="store_true")
    v = sub.add_parser("verify"); v.add_argument("--backup", required=True, type=Path)
    v.add_argument("--docker-container"); v.add_argument("--keep-database", action="store_true")
    p = sub.add_parser("prune"); p.add_argument("--out", required=True, type=Path)
    p.add_argument("--daily", type=int, default=7); p.add_argument("--weekly", type=int, default=4)
    p.add_argument("--monthly", type=int, default=12); p.add_argument("--apply", action="store_true")
    sub.add_parser("new-key")
    args = parser.parse_args(argv)
    if args.command == "backup":
        backup(args.out, args.docker_container, not args.no_encrypt)
    elif args.command == "verify":
        verify(args.backup, args.docker_container, args.keep_database, url_override=os.environ.get("IORP_RESTORE_DATABASE_URL"))
    elif args.command == "prune":
        prune(args.out, args.daily, args.weekly, args.monthly, args.apply)
    else:
        from cryptography.fernet import Fernet
        print(Fernet.generate_key().decode())


if __name__ == "__main__":
    main()
