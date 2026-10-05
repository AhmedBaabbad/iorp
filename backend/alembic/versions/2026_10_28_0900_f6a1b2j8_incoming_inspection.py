"""Incoming inspection (QUAL-INC-001, PROC-002).

- quality_check_type gains incoming_inspection.
- quality_checks.receipt_id / receipt_line_id: the received lot (a procurement goods receipt line) an incoming inspection
  is about (plain UUIDs, no foreign key into procurement, ADR-004).
No permission changes: quality's inspection and NCR permissions, and procurement's read permissions, cover it.
"""
import sqlalchemy as sa
from alembic import op

revision = "f6a1b2j8"
down_revision = "f6a1b2j7"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE quality_check_type ADD VALUE IF NOT EXISTS 'incoming_inspection'")
    uuid = sa.Uuid()
    op.add_column("quality_checks", sa.Column("receipt_id", uuid))
    op.add_column("quality_checks", sa.Column("receipt_line_id", uuid))
    op.create_index("ix_quality_checks_receipt_id", "quality_checks", ["receipt_id"])
    op.create_index("ix_quality_checks_receipt_line_id", "quality_checks", ["receipt_line_id"])


def downgrade():
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT count(*) FROM quality_checks WHERE receipt_id IS NOT NULL OR check_type = 'incoming_inspection'")):
        raise RuntimeError("Incoming inspections exist; they are records and are not dropped by a downgrade.")
    op.drop_index("ix_quality_checks_receipt_line_id", "quality_checks")
    op.drop_index("ix_quality_checks_receipt_id", "quality_checks")
    op.drop_column("quality_checks", "receipt_line_id")
    op.drop_column("quality_checks", "receipt_id")
    # PostgreSQL cannot drop an enum value; an unused incoming_inspection value is harmless.
