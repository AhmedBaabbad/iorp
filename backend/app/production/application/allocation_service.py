from decimal import Decimal
from sqlalchemy import func, or_, select
from app.core.interfaces.activity_log import get_registered_activity_logger
from app.core.utils import utc_now
from app.production.application.order_lines import rebuild_lines
from app.production.domain.compatibility import AllocationError
from app.production.domain.enums import ProductionAllocationStatus, ProductionOrderStatus
from app.production.infrastructure.demand_repository import ProductionDemandRepository
from app.production.infrastructure.execution_models import ProductionRun
from app.production.infrastructure.models import (
    DowntimeEvent, ProductionAllocation, ProductionDemand, ProductionDemandItem, ProductionOrder,
    ProductionOutput, WasteRecord,
)

ACTIVE = ProductionAllocationStatus.ACTIVE.value
RELEASED = ProductionAllocationStatus.RELEASED.value
# Demand states that are derived from allocations; draft and cancelled are never overridden.
ALLOCATION_DERIVED = ("ready_for_planning", "partially_planned", "planned")


class OverAllocationError(AllocationError):
    def __init__(self, item_id, required, allocated, requested):
        super().__init__("ALLOCATION_QUANTITY_CONFLICT", 409, reason="OVER_ALLOCATION", demand_item_id=str(item_id),
                         required_quantity=str(required), already_allocated=str(allocated),
                         requested_quantity=str(requested), would_exceed_by=str(allocated + requested - required))


class AllocationService:
    def _sum_allocations(self, db, org_id, demand_item_id, exclude_allocation_id=None):
        # Only ACTIVE allocations reserve demand quantity.
        query = select(func.coalesce(func.sum(ProductionAllocation.allocated_quantity), 0)).where(
            ProductionAllocation.organization_id == org_id,
            ProductionAllocation.production_demand_item_id == demand_item_id,
            ProductionAllocation.status == ACTIVE)
        if exclude_allocation_id is not None:
            # A quantity change replaces the allocation's own reservation.
            query = query.where(ProductionAllocation.id != exclude_allocation_id)
        return db.scalar(query) or Decimal(0)

    def validate_allocation(self, db, org_id, demand_item_id, requested_quantity, exclude_allocation_id=None):
        # The caller holds the organization mutex. Lock the item as well, and keep
        # both locks through insertion and commit. Parent join enforces tenant scope.
        item = db.scalar(select(ProductionDemandItem).join(ProductionDemand).where(
            ProductionDemand.organization_id == org_id, ProductionDemandItem.id == demand_item_id
        ).with_for_update(of=ProductionDemandItem).execution_options(populate_existing=True))
        if item is None:
            raise AllocationError("DEMAND_ITEM_NOT_FOUND", 404)
        if not requested_quantity.is_finite() or requested_quantity <= 0:
            raise AllocationError("INVALID_ALLOCATION_QUANTITY")
        allocated = self._sum_allocations(db, org_id, item.id, exclude_allocation_id)
        if allocated + requested_quantity > item.required_quantity:
            raise OverAllocationError(item.id, item.required_quantity, allocated, requested_quantity)
        return item

    validate_allocation_with_lock = validate_allocation

    def sync_demand_status(self, db, org_id, demand):
        """Derive the header status from ACTIVE allocations of every item."""
        if demand.status not in ALLOCATION_DERIVED:
            return demand.status
        items = list(db.scalars(select(ProductionDemandItem).where(ProductionDemandItem.production_demand_id == demand.id)))
        if not items:
            return demand.status
        allocated = [self._sum_allocations(db, org_id, item.id) for item in items]
        if all(a == 0 for a in allocated):
            status = "ready_for_planning"
        elif all(a >= item.required_quantity for a, item in zip(allocated, items)):
            status = "planned"
        else:
            status = "partially_planned"
        if status != demand.status:
            demand.status = status
            if status == "planned":
                demand.planning_sequence = None
            demand.updated_at = utc_now()
        return status


