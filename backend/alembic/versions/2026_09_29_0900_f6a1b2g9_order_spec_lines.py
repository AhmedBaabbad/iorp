"""Planning orders accept differing specifications as ordered lines.

Allocations link to the order line (production_order_items) they feed; one ACTIVE
allocation per demand item per order (released history may repeat); line quantities
use the allocation precision.

Revision ID: f6a1b2g9
Revises: f6a1b2g8
"""
import json
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from alembic import op
import sqlalchemy as sa

revision = "f6a1b2g9"
down_revision = "f6a1b2g8"
branch_labels = None
depends_on = None

# Frozen copy of the ordering at migration time: width -> color -> thickness -> weight.
_SORT_KEYS = (("width_mm", "width"), ("color", "colour"), ("thickness_mm", "thickness", "thickness_micron"), ("roll_weight_kg", "weight_kg", "weight"))


def _part(spec, names):
    value = next((spec[n] for n in names if spec.get(n) not in (None, "")), None)
    if value is None:
        return (1, 0, Decimal(0), "")
    try:
        return (0, 0, Decimal(str(value).strip()), "")
    except (InvalidOperation, ValueError):
        return (0, 1, Decimal(0), str(value).strip().casefold())


def _spec(raw):
    if raw is None:
        return {}
    return raw if isinstance(raw, dict) else json.loads(raw)


def upgrade():
    bind = op.get_bind()
    op.add_column("production_allocations", sa.Column("production_order_item_id", sa.Uuid(),
                  sa.ForeignKey("production_order_items.id", ondelete="SET NULL", name="fk_allocation_order_item")))
    op.create_index("ix_production_allocations_production_order_item_id", "production_allocations", ["production_order_item_id"])
    op.drop_constraint("uq_allocation_org_order_item", "production_allocations", type_="unique")
    op.create_index("uq_allocation_active_order_item", "production_allocations", ["organization_id", "production_order_id", "production_demand_item_id"],
                    unique=True, postgresql_where=sa.text("status = 'active'"))
    op.alter_column("production_order_items", "planned_quantity", type_=sa.Numeric(15, 3), existing_type=sa.Numeric(14, 2), existing_nullable=False)

    # Existing planning orders without lines get them from their ACTIVE allocations.
    orders = bind.execute(sa.text("""SELECT DISTINCT a.production_order_id FROM production_allocations a
        WHERE a.status = 'active' AND NOT EXISTS (SELECT 1 FROM production_order_items i WHERE i.production_order_id = a.production_order_id)""")).scalars().all()
    for order_id in orders:
        rows = bind.execute(sa.text("""SELECT a.id, a.allocated_quantity, a.unit, d.target_spec_json FROM production_allocations a
            JOIN production_demand_items d ON d.id = a.production_demand_item_id WHERE a.production_order_id = :o AND a.status = 'active'"""), dict(o=order_id)).all()
        groups = {}
        for allocation_id, quantity, unit, raw in rows:
            spec = _spec(raw)
            key = json.dumps(spec, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
            group = groups.setdefault(key, dict(spec=spec, unit=unit, quantity=Decimal(0), ids=[]))
            group["quantity"] += Decimal(quantity)
            group["ids"].append(allocation_id)
        ordered = sorted(groups.items(), key=lambda kv: tuple(_part(kv[1]["spec"], n) for n in _SORT_KEYS) + (kv[0],))
        for line_no, (_, group) in enumerate(ordered, 1):
            item_id = uuid4()
            bind.execute(sa.text("""INSERT INTO production_order_items (id, production_order_id, line_no, target_spec_json, planned_quantity, unit, created_at, updated_at)
                VALUES (:id, :o, :n, CAST(:spec AS json), :q, :u, now(), now())"""),
                dict(id=item_id, o=order_id, n=line_no, spec=json.dumps(group["spec"] or None), q=group["quantity"], u=group["unit"]))
            bind.execute(sa.text("UPDATE production_allocations SET production_order_item_id = :i WHERE id = ANY(:ids)"), dict(i=item_id, ids=list(group["ids"])))


def downgrade():
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT count(*) FROM (SELECT 1 FROM production_allocations GROUP BY organization_id, production_order_id, production_demand_item_id HAVING count(*) > 1) d")):
        raise RuntimeError("An order re-allocates a released demand item; archive that history before downgrading")
    if bind.scalar(sa.text("SELECT count(*) FROM production_order_items WHERE planned_quantity <> round(planned_quantity, 2)")):
        raise RuntimeError("Order lines use three decimal places; archive them before downgrading")
    op.alter_column("production_order_items", "planned_quantity", type_=sa.Numeric(14, 2), existing_type=sa.Numeric(15, 3), existing_nullable=False)
    op.drop_index("uq_allocation_active_order_item", table_name="production_allocations")
    op.create_unique_constraint("uq_allocation_org_order_item", "production_allocations", ["organization_id", "production_order_id", "production_demand_item_id"])
    op.drop_index("ix_production_allocations_production_order_item_id", table_name="production_allocations")
    op.drop_constraint("fk_allocation_order_item", "production_allocations", type_="foreignkey")
    op.drop_column("production_allocations", "production_order_item_id")
    # Generated lines are kept: they are valid order items on their own.
