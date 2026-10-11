import logging
from datetime import time
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete as sa_delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

_log = logging.getLogger(__name__)

from app.core.pagination import paginate
from app.core.tenancy import TenantContext
from app.core.utils import utc_now
from app.production.api.schemas import (
    ProductionOrderItemCreate,
    ProductionOrderItemUpdate,
    ProductionOrderCreate,
    ProductionOrderUpdate,
    ShiftDefinitionCreate,
    ShiftDefinitionUpdate,
    ShiftDeletionImpact,
    WorkCenterCreate,
    WorkCenterUpdate,
)
from app.production.domain.enums import (
    ProductionOrderPriority,
    ProductionOrderStatus,
    WorkCenterStatus,
)
from app.production.infrastructure.models import (
    DowntimeEvent,
    ProductionOrder,
    ProductionOrderItem,
    ProductionResultEntry,
    ShiftDefinition,
    WasteRecord,
    WorkCenter,
)
from app.production.infrastructure.repositories import (
    ProductionOrderItemRepository,
    ProductionOrderRepository,
    ShiftDefinitionRepository,
    WorkCenterRepository,
)


_TYPE_CODE_PREFIX: dict[str, str] = {
    "extrusion": "EXT",
    "rewinding": "RWD",
    "packing": "PCK",
    "quality_station": "QST",
    "generic": "GEN",
}


class WorkCenterService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.work_centers = WorkCenterRepository(db)

    def _generate_code(self, tenant: TenantContext, center_type: str) -> str:
        prefix = _TYPE_CODE_PREFIX.get(str(center_type), "GEN")
        highest = self.work_centers.get_highest_sequence_for_prefix(tenant.organization_id, prefix)
        return f"WC-{prefix}-{highest + 1:03d}"

    def create_work_center(self, tenant: TenantContext, data: WorkCenterCreate) -> WorkCenter:
        code = self._generate_code(tenant, data.center_type)
        work_center = WorkCenter(
            organization_id=tenant.organization_id,
            code=code,
            **data.model_dump(),
        )

        try:
            self.work_centers.add(work_center)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Work center could not be saved due to invalid or duplicate data.") from exc

        self.db.refresh(work_center)
        return work_center

    def list_work_centers(self, tenant: TenantContext) -> list[WorkCenter]:
        return self.work_centers.list_by_organization(tenant.organization_id)

    def get_work_center(self, tenant: TenantContext, work_center_id: UUID) -> WorkCenter | None:
        return self.work_centers.get_by_id(tenant.organization_id, work_center_id)

    def update_work_center(
        self,
        tenant: TenantContext,
        work_center_id: UUID,
        data: WorkCenterUpdate,
    ) -> WorkCenter | None:
        work_center = self.work_centers.get_by_id(tenant.organization_id, work_center_id)
        if work_center is None:
            return None

        payload = data.model_dump(exclude_unset=True)
        for field, value in payload.items():
            setattr(work_center, field, value)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Work center could not be saved due to invalid or duplicate data.") from exc

        self.db.refresh(work_center)
        return work_center

    def get_work_center_delete_summary(
        self, tenant: TenantContext, work_center_id: UUID
    ) -> dict | None:
        return self.work_centers.get_work_center_delete_summary(
            tenant.organization_id, work_center_id
        )

    def delete_work_center(self, tenant: TenantContext, work_center_id: UUID) -> bool:
        if self.work_centers.get_by_id(tenant.organization_id, work_center_id) is None:
            return False

        try:
            return self._delete_work_center_cascade(tenant, work_center_id)
        except Exception:
            self.db.rollback()
            _log.exception("delete_work_center failed for work_center_id=%s", work_center_id)
            raise

    def _delete_work_center_cascade(self, tenant: TenantContext, work_center_id: UUID) -> bool:
        from app.production.infrastructure.execution_models import ProductionRun
        if self.db.scalar(select(ProductionRun.id).where(
            ProductionRun.organization_id == tenant.organization_id,
            (ProductionRun.work_center_id == work_center_id) | ProductionRun.production_order_id.in_(
                select(ProductionOrder.id).where(ProductionOrder.organization_id == tenant.organization_id, ProductionOrder.work_center_id == work_center_id)
            ),
        ).limit(1)):
            raise ValueError("Cannot delete a work center with production execution history.")
        from app.production.infrastructure.demand_repository import ProductionDemandRepository
        ProductionDemandRepository(self.db).lock_organization(tenant.organization_id)
        from app.production.infrastructure.models import ProductionAllocation
        allocated = self.db.scalar(select(ProductionAllocation.id).join(ProductionOrder).where(ProductionOrder.organization_id == tenant.organization_id, ProductionOrder.work_center_id == work_center_id).limit(1))
        if allocated:
            raise ValueError("Cannot delete a work center with allocated production orders.")
        order_ids = list(self.db.scalars(
            select(ProductionOrder.id).where(ProductionOrder.work_center_id == work_center_id)
        ))
        # An order's final result, its waste and machine downtime are records to keep, never side effects of a delete.
        if order_ids and self.db.scalar(select(ProductionResultEntry.id).where(
                ProductionResultEntry.organization_id == tenant.organization_id, ProductionResultEntry.production_order_id.in_(order_ids)).limit(1)):
            raise ValueError("Cannot delete a work center whose production orders have a recorded final result.")
        at_center = WasteRecord.work_center_id == work_center_id
        if order_ids:
            at_center = at_center | WasteRecord.production_order_id.in_(order_ids)
        if self.db.scalar(select(WasteRecord.id).where(WasteRecord.organization_id == tenant.organization_id, at_center).limit(1)):
            raise ValueError("Cannot delete a work center with recorded waste.")
        stopped = DowntimeEvent.work_center_id == work_center_id
        if order_ids:
            stopped = stopped | DowntimeEvent.production_order_id.in_(order_ids)
        if self.db.scalar(select(DowntimeEvent.id).where(DowntimeEvent.organization_id == tenant.organization_id, stopped).limit(1)):
            raise ValueError("Cannot delete a work center with recorded downtime.")

        # --- Delete owned entities in FK-safe order ---
        if order_ids:
            self.db.execute(
                sa_delete(ProductionOrderItem)
                .where(ProductionOrderItem.production_order_id.in_(order_ids))
            )
        self.db.execute(
            sa_delete(ProductionOrder).where(ProductionOrder.work_center_id == work_center_id)
        )
        self.db.execute(
            sa_delete(WorkCenter).where(
                WorkCenter.id == work_center_id,
                WorkCenter.organization_id == tenant.organization_id,
            )
        )

        self.db.commit()
        return True