class AllocationLifecycleService:
    """Release of allocations and pre-execution cancellation of production orders."""

    def __init__(self, db, tenant):
        self.db, self.tenant = db, tenant
        self.org_id = tenant.organization_id
        self.allocations = AllocationService()

    def execution_evidence(self, order_id):
        """Names of execution records that make an order's allocations historical."""
        started_run = select(ProductionRun.id).where(
            ProductionRun.organization_id == self.org_id, ProductionRun.production_order_id == order_id,
            or_(ProductionRun.started_at.is_not(None), ProductionRun.status.not_in(("planned", "cancelled"))))
        checks = {"production_runs": started_run}
        for name, model in (("production_outputs", ProductionOutput), ("downtime_events", DowntimeEvent), ("waste_records", WasteRecord)):
            checks[name] = select(model.id).where(model.organization_id == self.org_id, model.production_order_id == order_id)
        return [name for name, query in checks.items() if self.db.scalar(query.limit(1)) is not None]

    def assert_releasable(self, order):
        status = ProductionOrderStatus(order.status)
        if status in (ProductionOrderStatus.COMPLETED, ProductionOrderStatus.CLOSED):
            raise AllocationError("ORDER_COMPLETED", 409, order_status=status.value)
        if status in (ProductionOrderStatus.IN_PROGRESS, ProductionOrderStatus.ON_HOLD):
            raise AllocationError("ORDER_EXECUTION_STARTED", 409, order_status=status.value)
        evidence = self.execution_evidence(order.id)
        if evidence:
            # Status alone is not trusted: recorded execution makes the allocation history.
            raise AllocationError("ORDER_EXECUTION_STARTED", 409, order_status=status.value, execution_records=evidence)

    def _lock_order(self, order_id):
        order = self.db.scalar(select(ProductionOrder).where(ProductionOrder.organization_id == self.org_id, ProductionOrder.id == order_id).with_for_update().execution_options(populate_existing=True))
        if order is None:
            raise AllocationError("PRODUCTION_ORDER_NOT_FOUND", 404)
        return order

    def _active_allocations(self, order_id):
        return list(self.db.scalars(select(ProductionAllocation).where(
            ProductionAllocation.organization_id == self.org_id, ProductionAllocation.production_order_id == order_id,
            ProductionAllocation.status == ACTIVE).order_by(ProductionAllocation.production_demand_item_id).with_for_update()))

    def _release(self, allocation, reason, now):
        allocation.status = RELEASED
        allocation.released_at = now
        allocation.released_by_user_id = self.tenant.user_id
        allocation.release_reason = reason
        allocation.updated_at = now

    def _sync_demands(self, demand_ids):
        for demand_id in sorted(demand_ids, key=str):
            demand = self.db.scalar(select(ProductionDemand).where(ProductionDemand.organization_id == self.org_id, ProductionDemand.id == demand_id).with_for_update().execution_options(populate_existing=True))
            self.allocations.sync_demand_status(self.db, self.org_id, demand)

    def _audit(self, action, entity_type, entity_id, name, **details):
        get_registered_activity_logger().log_activity(
            self.db, self.org_id, action, entity_type, entity_id, name, actor_id=self.tenant.user_id,
            details={key: str(value) for key, value in details.items()})

    def release_allocation(self, allocation_id, reason):
        db = self.db
        try:
            # Same first lock as allocation creation, so release and allocate never interleave.
            ProductionDemandRepository(db).lock_organization(self.org_id)
            allocation = db.scalar(select(ProductionAllocation).where(ProductionAllocation.organization_id == self.org_id, ProductionAllocation.id == allocation_id).with_for_update().execution_options(populate_existing=True))
            if allocation is None:
                raise AllocationError("ALLOCATION_NOT_FOUND", 404)
            if allocation.status != ACTIVE:
                raise AllocationError("ALLOCATION_ALREADY_RELEASED", 409)
            order = self._lock_order(allocation.production_order_id)
            self.assert_releasable(order)
            cancelled = order.status == ProductionOrderStatus.CANCELLED
            remaining = [a for a in self._active_allocations(order.id) if a.id != allocation.id]
            if not cancelled and not remaining:
                # An open order must keep at least one demand source; cancel the order instead.
                raise AllocationError("LAST_ACTIVE_ALLOCATION", 409)
            now = utc_now()
            self._release(allocation, reason, now)
            db.flush()
            if not cancelled:
                # Lines and planned quantity of an open order always follow its ACTIVE allocations.
                db.refresh(order, ["allocations"])
                rebuild_lines(db, order)
            self._sync_demands({allocation.production_demand_id})
            self._audit("production_allocation.released", "production_allocation", allocation.id, order.production_order_number,
                        production_order_id=order.id, production_demand_item_id=allocation.production_demand_item_id,
                        allocated_quantity=allocation.allocated_quantity, reason=reason)
            db.commit()
            db.expire_all()
            return db.get(ProductionAllocation, allocation.id)
        except Exception:
            db.rollback()
            raise

    def release_all_for_cancellation(self, order, reason):
        """Release every ACTIVE allocation of a locked order being cancelled; the caller changes the status.

        Order status is owned by OrderStatusService; this only returns the quantities to their demands.
        """
        self.assert_releasable(order)
        now = utc_now()
        released = self._active_allocations(order.id)
        for allocation in released:
            self._release(allocation, reason, now)
        self.db.flush()
        self._sync_demands({a.production_demand_id for a in released})
        return released

def demand_quantity_summary(demand):
    items = [dict(id=item.id, line_no=item.line_no, unit=item.unit, required_quantity=item.required_quantity,
                  active_allocated_quantity=item.active_allocated_quantity, released_allocated_quantity=item.released_allocated_quantity,
                  remaining_quantity=item.remaining_quantity, planning_state=item.planning_state) for item in demand.items]
    return dict(id=demand.id, demand_number=demand.demand_number, status=demand.status, items=items,
                total_required=sum((i["required_quantity"] for i in items), Decimal(0)),
                total_active_allocated=sum((i["active_allocated_quantity"] for i in items), Decimal(0)),
                total_released_allocated=sum((i["released_allocated_quantity"] for i in items), Decimal(0)),
                total_remaining=sum((i["remaining_quantity"] for i in items), Decimal(0)))
