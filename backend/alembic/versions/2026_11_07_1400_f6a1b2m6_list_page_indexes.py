"""PROD-QUALITY-FIX-001 item 2: indexes for the paged lists of production and quality (ARCH-PAGE-001).

Each list filters by organization and sorts by one column (then id); an index on (organization_id, that column) lets the
database read a page in order instead of sorting the organization's whole table. Status filters that lacked one get it.

  production_orders            (organization_id, planned_start_date)   order list sort
  production_orders            (organization_id, status)               status filter, order pickers
  production_waste_records     (organization_id, waste_date)           waste list sort
  production_downtime_events   (organization_id, start_time)           downtime list sort
  production_shift_rosters     (organization_id, effective_from)       roster list sort
  quality_checks               (organization_id, check_datetime)       inspection list sort
  quality_checks               (organization_id, status)               status filter
  quality_rejections           (organization_id, rejection_date)       rejection list sort
  quality_defects              (organization_id, defect_date)          defect list sort
  non_conformance_reports      (organization_id, report_date)          NCR list sort
  quality_ncr_actions          (organization_id, due_date)             corrective-action list sort
  quality_certificates         (organization_id, created_at)           certificate list sort
"""
from alembic import op

revision = "f6a1b2m6"
down_revision = "f6a1b2m5"
branch_labels = None
depends_on = None

INDEXES = (
    ("ix_production_orders_org_start", "production_orders", "planned_start_date"),
    ("ix_production_orders_org_status", "production_orders", "status"),
    ("ix_waste_org_date", "production_waste_records", "waste_date"),
    ("ix_downtime_org_start", "production_downtime_events", "start_time"),
    ("ix_roster_org_from", "production_shift_rosters", "effective_from"),
    ("ix_quality_checks_org_datetime", "quality_checks", "check_datetime"),
    ("ix_quality_checks_org_status", "quality_checks", "status"),
    ("ix_quality_rejections_org_date", "quality_rejections", "rejection_date"),
    ("ix_quality_defects_org_date", "quality_defects", "defect_date"),
    ("ix_ncr_org_date", "non_conformance_reports", "report_date"),
    ("ix_ncr_actions_org_due", "quality_ncr_actions", "due_date"),
    ("ix_quality_certificates_org_created", "quality_certificates", "created_at"),
)


def upgrade():
    for name, table, column in INDEXES:
        op.create_index(name, table, ["organization_id", column])
    print(f"list page indexes: {len(INDEXES)} created")


def downgrade():
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table)