def _time_to_minutes(value: time) -> int:
    return (value.hour * 60) + value.minute


def _calculate_shift_duration_hours(start_time: time, end_time: time) -> Decimal:
    start_minutes = _time_to_minutes(start_time)
    end_minutes = _time_to_minutes(end_time)
    duration_minutes = end_minutes - start_minutes
    if duration_minutes <= 0:
        duration_minutes += 24 * 60
    return Decimal(duration_minutes) / Decimal(60)


class ShiftDefinitionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.shift_definitions = ShiftDefinitionRepository(db)

    def create_shift_definition(
        self,
        tenant: TenantContext,
        data: ShiftDefinitionCreate,
    ) -> ShiftDefinition:
        existing = self.shift_definitions.get_by_code(tenant.organization_id, data.code)
        if existing is not None:
            raise ValueError(f"Shift definition code '{data.code}' already exists.")

        shift_definition = ShiftDefinition(
            organization_id=tenant.organization_id,
            crosses_midnight=data.end_time <= data.start_time,
            duration_hours=_calculate_shift_duration_hours(data.start_time, data.end_time),
            **data.model_dump(),
        )

        try:
            self.shift_definitions.add(shift_definition)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Shift definition could not be saved due to invalid or duplicate data.") from exc

        self.db.refresh(shift_definition)
        return shift_definition

    def list_shift_definitions(self, tenant: TenantContext) -> list[ShiftDefinition]:
        return self.shift_definitions.list_by_organization(tenant.organization_id)

    def get_shift_definition(
        self,
        tenant: TenantContext,
        shift_definition_id: UUID,
    ) -> ShiftDefinition | None:
        return self.shift_definitions.get_by_id(tenant.organization_id, shift_definition_id)

    def update_shift_definition(
        self,
        tenant: TenantContext,
        shift_definition_id: UUID,
        data: ShiftDefinitionUpdate,
    ) -> ShiftDefinition | None:
        shift_definition = self.shift_definitions.get_by_id(
            tenant.organization_id,
            shift_definition_id,
        )
        if shift_definition is None:
            return None

        payload = data.model_dump(exclude_unset=True)
        for field, value in payload.items():
            if field != "notes" and value is None:
                raise ValueError(f"{field} cannot be null.")

        new_code = payload.get("code")
        if new_code is not None and new_code != shift_definition.code:
            existing = self.shift_definitions.get_by_code(tenant.organization_id, new_code)
            if existing is not None and existing.id != shift_definition.id:
                raise ValueError(f"Shift definition code '{new_code}' already exists.")

        for field, value in payload.items():
            setattr(shift_definition, field, value)

        if "start_time" in payload or "end_time" in payload:
            shift_definition.crosses_midnight = shift_definition.end_time <= shift_definition.start_time
            shift_definition.duration_hours = _calculate_shift_duration_hours(
                shift_definition.start_time,
                shift_definition.end_time,
            )

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Shift definition could not be saved due to invalid or duplicate data.") from exc

        self.db.refresh(shift_definition)
        return shift_definition

    def get_deletion_impact(
        self,
        tenant: TenantContext,
        shift_definition_id: UUID,
    ) -> ShiftDeletionImpact | None:
        shift_definition = self.shift_definitions.get_by_id(
            tenant.organization_id,
            shift_definition_id,
        )
        if shift_definition is None:
            return None

        from app.production.infrastructure.execution_models import ShiftRoster, ProductionRun
        execution_history = any(self.db.scalar(select(model.id).where(model.organization_id == tenant.organization_id, model.shift_definition_id == shift_definition.id).limit(1)) for model in (ShiftRoster, ProductionRun))
        production_orders = 0
        return ShiftDeletionImpact(
            production_orders=production_orders,
            is_blocked=production_orders > 0 or execution_history,
        )

    def delete_shift_definition(
        self,
        tenant: TenantContext,
        shift_definition_id: UUID,
    ) -> bool:
        shift_definition = self.shift_definitions.get_by_id(
            tenant.organization_id,
            shift_definition_id,
        )
        if shift_definition is None:
            return False

        impact = self.get_deletion_impact(tenant, shift_definition_id)
        if impact and impact.is_blocked:
            raise ValueError(
                "Cannot delete a shift that has roster or production run history.",
            )
        try:
            self.db.delete(shift_definition)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError(
                "Shift could not be deleted because other records still reference it.",
            ) from exc
        return True


