from decimal import Decimal
from types import SimpleNamespace
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from app.core.interfaces.activity_log import get_registered_activity_logger
from app.core.utils import utc_now
from app.production.application.allocation_service import AllocationService, assert_allocation_open, follow_allocations
from app.production.application.order_lines import ACTIVE, rebuild_lines
from app.production.domain.arrangement import arrange
from app.production.domain.compatibility import AllocationError, DemandItemCompatibilityChecker
from app.production.domain.enums import ProductionOrderStatus
from app.production.domain.order_lifecycle import ALLOCATION_OPEN, allocation_open
from app.production.infrastructure.demand_repository import ProductionDemandRepository, PLANNABLE
from app.production.infrastructure.models import ProductionAllocation, ProductionDemand, ProductionDemandItem, ProductionOrder, WorkCenter


class PlanningOrderService:
    def __init__(self, db, tenant, compatibility_checker=None):
        self.db, self.tenant = db, tenant
        self.org_id = tenant.organization_id
        self.checker = compatibility_checker or DemandItemCompatibilityChecker()
        self.allocations = AllocationService()

    def _validated(self, requested):
        """Lock and validate each requested (demand item, quantity); returns (item, demand, quantity)."""
        db, org_id = self.db, self.org_id
        rows = []
        for alloc in sorted(requested, key=lambda a: str(a.production_demand_item_id)):
            item = self.allocations.validate_allocation_with_lock(db, org_id, alloc.production_demand_item_id, alloc.allocated_quantity)
            demand = db.scalar(select(ProductionDemand).where(ProductionDemand.organization_id == org_id, ProductionDemand.id == item.production_demand_id).execution_options(populate_existing=True))
            if demand.status not in PLANNABLE:
                raise AllocationError("DEMAND_NOT_PLANNABLE", 409)
            if not item.product_type or not item.product_type.strip():
                raise AllocationError("PRODUCT_TYPE_REQUIRED")
            rows.append((item, demand, alloc.allocated_quantity))
        # Product type and unit must match; differing specifications become separate lines.
        self.checker.validate_compatibility([item for item, _, _ in rows])
        return rows

    def preview(self, requested):
        """The arrangement an order would get, without writing anything."""
        try:
            ProductionDemandRepository(self.db).lock_organization(self.org_id)
            rows = self._validated(requested)
            entries = [SimpleNamespace(item=item, demand=demand, allocated_quantity=qty, unit=item.unit) for item, demand, qty in rows]
            lines = arrange(entries, spec=lambda e: e.item.target_spec_json)
            return dict(product_type=rows[0][0].product_type, unit=rows[0][0].unit,
                        total_quantity=sum((line.quantity for line in lines), Decimal(0)),
                        lines=[dict(line_no=line.line_no, target_spec_json=line.target_spec_json, planned_quantity=line.quantity, unit=line.unit,
                                    allocations=[dict(production_demand_item_id=e.item.id, production_demand_id=e.demand.id, demand_number=e.demand.demand_number,
                                                      customer_id=e.demand.customer_id, demand_item_line_no=e.item.line_no, allocated_quantity=e.allocated_quantity,
                                                      remaining_quantity=e.item.remaining_quantity) for e in line.allocations]) for line in lines])
        finally:
            # Releases the validation locks; a preview never commits.
            self.db.rollback()

    def create_order_from_planning(self, data):
        db, org_id = self.db, self.org_id
        try:
            # Same first lock as demand edits/reorders, preventing status/item races.
            # Serializes PO numbering and sibling-item status aggregation per tenant.
            ProductionDemandRepository(db).lock_organization(org_id)
            rows = self._validated(data.allocations)
            center = db.scalar(select(WorkCenter).where(WorkCenter.organization_id == org_id, WorkCenter.id == data.work_center_id))
            if center is None:
                raise AllocationError("WORK_CENTER_NOT_FOUND", 404)
            base = rows[0][0]
            year = utc_now().year
            # Organization mutex makes number selection atomic across planning/manual creation.
            numbers = set(db.scalars(select(ProductionOrder.production_order_number).where(ProductionOrder.organization_id == org_id)))
            sequence = len(numbers) + 1
            while (number := f"PO-{year}-{sequence:06d}") in numbers:
                sequence += 1
            order = ProductionOrder(organization_id=org_id, production_order_number=number,
                work_center_id=center.id, product_type=base.product_type, target_spec_json=None,
                planned_quantity=sum((qty for _, _, qty in rows), Decimal(0)), unit=base.unit, priority=data.priority,
                status=ProductionOrderStatus.DRAFT, planned_start_date=data.planned_start_date, planned_end_date=data.planned_end_date,
                notes=data.notes, created_by_user_id=self.tenant.user_id)
            db.add(order)
            db.flush()
            for item, _, qty in rows:
                order.allocations.append(ProductionAllocation(organization_id=org_id, production_order_id=order.id,
                    production_demand_id=item.production_demand_id, production_demand_item_id=item.id,
                    allocated_quantity=qty, unit=item.unit, order_status_at_allocation=ProductionOrderStatus.DRAFT.value,
                    created_by_user_id=self.tenant.user_id))
            db.flush()
            rebuild_lines(db, order)
            for demand_id in sorted({item.production_demand_id for item, _, _ in rows}, key=str):
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

    # ---- Allocations of an open order (draft, released, in progress, on hold) -------------

    def _lock_open_order(self, order_id):
        # Row lock on the order: a status change (complete, cancel) takes the same lock, so the two never interleave.
        order = self.db.scalar(select(ProductionOrder).where(ProductionOrder.organization_id == self.org_id, ProductionOrder.id == order_id)
                               .with_for_update().execution_options(populate_existing=True))
        if order is None:
            raise AllocationError("PRODUCTION_ORDER_NOT_FOUND", 404)
        assert_allocation_open(order)
        return order

    def eligible_orders(self, demand_item_id):
        """Open orders a demand item may join: same organization, product type and unit, specifications compatible with
        the order's current allocations, and the item not already in the order."""
        item = self.db.scalar(select(ProductionDemandItem).join(ProductionDemand).where(
            ProductionDemand.organization_id == self.org_id, ProductionDemandItem.id == demand_item_id))
        if item is None:
            raise AllocationError("DEMAND_ITEM_NOT_FOUND", 404)
        already = select(ProductionAllocation.production_order_id).where(
            ProductionAllocation.organization_id == self.org_id, ProductionAllocation.production_demand_item_id == item.id,
            ProductionAllocation.status == ACTIVE)
        orders = self.db.scalars(select(ProductionOrder).where(
            ProductionOrder.organization_id == self.org_id, ProductionOrder.status.in_([s.value for s in ALLOCATION_OPEN]),
            ProductionOrder.product_type == item.product_type, ProductionOrder.unit == item.unit, ProductionOrder.id.not_in(already))
            .order_by(ProductionOrder.planned_start_date, ProductionOrder.production_order_number, ProductionOrder.id)).all()
        eligible = []
        for order in orders:
            try:
                self.checker.validate_compatibility([*(a.demand_item for a in order.allocations if a.status == ACTIVE), item])
            except AllocationError:
                continue
            eligible.append(order)
        centers = dict(self.db.execute(select(WorkCenter.id, WorkCenter.name).where(
            WorkCenter.organization_id == self.org_id, WorkCenter.id.in_({o.work_center_id for o in eligible}))).all()) if eligible else {}
        return [dict(id=o.id, production_order_number=o.production_order_number, status=ProductionOrderStatus(o.status).value,
                     work_center_name=centers.get(o.work_center_id), product_type=o.product_type, unit=o.unit, planned_quantity=o.planned_quantity,
                     planned_start_date=o.planned_start_date, planned_end_date=o.planned_end_date) for o in eligible]

    def _audit(self, action, order, **details):
        get_registered_activity_logger().log_activity(self.db, self.org_id, action, "production_order", order.id, order.production_order_number,
                                                      actor_id=self.tenant.user_id, details={k: str(v) for k, v in details.items()})

    def _finish(self, order, demand_ids):
        follow_allocations(self.db, self.org_id, order)
        for demand_id in sorted(demand_ids, key=str):
            demand = self.db.scalar(select(ProductionDemand).where(ProductionDemand.organization_id == self.org_id, ProductionDemand.id == demand_id)
                                    .with_for_update().execution_options(populate_existing=True))
            self.allocations.sync_demand_status(self.db, self.org_id, demand)
        self.db.commit()
        self.db.expire_all()
        return self.db.get(ProductionOrder, order.id)

    def add_allocation(self, order_id, data):
        db = self.db
        try:
            ProductionDemandRepository(db).lock_organization(self.org_id)
            order = self._lock_open_order(order_id)
            if any(a.status == ACTIVE and a.production_demand_item_id == data.production_demand_item_id for a in order.allocations):
                raise AllocationError("ALLOCATION_ALREADY_IN_ORDER", 409)
            ((item, _, qty),) = self._validated([data])
            if item.product_type != order.product_type or item.unit != order.unit:
                raise AllocationError("INCOMPATIBLE_DEMAND_ITEMS", reason="DIFFERENT_PRODUCT_TYPE" if item.product_type != order.product_type else "DIFFERENT_UNIT")
            self.checker.validate_compatibility([*(a.demand_item for a in order.allocations if a.status == ACTIVE), item])
            status = ProductionOrderStatus(order.status).value
            before = order.planned_quantity
            order.allocations.append(ProductionAllocation(organization_id=self.org_id, production_order_id=order.id,
                production_demand_id=item.production_demand_id, production_demand_item_id=item.id,
                allocated_quantity=qty, unit=item.unit, order_status_at_allocation=status, created_by_user_id=self.tenant.user_id))
            db.flush()
            self._audit("production_order.allocation_added", order, production_demand_item_id=item.id, allocated_quantity=qty,
                        order_status=status, planned_quantity_before=before)
            return self._finish(order, {item.production_demand_id})
        except (IntegrityError, OperationalError) as exc:
            db.rollback()
            raise AllocationError("ALLOCATION_QUANTITY_CONFLICT", 409) from exc
        except Exception:
            db.rollback()
            raise

    def change_allocation(self, allocation_id, quantity):
        db = self.db
        try:
            ProductionDemandRepository(db).lock_organization(self.org_id)
            allocation = db.scalar(select(ProductionAllocation).where(ProductionAllocation.organization_id == self.org_id, ProductionAllocation.id == allocation_id)
                                   .with_for_update().execution_options(populate_existing=True))
            if allocation is None:
                raise AllocationError("ALLOCATION_NOT_FOUND", 404)
            if allocation.status != ACTIVE:
                raise AllocationError("ALLOCATION_ALREADY_RELEASED", 409)
            order = self._lock_open_order(allocation.production_order_id)
            # Checks the new quantity against what other ACTIVE allocations already reserve.
            self.allocations.validate_allocation(db, self.org_id, allocation.production_demand_item_id, quantity, exclude_allocation_id=allocation.id)
            previous = allocation.allocated_quantity
            allocation.allocated_quantity = quantity
            allocation.updated_at = utc_now()
            db.flush()
            self._audit("production_order.allocation_changed", order, allocation_id=allocation.id, from_quantity=previous, to_quantity=quantity,
                        order_status=ProductionOrderStatus(order.status).value)
            return self._finish(order, {allocation.production_demand_id})
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
    lines = {item.id: item for item in order.items}
    result["allocations"] = []
    for a in order.allocations:
        if a.organization_id != tenant.organization_id:
            continue
        customer = customer_lookup.get_customer_summary(db, a.demand.customer_id, tenant.organization_id)
        line = lines.get(a.production_order_item_id)
        # Released allocations stay listed so the order never loses its demand origin.
        result["allocations"].append(dict(id=a.id, production_demand_id=a.production_demand_id,
            production_demand_item_id=a.production_demand_item_id, demand_number=a.demand.demand_number,
            customer_name=customer.customer_name if customer else None, demand_item_line_no=a.demand_item.line_no,
            product_type=order.product_type, allocated_quantity=a.allocated_quantity, unit=a.unit,
            target_spec_json=a.demand_item.target_spec_json, production_order_item_id=a.production_order_item_id,
            order_line_no=line.line_no if line else None,
            status=a.status, allocated_at=a.created_at, released_at=a.released_at, release_reason=a.release_reason,
            order_status_at_allocation=a.order_status_at_allocation,
            # Added once the order was on the floor (in progress or on hold): screens and reports show it apart.
            added_after_start=a.order_status_at_allocation in (ProductionOrderStatus.IN_PROGRESS.value, ProductionOrderStatus.ON_HOLD.value)))
    result["active_allocated_quantity"] = sum((a["allocated_quantity"] for a in result["allocations"] if a["status"] == "active"), Decimal(0))
    # Specification lines in production order: width -> color -> thickness -> weight.
    result["lines"] = [dict(id=item.id, line_no=item.line_no, target_spec_json=item.target_spec_json, planned_quantity=item.planned_quantity, unit=item.unit,
                            allocation_ids=[a["id"] for a in result["allocations"] if a["production_order_item_id"] == item.id])
                       for item in sorted(order.items, key=lambda i: i.line_no)]
    result["editable"] = order.status == ProductionOrderStatus.DRAFT
    # Allocations can be added, changed and released while the order is open (domain.order_lifecycle.ALLOCATION_OPEN).
    result["allocation_open"] = allocation_open(order.status)
    return result
