"""Development-only PostgreSQL + attachment recovery rehearsal.

No application configuration is loaded. No existing server/container is accepted.
The only database server used is created here, without ports, mounts or network.
Artifacts contain synthetic data only. Production backup scheduling is separate.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import zipfile


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def require_equal(actual, expected, description):
    """Recovery checks must remain active under python -O."""
    if actual != expected:
        raise RuntimeError(f'Recovery verification failed: {description}')


def archive_files(source, destination):
    source = Path(source).resolve(strict=True)
    destination = Path(destination).resolve()
    if destination.is_relative_to(source):
        raise ValueError('Backup must be outside source')
    with zipfile.ZipFile(destination, 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob('*')):
            if path.is_symlink() or not path.resolve().is_relative_to(source):
                raise ValueError('Linked files are not allowed')
            if path.is_file():
                archive.write(path, path.relative_to(source).as_posix())


def restore_files(archive_path, target):
    target = Path(target).resolve()
    if target.exists():
        raise ValueError('Restore destination must not exist')
    with zipfile.ZipFile(archive_path) as archive:
        for entry in archive.infolist():
            relative = Path(entry.filename)
            if relative.is_absolute() or ':' in entry.filename or not (target / relative).resolve().is_relative_to(target):
                raise ValueError('Unsafe archive member')
            if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Archive links are forbidden')
        target.mkdir(parents=True)
        archive.extractall(target)


def docker(*args):
    return subprocess.run(['docker', *args], check=True, capture_output=True, text=True).stdout.strip()


def application_schema_sql():
    # Import model registrations without starting FastAPI or opening an engine.
    os.environ.update(APP_ENV='test', DEBUG='false', EMAIL_MODE='console',
                      PRODUCTION_AUTO_START_BY_DATE='false',
                      DATABASE_URL='postgresql+psycopg://unused:unused@127.0.0.1:1/unreachable')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.main import app  # noqa: F401
    from app.core.db import Base
    from sqlalchemy import create_mock_engine
    statements = []
    engine = create_mock_engine('postgresql+psycopg://', lambda sql, *a, **k: statements.append(str(sql.compile(dialect=engine.dialect))))
    Base.metadata.create_all(engine, checkfirst=False)
    return ';\n'.join(statements) + ';\n'


def rehearse(output, application_schema=False):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    name = 'iorp-recovery-test-' + uuid.uuid4().hex
    started = time.monotonic()
    created = False
    try:
        docker('run', '-d', '--name', name, '--label', 'iorp.purpose=recovery-test', '--network', 'none',
               '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', 'postgres:16')
        created = True
        for _ in range(60):
            try:
                docker('exec', name, 'pg_isready', '-U', 'postgres')
                break
            except subprocess.CalledProcessError:
                time.sleep(1)
        else:
            raise RuntimeError('Isolated PostgreSQL did not become ready')
        def sql(database, statement):
            return docker('exec', name, 'psql', '-U', 'postgres', '-d', database, '-v', 'ON_ERROR_STOP=1', '-Atc', statement)
        sql('postgres', 'CREATE DATABASE rehearsal_source')
        if application_schema:
            schema = output / 'application-schema.sql'
            schema.write_text(application_schema_sql(), encoding='utf-8')
            docker('cp', str(schema), name + ':/tmp/application-schema.sql')
            docker('exec', name, 'psql', '-U', 'postgres', '-d', 'rehearsal_source', '-v', 'ON_ERROR_STOP=1', '-f', '/tmp/application-schema.sql')
        sql('rehearsal_source', "CREATE TABLE tenants(id int PRIMARY KEY, name text); CREATE TABLE documents(id int PRIMARY KEY, tenant_id int REFERENCES tenants(id), path text); INSERT INTO tenants VALUES (1,'Synthetic A'),(2,'Synthetic B'); INSERT INTO documents VALUES (1,1,'organizations/1/example.txt'),(2,2,'organizations/2/example.txt'); CREATE TABLE alembic_version(version_num text); INSERT INTO alembic_version VALUES ('synthetic-fixture-not-app-schema')")
        uploads = output / 'source-files'
        for tenant in (1, 2):
            file = uploads / 'organizations' / str(tenant) / 'example.txt'
            file.parent.mkdir(parents=True)
            file.write_text(f'Synthetic attachment {tenant}', encoding='utf-8')
        docker('exec', name, 'pg_dump', '-U', 'postgres', '-Fc', '--no-owner', '--no-acl', '-f', '/tmp/rehearsal.dump', 'rehearsal_source')
        docker('cp', name + ':/tmp/rehearsal.dump', str(output / 'database.dump'))
        archive_files(uploads, output / 'files.zip')
        manifest = {p: digest(output / p) for p in ('database.dump', 'files.zip')}
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        restore_start = time.monotonic()
        for path, expected in manifest.items():
            if digest(output / path) != expected:
                raise ValueError('Backup checksum mismatch')
        # Restore the exported artifact, not the original in-container dump.
        docker('cp', str(output / 'database.dump'), name + ':/tmp/exported.dump')
        sql('postgres', 'CREATE DATABASE rehearsal_restored')
        docker('exec', name, 'pg_restore', '-U', 'postgres', '--exit-on-error', '--single-transaction', '--no-owner', '--no-acl', '-d', 'rehearsal_restored', '/tmp/exported.dump')
        query = 'SELECT d.id,t.name,d.path FROM documents d JOIN tenants t ON t.id=d.tenant_id ORDER BY d.id'
        require_equal(sql('rehearsal_restored', query), sql('rehearsal_source', query), 'document relationships')
        require_equal(sql('rehearsal_restored', 'SELECT count(*) FROM documents'), '2', 'document count')
        table_query = "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        require_equal(sql('rehearsal_restored', table_query), sql('rehearsal_source', table_query), 'table inventory')
        restore_files(output / 'files.zip', output / 'restored-files')
        for source in uploads.rglob('*.txt'):
            require_equal(digest(output / 'restored-files' / source.relative_to(uploads)), digest(source), 'attachment checksum')
        result = {'result': 'PASS', 'postgres': sql('postgres', 'SHOW server_version'),
                  'synthetic_tenants': 2, 'restored_documents': 2, 'restored_files': 2,
                  'restore_seconds': round(time.monotonic() - restore_start, 3),
                  'total_seconds': round(time.monotonic() - started, 3),
                  'application_metadata_schema_restored': application_schema,
                  'restored_tables': len(sql('rehearsal_restored', table_query).splitlines()),
                  'migration_chain_verified': False, 'production_rpo_rto_verified': False}
        (output / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result))
    finally:
        if created:
            # Only our exact randomly named and labelled disposable container.
            label = docker('inspect', '--format', '{{index .Config.Labels "iorp.purpose"}}', name)
            if label != 'recovery-test':
                raise RuntimeError('Refusing cleanup: unexpected container label')
            docker('rm', '-f', '-v', name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='New directory for synthetic artifacts')
    parser.add_argument('--application-schema', action='store_true', help='Also roundtrip the current ORM schema; not an Alembic migration-chain test')
    args = parser.parse_args()
    rehearse(args.output, args.application_schema)
