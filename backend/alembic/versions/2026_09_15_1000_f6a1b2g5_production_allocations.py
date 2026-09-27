"""Demand allocations; preserve old header references before removing them.

Revision ID: f6a1b2g5
Revises: f6a1b2g4
"""
from alembic import op
import sqlalchemy as sa
from uuid import uuid4

revision = "f6a1b2g5"
down_revision = "f6a1b2g4"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    op.create_table("production_allocations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("foundation_organizations.id"), nullable=False),
        sa.Column("production_order_id", sa.Uuid(), sa.ForeignKey("production_orders.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("production_demand_id", sa.Uuid(), sa.ForeignKey("production_demands.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("production_demand_item_id", sa.Uuid(), sa.ForeignKey("production_demand_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("allocated_quantity", sa.Numeric(15, 3), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("foundation_users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("allocated_quantity > 0", name="ck_allocation_quantity"),
        sa.UniqueConstraint("organization_id", "production_order_id", "production_demand_item_id", name="uq_allocation_org_order_item"))
    op.create_index("ix_production_allocations_organization_id", "production_allocations", ["organization_id"])
    for suffix, field in (("order", "production_order_id"), ("item", "production_demand_item_id"), ("demand", "production_demand_id")):
        op.create_index(f"ix_allocation_org_{suffix}", "production_allocations", ["organization_id", field])
    # Always retain nullable archive columns for a uniform schema across databases.
    # Local investigation found zero references. Other databases copy every value.
    for old, archive in (("commercial_order_id", "legacy_commercial_order_ref"), ("shift_definition_id", "legacy_shift_ref")):
        op.add_column("production_orders", sa.Column(archive, sa.JSON()))
        bind.execute(sa.text(f"UPDATE production_orders SET {archive} = json_build_object('{old}', {old}::text, 'migrated_at', now()::text) WHERE {old} IS NOT NULL"))
        for fk in sa.inspect(bind).get_foreign_keys("production_orders"):
            if old in fk["constrained_columns"]:
                op.drop_constraint(fk["name"], "production_orders", type_="foreignkey")
        op.drop_index(f"ix_production_orders_{old}", table_name="production_orders")
        op.drop_column("production_orders", old)
    op.alter_column("production_orders", "planned_quantity", type_=sa.Numeric(15, 3), existing_type=sa.Numeric(14, 2))
    # Convert priority to a checked string so upgrade/downgrade stay transactional.
    op.alter_column("production_orders", "priority", type_=sa.String(10), postgresql_using="priority::text")
    op.create_check_constraint("ck_production_order_priority", "production_orders", "priority IN ('low','normal','high','urgent')")
    # Old manual planning states have no allocations yet and must return to queue.
    bind.execute(sa.text("UPDATE production_demands SET status = 'ready_for_planning' WHERE status IN ('partially_planned','planned')"))
    for org_id in bind.scalars(sa.text("SELECT id FROM foundation_organizations")):
        for resource, action, name in (("planning", "allocate", "Allocate Quantities to Production Orders"), ("orders", "create", "Create Production Orders")):
            bind.execute(sa.text("INSERT INTO foundation_permissions (id, organization_id, code, name, description, module_name, resource_name, action_name, created_at, updated_at) VALUES (:id,:org,:code,CAST(:name AS text),CAST(:name AS text),'production',:resource,:action,now(),now()) ON CONFLICT (organization_id,code) DO NOTHING"), dict(id=uuid4(), org=org_id, code=f"production:{resource}:{action}", name=name, resource=resource, action=action))


def downgrade():
    bind = op.get_bind()
    # Refuse to discard newly created allocations. An operator must archive these
    # business records before a downgrade, rather than silently erase provenance.
    if bind.scalar(sa.text("SELECT count(*) FROM production_allocations")):
        raise RuntimeError("Archive production allocations before downgrading")
    if bind.scalar(sa.text("SELECT count(*) FROM production_orders WHERE priority = 'high' OR planned_quantity <> round(planned_quantity, 2)")):
        raise RuntimeError("Orders use new precision/priority; archive before downgrading")
    for old, archive in (("commercial_order_id", "legacy_commercial_order_ref"), ("shift_definition_id", "legacy_shift_ref")):
        op.add_column("production_orders", sa.Column(old, sa.Uuid()))
        bind.execute(sa.text(f"UPDATE production_orders SET {old} = ({archive}->>'{old}')::uuid WHERE {archive} IS NOT NULL"))
        op.create_index(f"ix_production_orders_{old}", "production_orders", [old])
        op.drop_column("production_orders", archive)
    op.create_foreign_key("production_orders_shift_definition_id_fkey", "production_orders", "production_shift_definitions", ["shift_definition_id"], ["id"])
    op.drop_constraint("ck_production_order_priority", "production_orders", type_="check")
    op.execute("ALTER TABLE production_orders ALTER COLUMN priority TYPE production_order_priority USING priority::production_order_priority")
    op.alter_column("production_orders", "planned_quantity", type_=sa.Numeric(14, 2), existing_type=sa.Numeric(15, 3))
    op.drop_table("production_allocations")
