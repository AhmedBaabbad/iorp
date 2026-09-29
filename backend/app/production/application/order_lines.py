from copy import deepcopy
from decimal import Decimal
from app.core.utils import utc_now
from app.production.domain.arrangement import arrange, common_spec
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
