import importlib.util
import logging
import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def migration():
    path = Path(__file__).parents[1] / "alembic/versions/2026_11_25_1200_f6a1b2p8_quality_bilingual.py"
    spec = importlib.util.spec_from_file_location("quality_bilingual_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exercise(connection, caplog):
    revision = migration()
    assert revision.down_revision == "f6a1b2p7"
    originals = ["نص عربي English", "English only", None]
    identifiers = [uuid4() for _ in originals]
    organization_id, foreign_id, specification_id = uuid4(), uuid4(), uuid4()
    metadata = sa.MetaData()
    items = sa.Table("masterdata_list_items", metadata, sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid()), sa.Column("list", sa.String()), sa.Column("key", sa.String()),
        sa.Column("name_ar", sa.String()), sa.Column("name_en", sa.String()), sa.Column("active", sa.Boolean()), sa.Column("sort_order", sa.Integer()))
    items.create(connection)
    connection.execute(items.insert(), [dict(id=uuid4(), organization_id=org, list="test_method", key="method", name_ar=arabic,
        name_en=originals[1], active=True, sort_order=1) for org, arabic in ((organization_id, "الطريقة الرسمية"), (foreign_id, "منظمة أخرى"))])
    specifications = sa.Table("quality_specifications", metadata, sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("organization_id", sa.Uuid()))
    specifications.create(connection)
    connection.execute(specifications.insert(), dict(id=specification_id, organization_id=organization_id))
    for name, fields in revision.TABLES.items():
        scope = ([sa.Column("specification_id", sa.Uuid()), sa.Column("target_source", sa.String()),
                  sa.Column("min_value", sa.Numeric()), sa.Column("max_value", sa.Numeric())]
                 if name == "quality_specification_lines" else [sa.Column("organization_id", sa.Uuid())])
        table = sa.Table(name, metadata, sa.Column("id", sa.Uuid(), primary_key=True),
                         *scope, *(sa.Column(field, sa.String(255), nullable=True) for field in fields))
        table.create(connection)
        connection.execute(table.insert(), [dict(id=identifier, **({"specification_id":specification_id} if name == "quality_specification_lines"
            else {"organization_id":organization_id}), **{field: value for field in fields})
                                             for identifier, value in zip(identifiers, originals)])
        if name == "quality_specification_lines":
            connection.execute(table.update().where(table.c.id == identifiers[0]).values(target_source="order_line", min_value=1, max_value=2))
    with Operations.context(MigrationContext.configure(connection)), caplog.at_level(logging.INFO):
        revision.upgrade()
        for name, fields in revision.TABLES.items():
            table = sa.Table(name, sa.MetaData(), autoload_with=connection)
            for field in fields:
                assert field not in table.c
                assert table.c[f"{field}_ar"].type.length == 255 and table.c[f"{field}_ar"].nullable
                rows = {UUID(str(row.id)): row._mapping for row in connection.execute(sa.select(table))}
                assert rows[identifiers[0]][f"{field}_ar"] == originals[0]
                assert rows[identifiers[0]][f"{field}_en"] is None
                assert rows[identifiers[1]][f"{field}_en"] == originals[1]
                assert rows[identifiers[1]][f"{field}_ar"] == ("الطريقة الرسمية" if field == "method" else None)
                assert rows[identifiers[2]][f"{field}_ar"] is None
            connection.execute(table.update().where(table.c.id == identifiers[0]).values(
                **{f"{field}_en": "Other language" for field in fields}))
            if name == "quality_specification_lines":
                assert rows[identifiers[0]]["min_value"] == 1 and rows[identifiers[0]]["max_value"] == 2
        revision.downgrade()
        for name, fields in revision.TABLES.items():
            table = sa.Table(name, sa.MetaData(), autoload_with=connection)
            rows = {UUID(str(row.id)): row._mapping for row in connection.execute(sa.select(table))}
            for field in fields:
                assert rows[identifiers[0]][field] == originals[0]  # Arabic wins coalesce.
                assert rows[identifiers[1]][field] == ("الطريقة الرسمية" if field == "method" else originals[1])
                assert f"{field}_ar" not in table.c
        revision.upgrade()
    assert all(value not in caplog.text for value in originals if value)
    assert "rows=2" in caplog.text
    assert "Quality order_line min/max ignored: rows=1" in caplog.text
    assert "Quality method Arabic backfill: table=quality_specification_lines rows=1" in caplog.text
    assert "الطريقة الرسمية" not in caplog.text and "منظمة أخرى" not in caplog.text


def test_bilingual_migration_upgrade_downgrade_and_rerun(caplog):
    with sa.create_engine("sqlite:///:memory:").begin() as connection:
        exercise(connection, caplog)


@pytest.mark.skipif(os.environ.get("RUN_POSTGRES_TESTS") != "1", reason="Isolated PostgreSQL opt-in")
def test_bilingual_migration_postgres(caplog):
    from app.core.db import engine
    schema = "quality_bilingual_" + uuid4().hex
    with engine.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated = sa.create_engine(engine.url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        with isolated.begin() as connection:
            exercise(connection, caplog)
    finally:
        isolated.dispose()
        with engine.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
