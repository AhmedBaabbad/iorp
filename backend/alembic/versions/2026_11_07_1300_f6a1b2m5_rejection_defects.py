"""PROD-QUALITY-FIX-001 item 5: a quality rejection may name several defects; a defect type is recorded once per inspection.

- New table quality_rejection_defects (one row per rejection and defect, optional affected quantity; unique per
  rejection and defect). Each existing rejection's quality_defect_id becomes one row, then the column is dropped.
  The downgrade restores, per rejection, its most severe defect (critical > major > minor; ties: the earliest found)
  and prints what it drops.
- quality_defects gets a unique key on (inspection, defect category): one inspection records a defect type once and
  counts it with defect_count. Existing duplicates, if any, are reported and the key is not created over them.
"""
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "f6a1b2m5"
down_revision = "f6a1b2m4"
branch_labels = None
depends_on = None

RANK = {"critical": 3, "major": 2, "minor": 1}


def upgrade():
    op.create_table(
        "quality_rejection_defects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("foundation_organizations.id"), nullable=False),
        sa.Column("quality_rejection_id", sa.Uuid(), sa.ForeignKey("quality_rejections.id", ondelete="CASCADE", name="fk_rejection_defect_rejection"),
                  nullable=False),
        sa.Column("quality_defect_id", sa.Uuid(), sa.ForeignKey("quality_defects.id", ondelete="RESTRICT", name="fk_rejection_defect_defect"),
                  nullable=False),
        sa.Column("affected_quantity", sa.Numeric(15, 3)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("affected_quantity IS NULL OR affected_quantity > 0", name="ck_rejection_defect_quantity"),
        sa.UniqueConstraint("quality_rejection_id", "quality_defect_id", name="uq_rejection_defect"),
    )
    op.create_index("ix_rejection_defect_rejection", "quality_rejection_defects", ["quality_rejection_id"])
    op.create_index("ix_rejection_defect_defect", "quality_rejection_defects", ["organization_id", "quality_defect_id"])
    bind = op.get_bind()
    rejections = sa.table("quality_rejections", sa.column("id", sa.Uuid()), sa.column("organization_id", sa.Uuid()),
                          sa.column("quality_defect_id", sa.Uuid()))
    rows = bind.execute(sa.select(rejections.c.id, rejections.c.organization_id, rejections.c.quality_defect_id)
                        .where(rejections.c.quality_defect_id.is_not(None))).all()
    links = sa.table("quality_rejection_defects", sa.column("id", sa.Uuid()), sa.column("organization_id", sa.Uuid()),
                     sa.column("quality_rejection_id", sa.Uuid()), sa.column("quality_defect_id", sa.Uuid()),
                     sa.column("created_at", sa.DateTime(timezone=True)), sa.column("updated_at", sa.DateTime(timezone=True)))
    now = datetime.now(timezone.utc)
    if rows:
        op.bulk_insert(links, [dict(id=uuid.uuid4(), organization_id=org, quality_rejection_id=rejection, quality_defect_id=defect,
                                    created_at=now, updated_at=now) for rejection, org, defect in rows])
    print(f"quality_rejection_defects: {len(rows)} rejection(s) with a defect -> {len(rows)} row(s)")
    with op.batch_alter_table("quality_rejections") as batch:
        batch.drop_index("ix_quality_rejections_quality_defect_id")
        batch.drop_column("quality_defect_id")

    duplicates = bind.execute(sa.text("SELECT quality_check_id, defect_category, count(*) FROM quality_defects "
                                      "GROUP BY quality_check_id, defect_category HAVING count(*) > 1")).all()
    if duplicates:
        print(f"quality_defects: {len(duplicates)} inspection(s) record a defect type more than once; unique key NOT created: {duplicates}")
    else:
        with op.batch_alter_table("quality_defects") as batch:
            batch.create_unique_constraint("uq_quality_defects_check_category", ["quality_check_id", "defect_category"])
        print("quality_defects: one row per inspection and defect type (unique key created)")


def downgrade():
    bind = op.get_bind()
    has_key = any(c.get("name") == "uq_quality_defects_check_category" for c in sa.inspect(bind).get_unique_constraints("quality_defects"))
    if has_key:
        with op.batch_alter_table("quality_defects") as batch:
            batch.drop_constraint("uq_quality_defects_check_category", type_="unique")
    with op.batch_alter_table("quality_rejections") as batch:
        batch.add_column(sa.Column("quality_defect_id", sa.Uuid(), sa.ForeignKey("quality_defects.id", name="fk_quality_rejections_defect")))
        batch.create_index("ix_quality_rejections_quality_defect_id", ["quality_defect_id"])
    rows = bind.execute(sa.text("SELECT l.quality_rejection_id, l.quality_defect_id, d.severity, d.created_at FROM quality_rejection_defects l "
                                "JOIN quality_defects d ON d.id = l.quality_defect_id")).all()
    chosen, dropped = {}, 0
    for rejection, defect, severity, created in sorted(rows, key=lambda r: (str(r[0]), -RANK.get(str(r[2]), 0), r[3])):
        if rejection in chosen:
            dropped += 1
        else:
            chosen[rejection] = defect
    for rejection, defect in chosen.items():
        bind.execute(sa.text("UPDATE quality_rejections SET quality_defect_id = :d WHERE id = :r"), dict(d=defect, r=rejection))
    print(f"quality_rejections: quality_defect_id restored on {len(chosen)} rejection(s) (most severe); {dropped} other link(s) dropped")
    op.drop_index("ix_rejection_defect_defect", table_name="quality_rejection_defects")
    op.drop_index("ix_rejection_defect_rejection", table_name="quality_rejection_defects")
    op.drop_table("quality_rejection_defects")
