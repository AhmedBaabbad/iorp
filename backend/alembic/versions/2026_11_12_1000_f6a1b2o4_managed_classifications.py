"""MD-003: classifications a department names become reference lists the organization manages.

- Supplier and material categories, defect categories, rejection reasons, complaint categories, customer interaction
  types and vehicle types are now keys of the organization's lists (master data). The values already stored are the keys
  of the lists' usual values, so no record changes; the columns become free strings (60) and the old enum types go.
- ck_masterdata_list_items_list accepts every list (it still named only the first four, so downtime and scrap reasons,
  skills and test methods could not be saved on PostgreSQL).
- Every organization receives the usual values of a list it has no item in yet (it edits them afterwards).
The downgrade restores the column types only when every stored value is one of the original values.
"""
from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

from app.masterdata.domain import lists as L

revision = "f6a1b2o4"
down_revision = "f6a1b2o3"
branch_labels = None
depends_on = None

ENUMS = {  # table, column, enum type, original values
    "defect": ("quality_defects", "defect_category", "quality_defect_category",
               ("dimension", "thickness", "surface", "color", "strength", "winding", "weight", "packaging", "labeling", "finish", "other")),
    "rejection": ("quality_rejections", "rejection_reason", "quality_rejection_reason",
                  ("failed_quality_check", "critical_defect", "out_of_spec", "dimension_failure", "surface_failure", "packaging_failure",
                   "labeling_issue", "other")),
    "interaction": ("commercial_customer_interactions", "interaction_type", "customer_interaction_type", ("call", "visit", "whatsapp", "email", "meeting")),
}
WIDEN = (("procurement_suppliers", "category", 16), ("procurement_materials", "category", 16), ("commercial_complaints", "category", 32))
NEW_LISTS = ("downtime_reason", "waste_reason", "workforce_skill", "test_method", "supplier_category", "material_category", "defect_category",
             "rejection_reason", "complaint_category", "interaction_type", "vehicle_type")


def _check(lists):
    return "list IN (" + ", ".join(f"'{name}'" for name in lists) + ")"


def upgrade():
    bind = op.get_bind()
    postgres = bind.dialect.name == "postgresql"
    for table, column, enum_name, _values in ENUMS.values():
        with op.batch_alter_table(table) as batch:
            batch.alter_column(column, type_=sa.String(60), existing_nullable=False,
                               postgresql_using=f"{column}::text")
        if postgres:
            op.execute(f"DROP TYPE IF EXISTS {enum_name}")
    for table, column, _size in WIDEN:
        with op.batch_alter_table(table) as batch:
            batch.alter_column(column, type_=sa.String(60))
    with op.batch_alter_table("masterdata_list_items") as batch:
        batch.drop_constraint("ck_masterdata_list_items_list", type_="check")
        batch.create_check_constraint("ck_masterdata_list_items_list", _check(L.LISTS))

    meta = sa.MetaData()
    orgs, items = (sa.Table(n, meta, autoload_with=bind) for n in ("foundation_organizations", "masterdata_list_items"))
    for table in (orgs, items):
        for c in table.c:
            if c.name in ("id", "organization_id"):
                c.type = sa.Uuid()
    now, seeded = datetime.now(timezone.utc), 0
    for org in bind.scalars(sa.select(orgs.c.id)):
        present = set(bind.scalars(sa.select(items.c.list).where(items.c.organization_id == org).distinct()))
        for name in NEW_LISTS:
            if name in present:
                continue
            for order, row in enumerate(L.STANDARD[name], 1):
                bind.execute(items.insert().values(id=uuid4(), organization_id=org, list=name, key=row[0], name_ar=row[1], name_en=row[2],
                                                   parent_key=None, active=True, sort_order=order, created_at=now, updated_at=now))
                seeded += 1
    print(f"managed classifications: {seeded} usual values added")


def downgrade():
    bind = op.get_bind()
    postgres = bind.dialect.name == "postgresql"
    for table, column, enum_name, values in ENUMS.values():
        stray = bind.scalar(sa.text(f"SELECT count(*) FROM {table} WHERE {column} NOT IN ({', '.join(repr(v) for v in values)})"))
        if stray:
            raise RuntimeError(f"{table}.{column} holds {stray} value(s) outside the original ones; map them before downgrading")
        if postgres:
            sa.Enum(*values, name=enum_name).create(bind, checkfirst=True)
        with op.batch_alter_table(table) as batch:
            batch.alter_column(column, type_=sa.Enum(*values, name=enum_name), existing_nullable=False,
                               postgresql_using=f"{column}::{enum_name}")
    bind.execute(sa.text(f"DELETE FROM masterdata_list_items WHERE list IN ({', '.join(repr(n) for n in NEW_LISTS[4:])})"))
    with op.batch_alter_table("masterdata_list_items") as batch:
        batch.drop_constraint("ck_masterdata_list_items_list", type_="check")
        batch.create_check_constraint("ck_masterdata_list_items_list", _check(L.LISTS[:8]))
