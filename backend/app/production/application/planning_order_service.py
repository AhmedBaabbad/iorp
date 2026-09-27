from copy import deepcopy
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from app.core.utils import utc_now
from app.production.application.allocation_service import AllocationService
from app.production.domain.compatibility import AllocationError, DemandItemCompatibilityChecker
from app.production.domain.enums import ProductionOrderStatus
from app.production.infrastructure.demand_repository import ProductionDemandRepository, PLANNABLE
from app.production.infrastructure.models import ProductionAllocation, ProductionDemand, ProductionOrder, WorkCenter


class PlanningOrderService:
    def __init__(self, db, tenant, compatibility_checker=None):
        self.db, self.tenant = db, tenant
        self.checker = compatibility_checker or DemandItemCompatibilityChecker()
        self.allocations = AllocationService()

    def create_order_from_planning(self, data):
        db, org_id = self.db, self.tenant.organization_id
        try:
            # Same first lock as demand edits/reorders, preventing status/item races.
            # Serializes PO numbering and sibling-item status aggregation per tenant.
            ProductionDemandRepository(db).lock_organization(org_id)
            items = []
            for alloc in sorted(data.allocations, key=lambda a: str(a.production_demand_item_id)):
                item = self.allocations.validate_allocation_with_lock(db, org_id, alloc.production_demand_item_id, alloc.allocated_quantity)
                demand = db.scalar(select(ProductionDemand).where(ProductionDemand.organization_id == org_id, ProductionDemand.id == item.production_demand_id).execution_options(populate_existing=True))
                if demand.status not in PLANNABLE:
                    raise AllocationError("DEMAND_NOT_PLANNABLE", 409)
                if not item.product_type or not item.product_type.strip():
                    raise AllocationError("PRODUCT_TYPE_REQUIRED")
                items.append((item, alloc.allocated_quantity))
            self.checker.validate_compatibility([item for item, _ in items])
            center = db.scalar(select(WorkCenter).where(WorkCenter.organization_id == org_id, WorkCenter.id == data.work_center_id))
            if center is None:
                raise AllocationError("WORK_CENTER_NOT_FOUND", 404)
            total = sum((qty for _, qty in items), Decimal(0))
            base = items[0][0]
            year = utc_now().year
            # Organization mutex makes number selection atomic across planning/manual creation.
            numbers = set(db.scalars(select(ProductionOrder.production_order_number).where(ProductionOrder.organization_id == org_id)))
            sequence = len(numbers) + 1
            while (number := f"PO-{year}-{sequence:06d}") in numbers:
                sequence += 1
            order = ProductionOrder(organization_id=org_id, production_order_number=number,
                work_center_id=center.id, product_type=base.product_type, target_spec_json=deepcopy(base.target_spec_json),
                planned_quantity=total, unit=base.unit, priority=data.priority, status=ProductionOrderStatus.DRAFT,
                planned_start_date=data.planned_start_date, planned_end_date=data.planned_end_date,
                notes=data.notes, created_by_user_id=self.tenant.user_id)
            db.add(order)
            db.flush()
            for item, qty in items:
                db.add(ProductionAllocation(organization_id=org_id, production_order_id=order.id,
                    production_demand_id=item.production_demand_id, production_demand_item_id=item.id,
                    allocated_quantity=qty, unit=item.unit, created_by_user_id=self.tenant.user_id))
            db.flush()
            for demand_id in sorted({item.production_demand_id for item, _ in items}, key=str):
                self.allocations.sync_demand_status(db, org_id, db.get(ProductionDemand, demand_id))
            db.commit()
            db.expire_all()
            return db.get(ProductionOrder, order.id)
        except (IntegrityError, OperationalError) as exc:
            db.rollback()
            raise AllocationError("ALLOCATION_QUANTITY_CONFLICT", 409) from exc
        except Exception:
            db.rollback()
            raise


def order_response(order, db, tenant, customer_lookup):
    from app.production.api.schemas import ProductionOrderRead
    result = ProductionOrderRead.model_validate(order).model_dump()
    center = db.scalar(select(WorkCenter).where(WorkCenter.id == order.work_center_id, WorkCenter.organization_id == tenant.organization_id))
    result["work_center"] = {"id": center.id, "name": center.name} if center else None
    result["allocations"] = []
    for a in order.allocations:
        if a.organization_id != tenant.organization_id:
            continue
        customer = customer_lookup.get_customer_summary(db, a.demand.customer_id, tenant.organization_id)
        # Released allocations stay listed so the order never loses its demand origin.
        result["allocations"].append(dict(id=a.id, production_demand_id=a.production_demand_id,
            production_demand_item_id=a.production_demand_item_id, demand_number=a.demand.demand_number,
            customer_name=customer.customer_name if customer else None, demand_item_line_no=a.demand_item.line_no,
            product_type=order.product_type, allocated_quantity=a.allocated_quantity, unit=a.unit,
            status=a.status, allocated_at=a.created_at, released_at=a.released_at, release_reason=a.release_reason))
    result["active_allocated_quantity"] = sum((a["allocated_quantity"] for a in result["allocations"] if a["status"] == "active"), Decimal(0))
    return result