class ProductionOrderService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.production_orders = ProductionOrderRepository(db)
        self.work_centers = WorkCenterRepository(db)

    def _generate_production_order_number(self, tenant: TenantContext) -> str:
        year = utc_now().year
        sequence = self.production_orders.count_by_organization(tenant.organization_id) + 1
        while True:
            production_order_number = f"PO-{year}{sequence:04d}"
            existing = self.production_orders.get_by_number(
                tenant.organization_id,
                production_order_number,
            )
            if existing is None:
                return production_order_number
            sequence += 1

    def create_production_order(
        self,
        tenant: TenantContext,
        data: ProductionOrderCreate,
    ) -> ProductionOrder:
        from app.production.infrastructure.demand_repository import ProductionDemandRepository
        ProductionDemandRepository(self.db).lock_organization(tenant.organization_id)
        work_center = self.work_centers.get_by_id(tenant.organization_id, data.work_center_id)
        if work_center is None:
            raise ValueError("Work center must belong to the current organization.")

        production_order_number = data.production_order_number
        if production_order_number is None:
            production_order_number = self._generate_production_order_number(tenant)
        else:
            existing = self.production_orders.get_by_number(
                tenant.organization_id,
                production_order_number,
            )
            if existing is not None:
                raise ValueError(f"Production order number '{production_order_number}' already exists.")

        payload = data.model_dump(exclude={"production_order_number"})
        if data.planned_end_date < data.planned_start_date:
            raise ValueError("Invalid date range.")
        production_order = ProductionOrder(
            organization_id=tenant.organization_id,
            production_order_number=production_order_number,
            status=ProductionOrderStatus.DRAFT,
            created_by_user_id=tenant.user_id,
            **payload,
        )

        try:
            self.production_orders.add(production_order)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Production order could not be saved due to invalid or duplicate data.") from exc

        self.db.refresh(production_order)
        return production_order

    def list_production_orders(
        self,
        tenant: TenantContext,
        params,
        status: ProductionOrderStatus | None = None,
        work_center_id: UUID | None = None,
        priority: ProductionOrderPriority | None = None,
        search: str | None = None,
    ) -> tuple[list[ProductionOrder], int]:
        """One page of the organization's orders and the total matching the filters (ARCH-PAGE-001)."""
        return paginate(self.db, self.production_orders.list_statement(
            tenant.organization_id, status=status, work_center_id=work_center_id, priority=priority, search=search), params)

    def lookup_production_orders(self, tenant: TenantContext, search: str = "", statuses=(), ids=(), limit: int = 20) -> list[ProductionOrder]:
        """Orders for a picker: searched on the server (number or product), at most `limit`; or the given ids."""
        statement = self.production_orders.list_statement(tenant.organization_id, search=search or None)
        if statuses:
            statement = statement.where(ProductionOrder.status.in_(list(statuses)))
        if ids:
            statement = statement.where(ProductionOrder.id.in_(list(ids)))
        return list(self.db.scalars(statement.limit(limit)))

    def get_production_order(
        self,
        tenant: TenantContext,
        production_order_id: UUID,
    ) -> ProductionOrder | None:
        return self.production_orders.get_by_id(tenant.organization_id, production_order_id)

    def update_production_order(
        self,
        tenant: TenantContext,
        production_order_id: UUID,
        data: ProductionOrderUpdate,
    ) -> ProductionOrder | None:
        production_order = self.production_orders.get_by_id_for_update(
            tenant.organization_id,
            production_order_id,
        )
        if production_order is None:
            return None

        payload = data.model_dump(exclude_unset=True)
        if production_order.status in (ProductionOrderStatus.CLOSED, ProductionOrderStatus.CANCELLED):
            raise ValueError("A closed or cancelled production order cannot be edited.")
        if production_order.allocations:
            protected = {"planned_quantity", "unit", "product_type", "target_spec_json"}
            if protected.intersection(payload):
                raise ValueError("Allocated order quantity and product snapshot are read-only.")
        if payload.get("planned_end_date", production_order.planned_end_date) < payload.get("planned_start_date", production_order.planned_start_date):
            raise ValueError("Invalid date range.")
        if "work_center_id" in payload and payload["work_center_id"] is None:
            raise ValueError("work_center_id cannot be set to null.")

        new_work_center_id = payload.get("work_center_id")
        if new_work_center_id is not None:
            work_center = self.work_centers.get_by_id(tenant.organization_id, new_work_center_id)
            if work_center is None:
                raise ValueError("Work center must belong to the current organization.")

        new_number = payload.get("production_order_number")
        if new_number is not None and new_number != production_order.production_order_number:
            existing = self.production_orders.get_by_number(tenant.organization_id, new_number)
            if existing is not None and existing.id != production_order.id:
                raise ValueError(f"Production order number '{new_number}' already exists.")

        for field, value in payload.items():
            setattr(production_order, field, value)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Production order could not be saved due to invalid or duplicate data.") from exc

        self.db.refresh(production_order)
        return production_order


