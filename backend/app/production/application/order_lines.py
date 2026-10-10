from collections import defaultdict
from copy import deepcopy
from decimal import Decimal
from app.core.utils import utc_now
from app.production.domain.arrangement import arrange, common_spec, sort_key, spec_identity
from app.production.infrastructure.models import ProductionOrderItem

ACTIVE = "active"


def rebuild_lines(db, order):
    """Regenerate the order's specification lines and header totals from its ACTIVE allocations.

    One line per distinct specification, ordered width -> color -> thickness -> weight.
    Only called while no execution exists, so lines carry no execution history yet.
    """
    active = [a for a in order.allocations if a.status == ACTIVE]
    for allocation in order.allocations:
        allocation.production_order_item_id = None
    order.items.clear()
    db.flush()
    lines = arrange(active, spec=lambda a: a.demand_item.target_spec_json)
    for line in lines:
        item = ProductionOrderItem(production_order_id=order.id, line_no=line.line_no, target_spec_json=deepcopy(line.target_spec_json),
                                   planned_quantity=line.quantity, unit=line.unit)
        order.items.append(item)
        db.flush()
        for allocation in line.allocations:
            allocation.production_order_item_id = item.id
    order.planned_quantity = sum((line.quantity for line in lines), Decimal(0))
    order.target_spec_json = common_spec([line.target_spec_json for line in lines])
    order.updated_at = utc_now()
    db.flush()
    return lines


def adjust_lines(db, order):
    """Make the lines of an order already on the floor follow its ACTIVE allocations, without removing or renumbering a line.

    Runs, waste, results and quality records may point at the lines, so nothing is rebuilt: an allocation joins the line
    of its specification (whose planned quantity grows), a new specification becomes a new line at the end, and a line
    whose allocations are all released stays in place at zero. A line's quantity is a sum of positive allocations, so it
    never goes below zero.
    """
    active = [a for a in order.allocations if a.status == ACTIVE]
    lines = {spec_identity(item.target_spec_json): item for item in order.items}
    totals = defaultdict(lambda: Decimal(0))
    last = max((item.line_no for item in order.items), default=0)
    for allocation in sorted(active, key=lambda a: sort_key(a.demand_item.target_spec_json)):
        spec = allocation.demand_item.target_spec_json
        key = spec_identity(spec)
        item = lines.get(key)
        if item is None:
            last += 1
            item = lines[key] = ProductionOrderItem(production_order_id=order.id, line_no=last, target_spec_json=deepcopy(spec),
                                                    planned_quantity=Decimal(0), unit=allocation.unit)
            order.items.append(item)
            db.flush()
        allocation.production_order_item_id = item.id
        totals[key] += allocation.allocated_quantity
    for key, item in lines.items():
        item.planned_quantity = totals[key]
    order.planned_quantity = sum(totals.values(), Decimal(0))
    order.target_spec_json = common_spec([item.target_spec_json for item in order.items if item.planned_quantity > 0])
    order.updated_at = utc_now()
    db.flush()
    return sorted(order.items, key=lambda i: i.line_no)
