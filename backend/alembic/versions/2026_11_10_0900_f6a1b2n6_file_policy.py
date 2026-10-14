"""PROJECT-FILES-003: one file policy, small stored files, a quota per organization.

- foundation_organizations.storage_quota_bytes (empty = the platform default, 2 GB).
- The tables that hold uploaded files' metadata gain what was missing: commercial_complaint_attachments size_bytes and
  checksum; quality_ncr_attachments and shipping_attachments checksum and archived_at / archived_by_user_id (a file of a
  finished record is archived, never deleted); foundation_stored_assets size_bytes and checksum.
- Existing files are not moved, renamed nor compressed: their size and sha256 are read from where they are (each
  missing file is printed and left with size 0, its row untouched otherwise).
"""
import hashlib
import os
from pathlib import Path

from alembic import op
import sqlalchemy as sa

revision = "f6a1b2n6"
down_revision = "f6a1b2n5"
branch_labels = None
depends_on = None

FILES = (("commercial_complaint_attachments", "storage_path", True), ("quality_ncr_attachments", "storage_path", False),
         ("shipping_attachments", "storage_path", False), ("foundation_stored_assets", "storage_key", True))


def _root() -> Path:
    return Path(os.environ.get("UPLOADS_DIR", "uploads")).resolve()


def upgrade():
    op.add_column("foundation_organizations", sa.Column("storage_quota_bytes", sa.BigInteger(), nullable=True))
    for table in ("commercial_complaint_attachments", "foundation_stored_assets"):
        op.add_column(table, sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"))
    for table, _, _ in FILES:
        op.add_column(table, sa.Column("checksum", sa.String(64), nullable=True))
    for table in ("quality_ncr_attachments", "shipping_attachments"):
        op.add_column(table, sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("archived_by_user_id", sa.Uuid(), sa.ForeignKey("foundation_users.id"), nullable=True))

    bind, root = op.get_bind(), _root()
    measured = missing = 0
    for table, column, sets_size in FILES:
        for row_id, key in bind.execute(sa.text(f"SELECT id, {column} FROM {table}")).all():
            path = (root / key).resolve()
            if root not in path.parents or not path.is_file():
                missing += 1
                print(f"{table} {row_id}: file not found at {key} (left as it is)")
                continue
            content = path.read_bytes()
            values = dict(c=hashlib.sha256(content).hexdigest(), i=row_id)
            if sets_size:
                values["s"] = len(content)
            bind.execute(sa.text(f"UPDATE {table} SET checksum = :c{', size_bytes = :s' if sets_size else ''} WHERE id = :i"), values)
            measured += 1
    print(f"files: {measured} measured, {missing} not found; none moved or changed")


def downgrade():
    for table in ("quality_ncr_attachments", "shipping_attachments"):
        op.drop_column(table, "archived_by_user_id")
        op.drop_column(table, "archived_at")
    for table, _, _ in FILES:
        op.drop_column(table, "checksum")
    for table in ("commercial_complaint_attachments", "foundation_stored_assets"):
        op.drop_column(table, "size_bytes")
    op.drop_column("foundation_organizations", "storage_quota_bytes")
