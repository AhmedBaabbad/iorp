"""Production declares its history visibility; core never imports production models."""
from sqlalchemy import select
from app.core.interfaces.record_history import register_record_history
from app.core.interfaces.record_history import record_event, diff_fields, safe
from app.production.domain.permissions import DEMANDS_READ, ORDERS_READ
from app.production.infrastructure.models import ProductionDemand, ProductionOrder


def register():
    def visible(model):
        def check(db, tenant, entity_id):
            return db.scalar(select(model.id).where(model.id == entity_id, model.organization_id == tenant.organization_id)) is not None
        return check
    register_record_history('production_demand', DEMANDS_READ, visible(ProductionDemand))
    register_record_history('production_order', ORDERS_READ, visible(ProductionOrder))


def order_lines(order):
    return {'lines': [dict(line_no=i.line_no, target_spec_json=i.target_spec_json,
                           planned_quantity=safe(i.planned_quantity), unit=i.unit) for i in sorted(order.items, key=lambda i: i.line_no)]}


def allocation_event(db, tenant, allocation, action, before, after, reason=None):
    order, demand = allocation.production_order, allocation.demand
    related = dict(allocation_id=allocation.id, item_id=allocation.production_demand_item_id,
                   production_order_id=order.id, production_order_number=order.production_order_number,
                   production_demand_id=demand.id, demand_number=demand.demand_number,
                   order_status=order.status, product_type=allocation.product_type_snapshot,
                   allocated_quantity=allocation.allocated_quantity, unit=allocation.unit)
    changes = diff_fields(before, after, sorted(set(before) | set(after)))
    for kind, row, name in (('production_order', order, order.production_order_number), ('production_demand', demand, demand.demand_number)):
        record_event(db, tenant.organization_id, kind, row.id, name, action, tenant, changes, reason, related)
