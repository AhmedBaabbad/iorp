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
    legacy_lines = sa.table("quality_specification_lines", sa.column("target_source"), sa.column("min_value"), sa.column("max_value"))
    ignored = bind.scalar(sa.select(sa.func.count()).select_from(legacy_lines).where(
        legacy_lines.c.target_source == "order_line",
        sa.or_(legacy_lines.c.min_value.is_not(None), legacy_lines.c.max_value.is_not(None))))
    logger.info("Quality order_line min/max ignored: rows=%d", ignored)
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
    _fill_official_arabic(bind)


def _fill_official_arabic(bind):
    items = sa.table("masterdata_list_items", *(sa.column(name) for name in
        ("organization_id", "list", "name_en", "name_ar", "active", "sort_order", "key", "id")))
    specifications = sa.table("quality_specifications", sa.column("id"), sa.column("organization_id"))
    for name in TABLES:
        table = sa.table(name, *(sa.column(column) for column in
            ("id", "organization_id", "specification_id", "method_en", "method_ar")))
        organization = (sa.select(specifications.c.organization_id).where(specifications.c.id == table.c.specification_id)
                        .correlate(table).scalar_subquery()) if name == "quality_specification_lines" else table.c.organization_id
        arabic = (sa.select(items.c.name_ar).where(items.c.organization_id == organization,
            items.c.list == "test_method", items.c.name_en == table.c.method_en)
            .order_by(items.c.active.desc(), items.c.sort_order, items.c.key, items.c.id).limit(1).correlate(table).scalar_subquery())
        result = bind.execute(table.update().where(sa.or_(table.c.method_ar.is_(None), table.c.method_ar == ""),
            table.c.method_en.is_not(None), arabic.is_not(None)).values(method_ar=arabic))
        logger.info("Quality method Arabic backfill: table=%s rows=%d", name, result.rowcount or 0)


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
