"""Quality decisions on returned goods (QUAL-RET-001, SHIP-005).

- quality_checks.return_id / return_line_id and quality_rejections.return_id / return_line_id: an inspection of a
  returned line and its rejected parts (plain UUIDs, no foreign key into shipping, ADR-004).
- shipping_returns.quality_required: the goods go to quality; filled for returns already received whose reason puts the
  goods in question (a quality reason, transit damage, other).
No permission changes: existing quality and shipping permissions cover it.
"""
import sqlalchemy as sa
from alembic import op

revision = "f6a1b2j5"
down_revision = "f6a1b2j4"
branch_labels = None
depends_on = None


def upgrade():
    uuid = sa.Uuid()
    for table in ("quality_checks", "quality_rejections"):
        op.add_column(table, sa.Column("return_id", uuid))
        op.add_column(table, sa.Column("return_line_id", uuid))
        op.create_index(f"ix_{table}_return_id", table, ["return_id"])
    op.create_index("ix_quality_checks_return_line_id", "quality_checks", ["return_line_id"])
    op.add_column("shipping_returns", sa.Column("quality_required", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE shipping_returns SET quality_required = true WHERE status = 'received' AND reason IN "
               "('quality_issue', 'quality_defect', 'spec_mismatch', 'transit_damage', 'other')")


def downgrade():
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT count(*) FROM quality_checks WHERE return_id IS NOT NULL")):
        raise RuntimeError("Inspections of returned goods exist; they are records and are not dropped by a downgrade.")
    op.drop_column("shipping_returns", "quality_required")
    op.drop_index("ix_quality_checks_return_line_id", "quality_checks")
    for table in ("quality_checks", "quality_rejections"):
        op.drop_index(f"ix_{table}_return_id", table)
        op.drop_column(table, "return_line_id")
        op.drop_column(table, "return_id")
