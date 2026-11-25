"""Bilingual quality wording, including immutable inspection-plan snapshots.

Revision ID: f6a1b2p8
Revises: f6a1b2p7
"""
import logging
import re

from alembic import op
import sqlalchemy as sa

revision = "f6a1b2p8"
down_revision = "f6a1b2p7"
branch_labels = None
depends_on = None

TABLES = {
    "quality_specification_lines": ("requirement", "acceptance", "method"),
    "quality_test_parameters": ("method",),
    "quality_check_measurements": ("requirement", "acceptance", "method"),
}
ARABIC = re.compile(r"[\u0600-\u06ff]")
logger = logging.getLogger("alembic.runtime.migration")


def upgrade():
    bind = op.get_bind()
    for table_name, fields in TABLES.items():
        for field in fields:
            for language in ("ar", "en"):
                op.add_column(table_name, sa.Column(f"{field}_{language}", sa.String(255), nullable=True))
        table = sa.table(table_name, sa.column("id", sa.Uuid()),
            *(sa.column(name, sa.String(255)) for field in fields for name in (field, f"{field}_ar", f"{field}_en")))
        cursor = bind.execute(sa.select(table.c.id, *(table.c[field] for field in fields)))
        count = 0
        while rows := cursor.mappings().fetchmany(1000):
            for row in rows:
                values = {}
                for field in fields:
                    value = row[field]
                    if value is not None:
                        values[f"{field}_{'ar' if ARABIC.search(value) else 'en'}"] = value
                if values:
                    bind.execute(table.update().where(table.c.id == row["id"]).values(**values))
                    count += 1
        cursor.close()
        for field in fields:
            op.drop_column(table_name, field)
        logger.info("Quality bilingual migration: table=%s rows=%d", table_name, count)


def downgrade():
    bind = op.get_bind()
    for table_name, fields in TABLES.items():
        for field in fields:
            op.add_column(table_name, sa.Column(field, sa.String(255), nullable=True))
        table = sa.table(table_name, *(sa.column(name, sa.String(255)) for field in fields
            for name in (field, f"{field}_ar", f"{field}_en")))
        bind.execute(table.update().values(**{field: sa.func.coalesce(table.c[f"{field}_ar"], table.c[f"{field}_en"]) for field in fields}))
        for field in fields:
            for language in ("ar", "en"):
                op.drop_column(table_name, f"{field}_{language}")
