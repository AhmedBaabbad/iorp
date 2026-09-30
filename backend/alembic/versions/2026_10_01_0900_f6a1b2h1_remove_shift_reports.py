"""Remove shift reports.

Hand-written shift reports are replaced by reports computed from the actual records
(orders, rosters, outputs, waste, downtime, quality). Their table, the optional links
from those records, and the shift_reports permissions are removed.

Revision ID: f6a1b2h1
Revises: f6a1b2h0
"""
import importlib.util
from pathlib import Path
from alembic import op
import sqlalchemy as sa

revision = "f6a1b2h1"
down_revision = "f6a1b2h0"
branch_labels = None
depends_on = None

LINKED = ("production_outputs", "production_downtime_events", "production_waste_records", "quality_checks")
PERMISSIONS = ("production:shift_reports:read", "production:shift_reports:write")


def _drop_link(bind, table):
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(table):
        if fk["constrained_columns"] == ["shift_report_id"]:
            op.drop_constraint(fk["name"], table, type_="foreignkey")
    for index in inspector.get_indexes(table):
        if index["column_names"] == ["shift_report_id"]:
            op.drop_index(index["name"], table_name=table)
    op.drop_column(table, "shift_report_id")


def upgrade():
    bind = op.get_bind()
    # Refuse rather than silently destroy reports someone wrote.
    if bind.scalar(sa.text("SELECT count(*) FROM production_shift_reports")):
        raise RuntimeError("Shift reports exist; export or archive them before removing the feature")
    for table in LINKED:
        _drop_link(bind, table)
    op.drop_table("production_shift_reports")
    op.execute("DROP TYPE IF EXISTS production_shift_report_status")
    codes = {"codes": list(PERMISSIONS)}
    bind.execute(sa.text("DELETE FROM foundation_role_permissions WHERE permission_id IN (SELECT id FROM foundation_permissions WHERE code = ANY(:codes))"), codes)
    bind.execute(sa.text("DELETE FROM foundation_permissions WHERE code = ANY(:codes)"), codes)


def downgrade():
    # Rebuild the table exactly as its baseline migration created it, then restore the links.
    path = Path(__file__).with_name("2026_07_01_0900_7e3a5f1d_shift_reports_baseline.py")
    spec = importlib.util.spec_from_file_location("shift_reports_baseline", path)
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)
    baseline.upgrade()
    for table in LINKED:
        op.add_column(table, sa.Column("shift_report_id", sa.Uuid(), nullable=True))
        op.create_index(f"ix_{table}_shift_report_id", table, ["shift_report_id"])
        if table != "quality_checks":  # quality keeps plain references across modules (ADR-004)
            op.create_foreign_key(f"{table}_shift_report_id_fkey", table, "production_shift_reports", ["shift_report_id"], ["id"])
    # Removed permissions are not recreated; re-grant them explicitly if the feature returns.
