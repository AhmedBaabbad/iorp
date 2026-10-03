"""Remove the report audit and reference counters (report_exports, report_counters).

Reports are generated from current data on each request and are not stored. Nothing reads the
audit any more (the export history screen was removed in f6a1b2i2), so reports no longer carry
an RPT- reference. Each report prints when it was issued and who prepared it, and failures go to
the server log. The audit rows are download records, not business data. The downgrade
recreates both tables empty, as f6a1b2h8 created them.
"""
import sqlalchemy as sa
from alembic import op

revision = "f6a1b2i4"
down_revision = "f6a1b2i3"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    rows = bind.scalar(sa.text("SELECT count(*) FROM report_exports"))
    op.drop_index("ix_report_exports_generated_at", table_name="report_exports")
    op.drop_index("ix_report_exports_organization_id", table_name="report_exports")
    op.drop_table("report_exports")
    op.drop_table("report_counters")
    print(f"Removed report audit: {rows} download record(s)")


def downgrade():
    op.create_table('report_counters', sa.Column('organization_id', sa.Uuid(), sa.ForeignKey('foundation_organizations.id'), primary_key=True),
                    sa.Column('module', sa.String(40), primary_key=True), sa.Column('year', sa.Integer(), primary_key=True),
                    sa.Column('value', sa.Integer(), nullable=False))
    op.create_table('report_exports', sa.Column('id', sa.Uuid(), primary_key=True),
                    sa.Column('organization_id', sa.Uuid(), sa.ForeignKey('foundation_organizations.id'), nullable=False),
                    sa.Column('report_key', sa.String(120), nullable=False), sa.Column('reference_no', sa.String(100), nullable=False),
                    sa.Column('params_json', sa.JSON(), nullable=False), sa.Column('format', sa.String(10), nullable=False),
                    sa.Column('generated_by_user_id', sa.Uuid(), sa.ForeignKey('foundation_users.id', ondelete='SET NULL')),
                    sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
                    sa.Column('page_count', sa.Integer()), sa.Column('duration_ms', sa.Integer()),
                    sa.Column('status', sa.String(20), nullable=False), sa.Column('error_message', sa.String(200)),
                    sa.UniqueConstraint('organization_id', 'reference_no', name='uq_report_reference'))
    op.create_index('ix_report_exports_organization_id', 'report_exports', ['organization_id'])
    op.create_index('ix_report_exports_generated_at', 'report_exports', ['generated_at'])