class ProductionOrderItemService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.production_orders = ProductionOrderRepository(db)
        self.items = ProductionOrderItemRepository(db)

    def _get_parent_order(self, tenant: TenantContext, production_order_id: UUID) -> ProductionOrder | None:
        return self.production_orders.get_by_id(tenant.organization_id, production_order_id)

    def _get_writable_parent(self, tenant: TenantContext, production_order_id: UUID) -> ProductionOrder | None:
        production_order = self._get_parent_order(tenant, production_order_id)
        if production_order is not None and production_order.allocations:
            # Planning orders derive their lines from allocations; edit the allocations instead.
            raise ValueError("Lines of a planned production order follow its allocations; change the allocations instead.")
        return production_order

    def create_item(
        self,
        tenant: TenantContext,
        production_order_id: UUID,
        data: ProductionOrderItemCreate,
    ) -> ProductionOrderItem | None:
        production_order = self._get_writable_parent(tenant, production_order_id)
        if production_order is None:
            return None
        if production_order.status in (ProductionOrderStatus.CANCELLED, ProductionOrderStatus.CLOSED):
            raise ValueError("Cannot add items to a cancelled or closed production order.")

        line_no = data.line_no or self.items.next_line_no(tenant.organization_id, production_order.id)
        existing = self.items.get_by_line_no(tenant.organization_id, production_order.id, line_no)
        if existing is not None:
            raise ValueError(f"Production order item line_no '{line_no}' already exists.")

        payload = data.model_dump(exclude={"line_no"})
        item = ProductionOrderItem(
            production_order_id=production_order.id,
            line_no=line_no,
            **payload,
        )

        try:
            self.items.add(item)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Production order item could not be saved due to invalid or duplicate data.") from exc

        self.db.refresh(item)
        return item

    def list_items(
        self,
        tenant: TenantContext,
        production_order_id: UUID,
    ) -> list[ProductionOrderItem] | None:
        production_order = self._get_parent_order(tenant, production_order_id)
        if production_order is None:
            return None
        return self.items.list_by_order(tenant.organization_id, production_order.id)

    def get_item(
        self,
        tenant: TenantContext,
        production_order_id: UUID,
        item_id: UUID,
    ) -> ProductionOrderItem | None:
        production_order = self._get_parent_order(tenant, production_order_id)
        if production_order is None:
            return None
        return self.items.get_by_id(tenant.organization_id, production_order.id, item_id)

    def update_item(
        self,
        tenant: TenantContext,
        production_order_id: UUID,
        item_id: UUID,
        data: ProductionOrderItemUpdate,
    ) -> ProductionOrderItem | None:
        production_order = self._get_writable_parent(tenant, production_order_id)
        if production_order is None:
            return None
        if production_order.status in (ProductionOrderStatus.COMPLETED, ProductionOrderStatus.CLOSED):
            raise ValueError("Cannot update items for a completed or closed production order.")

        item = self.items.get_by_id(tenant.organization_id, production_order.id, item_id)
        if item is None:
            return None

        payload = data.model_dump(exclude_unset=True)
        new_line_no = payload.get("line_no")
        if new_line_no is not None and new_line_no != item.line_no:
            existing = self.items.get_by_line_no(tenant.organization_id, production_order.id, new_line_no)
            if existing is not None and existing.id != item.id:
                raise ValueError(f"Production order item line_no '{new_line_no}' already exists.")

        for field, value in payload.items():
            setattr(item, field, value)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Production order item could not be saved due to invalid or duplicate data.") from exc

        self.db.refresh(item)
        return item

    def delete_item(
        self,
        tenant: TenantContext,
        production_order_id: UUID,
        item_id: UUID,
    ) -> bool | None:
        production_order = self._get_writable_parent(tenant, production_order_id)
        if production_order is None:
            return None
        if production_order.status in {
            ProductionOrderStatus.IN_PROGRESS,
            ProductionOrderStatus.COMPLETED,
        }:
            raise ValueError("Cannot delete items for an in-progress or completed production order.")

        item = self.items.get_by_id(tenant.organization_id, production_order.id, item_id)
        if item is None:
            return None

        self.items.delete(item)
        self.db.commit()
        return True


from app.core.interfaces.activity_log import instrument_activity_methods

instrument_activity_methods(WorkCenterService, {"create_work_center": ("work_center.created", "work_center"), "update_work_center": ("work_center.updated", "work_center"), "delete_work_center": ("work_center.deleted", "work_center")})
instrument_activity_methods(ShiftDefinitionService, {"create_shift_definition": ("shift.created", "shift"), "update_shift_definition": ("shift.updated", "shift"), "delete_shift_definition": ("shift.deleted", "shift")})
instrument_activity_methods(ProductionOrderService, {"create_production_order": ("production_order.created", "production_order"), "update_production_order": ("production_order.updated", "production_order")})
instrument_activity_methods(ProductionOrderItemService, {"create_item": ("production_order_item.created", "production_order_item"), "update_item": ("production_order_item.updated", "production_order_item"), "delete_item": ("production_order_item.deleted", "production_order_item")})
