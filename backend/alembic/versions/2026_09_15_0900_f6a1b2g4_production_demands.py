"""Customer production demands, snapshot items and organization counters."""
from alembic import op
import sqlalchemy as sa

revision = "f6a1b2g4"
down_revision = "f6a1b2g3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("production_demand_counters",
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("foundation_organizations.id"), primary_key=True),
        sa.Column("year", sa.Integer(), primary_key=True),
        sa.Column("last_value", sa.Integer(), nullable=False))
    op.create_table("production_demands",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("foundation_organizations.id"), nullable=False),
        sa.Column("demand_number", sa.String(30), nullable=False),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("commercial_customers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quote_id", sa.Uuid(), sa.ForeignKey("commercial_quotes.id", ondelete="SET NULL")),
        sa.Column("request_date", sa.Date(), nullable=False),
        sa.Column("requested_delivery_date", sa.Date()),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("status", sa.String(25), nullable=False),
        sa.Column("planning_sequence", sa.Integer()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("foundation_users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "demand_number", name="uq_production_demands_org_number"),
        sa.CheckConstraint("status IN ('draft','ready_for_planning','partially_planned','planned','cancelled')", name="ck_demand_status"),
        sa.CheckConstraint("priority IN ('low','normal','high','urgent')", name="ck_demand_priority"))
    for suffix, columns in (("organization_id", ["organization_id"]), ("org_status", ["organization_id", "status"]), ("org_customer", ["organization_id", "customer_id"]), ("org_sequence", ["organization_id", "planning_sequence"])):
        op.create_index(f"ix_production_demands_{suffix}", "production_demands", columns)
    op.create_table("production_demand_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("production_demand_id", sa.Uuid(), sa.ForeignKey("production_demands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("product_type", sa.String(100)),
        sa.Column("target_spec_json", sa.JSON()),
        sa.Column("required_quantity", sa.Numeric(15, 3), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("production_demand_id", "line_no", name="uq_production_demand_items_line"),
        sa.CheckConstraint("required_quantity > 0", name="ck_demand_item_quantity"),
        sa.CheckConstraint("line_no > 0", name="ck_demand_item_line"))
    op.create_index("ix_production_demand_items_production_demand_id", "production_demand_items", ["production_demand_id"])


def downgrade():
    op.drop_table("production_demand_items")
    op.drop_table("production_demands")
    op.drop_table("production_demand_counters")
