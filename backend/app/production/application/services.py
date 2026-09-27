import logging
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete as sa_delete, select, update as sa_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

_log = logging.getLogger(__name__)

from app.core.tenancy import TenantContext
from app.core.utils import utc_now
from app.production.api.schemas import (
    DowntimeEventCreate,
    DowntimeEventUpdate,
    ProductionOutputCreate,
    ProductionOutputUpdate,
    ProductionOrderItemCreate,
    ProductionOrderItemUpdate,
    ProductionOrderCreate,
    ProductionOrderUpdate,
    ShiftDefinitionCreate,
    ShiftDefinitionUpdate,
    ShiftDeletionImpact,
    ShiftReportCreate,
    ShiftReportUpdate,
    WasteRecordCreate,
    WasteRecordUpdate,
    WorkCenterCreate,
    WorkCenterUpdate,
)
from app.production.domain.enums import (
    DowntimeCategory,
    DowntimeStatus,
    ProductionOutputStatus,
    ProductionOrderPriority,
    ProductionOrderStatus,
    ShiftReportStatus,
    WasteCategory,
    WorkCenterStatus,
)
from app.production.infrastructure.models import (
    DowntimeEvent,
    ProductionOutput,
    ProductionOrder,
    ProductionOrderItem,
    ShiftDefinition,
    ShiftReport,
    WasteRecord,
    WorkCenter,
)
from app.production.infrastructure.repositories import (
    DowntimeEventRepository,
    ProductionOutputRepository,
    ProductionOrderItemRepository,
    ProductionOrderRepository,
    ShiftDefinitionRepository,
    ShiftReportRepository,
    WasteRecordRepository,
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
        shift_report_ids = list(self.db.scalars(
            select(ShiftReport.id).where(ShiftReport.work_center_id == work_center_id)
        ))

        # --- Nullable FK nullification on records from OTHER work centers ---
        if order_ids:
            # ShiftReports and DowntimeEvents from other WCs referencing our orders
            self.db.execute(
                sa_update(ShiftReport)
                .where(
                    ShiftReport.production_order_id.in_(order_ids),
                    ShiftReport.work_center_id != work_center_id,
                )
                .values(production_order_id=None)
            )
            self.db.execute(
                sa_update(DowntimeEvent)
                .where(
                    DowntimeEvent.production_order_id.in_(order_ids),
                    DowntimeEvent.work_center_id != work_center_id,
                )
                .values(production_order_id=None)
            )
        if shift_report_ids:
            # ProductionOutputs, DowntimeEvents, WasteRecords from other WCs referencing our ShiftReports
            self.db.execute(
                sa_update(ProductionOutput)
                .where(
                    ProductionOutput.shift_report_id.in_(shift_report_ids),
                    ProductionOutput.work_center_id != work_center_id,
                )
                .values(shift_report_id=None)
            )
            self.db.execute(
                sa_update(DowntimeEvent)
                .where(
                    DowntimeEvent.shift_report_id.in_(shift_report_ids),
                    DowntimeEvent.work_center_id != work_center_id,
                )
                .values(shift_report_id=None)
            )
            self.db.execute(
                sa_update(WasteRecord)
                .where(
                    WasteRecord.shift_report_id.in_(shift_report_ids),
                    WasteRecord.work_center_id != work_center_id,
                )
                .values(shift_report_id=None)
            )
        # --- NOT NULL FK cleanup: delete rows from other WCs that cannot be nullified ---
        if order_ids:
            # ProductionOutputs and WasteRecords from other WCs referencing our orders
            self.db.execute(
                sa_delete(ProductionOutput)
                .where(
                    ProductionOutput.production_order_id.in_(order_ids),
                    ProductionOutput.work_center_id != work_center_id,
                )
            )
            self.db.execute(
                sa_delete(WasteRecord)
                .where(
                    WasteRecord.production_order_id.in_(order_ids),
                    WasteRecord.work_center_id != work_center_id,
                )
            )
        # --- Delete owned entities in FK-safe order ---
        self.db.execute(
            sa_delete(ProductionOutput).where(ProductionOutput.work_center_id == work_center_id)
        )
        self.db.execute(
            sa_delete(WasteRecord).where(WasteRecord.work_center_id == work_center_id)
        )
        self.db.execute(
            sa_delete(DowntimeEvent).where(DowntimeEvent.work_center_id == work_center_id)
        )
        self.db.execute(
            sa_delete(ShiftReport).where(ShiftReport.work_center_id == work_center_id)
        )
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
        self.shift_reports = ShiftReportRepository(db)

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
        shift_reports = self.shift_reports.count_by_shift_definition(shift_definition.id)
        production_orders = 0
        return ShiftDeletionImpact(
            shift_reports=shift_reports,
            production_orders=production_orders,
            is_blocked=shift_reports > 0 or production_orders > 0 or execution_history,
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
            if impact.shift_reports:
                raise ValueError(
                    "Cannot delete a shift that has shift reports. Remove the shift reports first.",
                )
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
        status: ProductionOrderStatus | None = None,
        work_center_id: UUID | None = None,
        priority: ProductionOrderPriority | None = None,
    ) -> list[ProductionOrder]:
        return self.production_orders.list_by_organization(
            tenant.organization_id,
            status=status,
            work_center_id=work_center_id,
            priority=priority,
        )

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
        if "status" in payload and payload["status"] != production_order.status:
            if payload["status"] == ProductionOrderStatus.CANCELLED:
                # Cancellation must release allocations; only the cancel operation does that atomically.
                raise ValueError("Use the cancel action to cancel a production order.")
            if production_order.status == ProductionOrderStatus.CANCELLED:
                raise ValueError("A cancelled production order cannot be reopened.")
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

    def create_item(
        self,
        tenant: TenantContext,
        production_order_id: UUID,
        data: ProductionOrderItemCreate,
    ) -> ProductionOrderItem | None:
        production_order = self._get_parent_order(tenant, production_order_id)
        if production_order is None:
            return None
        if production_order.status == ProductionOrderStatus.CANCELLED:
            raise ValueError("Cannot add items to a cancelled production order.")

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
        production_order = self._get_parent_order(tenant, production_order_id)
        if production_order is None:
            return None
        if production_order.status == ProductionOrderStatus.COMPLETED:
            raise ValueError("Cannot update items for a completed production order.")

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
        production_order = self._get_parent_order(tenant, production_order_id)
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


class ShiftReportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.production_orders = ProductionOrderRepository(db)
        self.shift_definitions = ShiftDefinitionRepository(db)
        self.shift_reports = ShiftReportRepository(db)
        self.work_centers = WorkCenterRepository(db)

    def _validate_execution_window(
        self,
        shift_started_at: datetime | None,
        shift_ended_at: datetime | None,
    ) -> None:
        if (
            shift_started_at is not None
            and shift_ended_at is not None
            and shift_ended_at < shift_started_at
        ):
            raise ValueError("shift_ended_at cannot be before shift_started_at.")

    def _validate_required_links(
        self,
        tenant: TenantContext,
        work_center_id: UUID,
        shift_definition_id: UUID,
    ) -> None:
        work_center = self.work_centers.get_by_id(tenant.organization_id, work_center_id)
        if work_center is None:
            raise ValueError("Work center must belong to the current organization.")

        shift_definition = self.shift_definitions.get_by_id(
            tenant.organization_id,
            shift_definition_id,
        )
        if shift_definition is None:
            raise ValueError("Shift definition must belong to the current organization.")

    def _validate_optional_production_order(
        self,
        tenant: TenantContext,
        production_order_id: UUID | None,
    ) -> None:
        if production_order_id is None:
            return

        production_order = self.production_orders.get_by_id(tenant.organization_id, production_order_id)
        if production_order is None:
            raise ValueError("Production order must belong to the current organization.")

    def create_shift_report(
        self,
        tenant: TenantContext,
        data: ShiftReportCreate,
    ) -> ShiftReport:
        self._validate_required_links(tenant, data.work_center_id, data.shift_definition_id)
        self._validate_optional_production_order(tenant, data.production_order_id)
        self._validate_execution_window(data.shift_started_at, data.shift_ended_at)

        shift_report = ShiftReport(
            organization_id=tenant.organization_id,
            status=ShiftReportStatus.DRAFT,
            created_by_user_id=tenant.user_id,
            **data.model_dump(),
        )

        try:
            self.shift_reports.add(shift_report)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Shift report could not be saved due to invalid data.") from exc

        self.db.refresh(shift_report)
        return shift_report

    def list_shift_reports(
        self,
        tenant: TenantContext,
        status: ShiftReportStatus | None = None,
        work_center_id: UUID | None = None,
        shift_definition_id: UUID | None = None,
        report_date: date | None = None,
    ) -> list[ShiftReport]:
        return self.shift_reports.list_by_organization(
            tenant.organization_id,
            status=status,
            work_center_id=work_center_id,
            shift_definition_id=shift_definition_id,
            report_date=report_date,
        )

    def get_shift_report(
        self,
        tenant: TenantContext,
        shift_report_id: UUID,
    ) -> ShiftReport | None:
        return self.shift_reports.get_by_id(tenant.organization_id, shift_report_id)

    def update_shift_report(
        self,
        tenant: TenantContext,
        shift_report_id: UUID,
        data: ShiftReportUpdate,
    ) -> ShiftReport | None:
        shift_report = self.shift_reports.get_by_id(tenant.organization_id, shift_report_id)
        if shift_report is None:
            return None

        payload = data.model_dump(exclude_unset=True)
        if "work_center_id" in payload and payload["work_center_id"] is None:
            raise ValueError("work_center_id cannot be set to null.")
        if "shift_definition_id" in payload and payload["shift_definition_id"] is None:
            raise ValueError("shift_definition_id cannot be set to null.")

        new_work_center_id = payload.get("work_center_id", shift_report.work_center_id)
        new_shift_definition_id = payload.get(
            "shift_definition_id",
            shift_report.shift_definition_id,
        )
        self._validate_required_links(tenant, new_work_center_id, new_shift_definition_id)

        if "production_order_id" in payload:
            self._validate_optional_production_order(tenant, payload["production_order_id"])

        new_started_at = payload.get("shift_started_at", shift_report.shift_started_at)
        new_ended_at = payload.get("shift_ended_at", shift_report.shift_ended_at)
        if payload.get("status") == ShiftReportStatus.SUBMITTED and new_ended_at is None:
            new_ended_at = utc_now()
            payload["shift_ended_at"] = new_ended_at
        self._validate_execution_window(new_started_at, new_ended_at)

        for field, value in payload.items():
            setattr(shift_report, field, value)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Shift report could not be saved due to invalid data.") from exc

        self.db.refresh(shift_report)
        return shift_report


class ProductionOutputService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.items = ProductionOrderItemRepository(db)
        self.outputs = ProductionOutputRepository(db)
        self.production_orders = ProductionOrderRepository(db)
        self.shift_reports = ShiftReportRepository(db)
        self.work_centers = WorkCenterRepository(db)

    def _validate_positive_quantity(self, quantity: Decimal | None) -> None:
        if quantity is not None and quantity <= 0:
            raise ValueError("quantity_produced must be positive.")

    def _validate_required_links(
        self,
        tenant: TenantContext,
        production_order_id: UUID,
        work_center_id: UUID,
    ) -> ProductionOrder:
        production_order = self.production_orders.get_by_id(
            tenant.organization_id,
            production_order_id,
        )
        if production_order is None:
            raise ValueError("Production order must belong to the current organization.")

        work_center = self.work_centers.get_by_id(tenant.organization_id, work_center_id)
        if work_center is None:
            raise ValueError("Work center must belong to the current organization.")

        return production_order

    def _validate_optional_shift_report(
        self,
        tenant: TenantContext,
        shift_report_id: UUID | None,
    ) -> None:
        if shift_report_id is None:
            return

        shift_report = self.shift_reports.get_by_id(tenant.organization_id, shift_report_id)
        if shift_report is None:
            raise ValueError("Shift report must belong to the current organization.")

    def _validate_optional_item(
        self,
        tenant: TenantContext,
        production_order_id: UUID,
        production_order_item_id: UUID | None,
    ) -> None:
        if production_order_item_id is None:
            return

        item = self.items.get_by_id_with_parent_org(tenant.organization_id, production_order_item_id)
        if item is None:
            raise ValueError("Production order item must belong to the current organization.")
        if item.production_order_id != production_order_id:
            raise ValueError("Production order item must belong to the selected production order.")

    def create_production_output(
        self,
        tenant: TenantContext,
        data: ProductionOutputCreate,
    ) -> ProductionOutput:
        self._validate_positive_quantity(data.quantity_produced)
        self._validate_required_links(tenant, data.production_order_id, data.work_center_id)
        self._validate_optional_shift_report(tenant, data.shift_report_id)
        self._validate_optional_item(tenant, data.production_order_id, data.production_order_item_id)

        production_output = ProductionOutput(
            organization_id=tenant.organization_id,
            output_status=ProductionOutputStatus.RECORDED,
            created_by_user_id=tenant.user_id,
            **data.model_dump(),
        )

        try:
            self.outputs.add(production_output)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Production output could not be saved due to invalid data.") from exc

        self.db.refresh(production_output)
        return production_output

    def list_production_outputs(
        self,
        tenant: TenantContext,
        production_order_id: UUID | None = None,
        shift_report_id: UUID | None = None,
        work_center_id: UUID | None = None,
        output_date: date | None = None,
        output_status: ProductionOutputStatus | None = None,
    ) -> list[ProductionOutput]:
        return self.outputs.list_by_organization(
            tenant.organization_id,
            production_order_id=production_order_id,
            shift_report_id=shift_report_id,
            work_center_id=work_center_id,
            output_date=output_date,
            output_status=output_status,
        )

    def get_production_output(
        self,
        tenant: TenantContext,
        production_output_id: UUID,
    ) -> ProductionOutput | None:
        return self.outputs.get_by_id(tenant.organization_id, production_output_id)

    def update_production_output(
        self,
        tenant: TenantContext,
        production_output_id: UUID,
        data: ProductionOutputUpdate,
    ) -> ProductionOutput | None:
        production_output = self.outputs.get_by_id(tenant.organization_id, production_output_id)
        if production_output is None:
            return None

        payload = data.model_dump(exclude_unset=True)
        if "production_order_id" in payload and payload["production_order_id"] is None:
            raise ValueError("production_order_id cannot be set to null.")
        if "work_center_id" in payload and payload["work_center_id"] is None:
            raise ValueError("work_center_id cannot be set to null.")

        new_production_order_id = payload.get(
            "production_order_id",
            production_output.production_order_id,
        )
        new_work_center_id = payload.get("work_center_id", production_output.work_center_id)
        self._validate_required_links(tenant, new_production_order_id, new_work_center_id)

        if "shift_report_id" in payload:
            self._validate_optional_shift_report(tenant, payload["shift_report_id"])

        new_item_id = payload.get(
            "production_order_item_id",
            production_output.production_order_item_id,
        )
        self._validate_optional_item(tenant, new_production_order_id, new_item_id)
        self._validate_positive_quantity(payload.get("quantity_produced"))

        for field, value in payload.items():
            setattr(production_output, field, value)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Production output could not be saved due to invalid data.") from exc

        self.db.refresh(production_output)
        return production_output


class DowntimeEventService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.downtime_events = DowntimeEventRepository(db)
        self.production_orders = ProductionOrderRepository(db)
        self.shift_reports = ShiftReportRepository(db)
        self.work_centers = WorkCenterRepository(db)

    def _calculate_duration_minutes(
        self,
        start_time: datetime,
        end_time: datetime | None,
    ) -> int | None:
        if end_time is None:
            return None
        return int((end_time - start_time).total_seconds() // 60)

    def _derive_status(self, end_time: datetime | None) -> DowntimeStatus:
        if end_time is None:
            return DowntimeStatus.OPEN
        return DowntimeStatus.CLOSED

    def _validate_time_window(
        self,
        start_time: datetime,
        end_time: datetime | None,
    ) -> None:
        if end_time is not None and end_time <= start_time:
            raise ValueError("end_time must be after start_time.")

    def _validate_work_center(self, tenant: TenantContext, work_center_id: UUID) -> None:
        work_center = self.work_centers.get_by_id(tenant.organization_id, work_center_id)
        if work_center is None:
            raise ValueError("Work center must belong to the current organization.")

    def _validate_optional_shift_report(
        self,
        tenant: TenantContext,
        shift_report_id: UUID | None,
    ) -> None:
        if shift_report_id is None:
            return

        shift_report = self.shift_reports.get_by_id(tenant.organization_id, shift_report_id)
        if shift_report is None:
            raise ValueError("Shift report must belong to the current organization.")

    def _validate_optional_production_order(
        self,
        tenant: TenantContext,
        production_order_id: UUID | None,
    ) -> None:
        if production_order_id is None:
            return

        production_order = self.production_orders.get_by_id(tenant.organization_id, production_order_id)
        if production_order is None:
            raise ValueError("Production order must belong to the current organization.")

    def create_downtime_event(
        self,
        tenant: TenantContext,
        data: DowntimeEventCreate,
    ) -> DowntimeEvent:
        self._validate_work_center(tenant, data.work_center_id)
        self._validate_optional_shift_report(tenant, data.shift_report_id)
        self._validate_optional_production_order(tenant, data.production_order_id)
        self._validate_time_window(data.start_time, data.end_time)

        downtime_event = DowntimeEvent(
            organization_id=tenant.organization_id,
            status=self._derive_status(data.end_time),
            duration_minutes=self._calculate_duration_minutes(data.start_time, data.end_time),
            created_by_user_id=tenant.user_id,
            **data.model_dump(),
        )

        try:
            self.downtime_events.add(downtime_event)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Downtime event could not be saved due to invalid data.") from exc

        self.db.refresh(downtime_event)
        return downtime_event

    def list_downtime_events(
        self,
        tenant: TenantContext,
        work_center_id: UUID | None = None,
        shift_report_id: UUID | None = None,
        production_order_id: UUID | None = None,
        status: DowntimeStatus | None = None,
        category: DowntimeCategory | None = None,
    ) -> list[DowntimeEvent]:
        return self.downtime_events.list_by_organization(
            tenant.organization_id,
            work_center_id=work_center_id,
            shift_report_id=shift_report_id,
            production_order_id=production_order_id,
            status=status,
            category=category,
        )

    def get_downtime_event(
        self,
        tenant: TenantContext,
        downtime_event_id: UUID,
    ) -> DowntimeEvent | None:
        return self.downtime_events.get_by_id(tenant.organization_id, downtime_event_id)

    def update_downtime_event(
        self,
        tenant: TenantContext,
        downtime_event_id: UUID,
        data: DowntimeEventUpdate,
    ) -> DowntimeEvent | None:
        downtime_event = self.downtime_events.get_by_id(tenant.organization_id, downtime_event_id)
        if downtime_event is None:
            return None

        payload = data.model_dump(exclude_unset=True)
        if "work_center_id" in payload and payload["work_center_id"] is None:
            raise ValueError("work_center_id cannot be set to null.")
        if "start_time" in payload and payload["start_time"] is None:
            raise ValueError("start_time cannot be set to null.")

        new_work_center_id = payload.get("work_center_id", downtime_event.work_center_id)
        self._validate_work_center(tenant, new_work_center_id)

        if "shift_report_id" in payload:
            self._validate_optional_shift_report(tenant, payload["shift_report_id"])
        if "production_order_id" in payload:
            self._validate_optional_production_order(tenant, payload["production_order_id"])

        new_start_time = payload.get("start_time", downtime_event.start_time)
        new_end_time = payload.get("end_time", downtime_event.end_time)
        self._validate_time_window(new_start_time, new_end_time)
        payload["status"] = self._derive_status(new_end_time)
        payload["duration_minutes"] = self._calculate_duration_minutes(new_start_time, new_end_time)

        for field, value in payload.items():
            setattr(downtime_event, field, value)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Downtime event could not be saved due to invalid data.") from exc

        self.db.refresh(downtime_event)
        return downtime_event


class WasteRecordService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.items = ProductionOrderItemRepository(db)
        self.production_orders = ProductionOrderRepository(db)
        self.shift_reports = ShiftReportRepository(db)
        self.waste_records = WasteRecordRepository(db)
        self.work_centers = WorkCenterRepository(db)

    def _validate_positive_quantity(self, quantity: Decimal | None) -> None:
        if quantity is not None and quantity <= 0:
            raise ValueError("quantity_wasted must be positive.")

    def _validate_required_links(
        self,
        tenant: TenantContext,
        production_order_id: UUID,
        work_center_id: UUID,
    ) -> ProductionOrder:
        production_order = self.production_orders.get_by_id(
            tenant.organization_id,
            production_order_id,
        )
        if production_order is None:
            raise ValueError("Production order must belong to the current organization.")

        work_center = self.work_centers.get_by_id(tenant.organization_id, work_center_id)
        if work_center is None:
            raise ValueError("Work center must belong to the current organization.")

        return production_order

    def _validate_optional_shift_report(
        self,
        tenant: TenantContext,
        shift_report_id: UUID | None,
    ) -> None:
        if shift_report_id is None:
            return

        shift_report = self.shift_reports.get_by_id(tenant.organization_id, shift_report_id)
        if shift_report is None:
            raise ValueError("Shift report must belong to the current organization.")

    def _validate_optional_item(
        self,
        tenant: TenantContext,
        production_order_id: UUID,
        production_order_item_id: UUID | None,
    ) -> None:
        if production_order_item_id is None:
            return

        item = self.items.get_by_id_with_parent_org(tenant.organization_id, production_order_item_id)
        if item is None:
            raise ValueError("Production order item must belong to the current organization.")
        if item.production_order_id != production_order_id:
            raise ValueError("Production order item must belong to the selected production order.")

    def create_waste_record(
        self,
        tenant: TenantContext,
        data: WasteRecordCreate,
    ) -> WasteRecord:
        self._validate_positive_quantity(data.quantity_wasted)
        self._validate_required_links(tenant, data.production_order_id, data.work_center_id)
        self._validate_optional_shift_report(tenant, data.shift_report_id)
        self._validate_optional_item(tenant, data.production_order_id, data.production_order_item_id)

        waste_record = WasteRecord(
            organization_id=tenant.organization_id,
            created_by_user_id=tenant.user_id,
            **data.model_dump(),
        )

        try:
            self.waste_records.add(waste_record)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Waste record could not be saved due to invalid data.") from exc

        self.db.refresh(waste_record)
        return waste_record
    def list_waste_records(
        self,
        tenant: TenantContext,
        production_order_id: UUID | None = None,
        shift_report_id: UUID | None = None,
        work_center_id: UUID | None = None,
        waste_category: WasteCategory | None = None,
        waste_date: date | None = None,
    ) -> list[WasteRecord]:
        return self.waste_records.list_by_organization(
            tenant.organization_id,
            production_order_id=production_order_id,
            shift_report_id=shift_report_id,
            work_center_id=work_center_id,
            waste_category=waste_category,
            waste_date=waste_date,
        )

    def get_waste_record(
        self,
        tenant: TenantContext,
        waste_record_id: UUID,
    ) -> WasteRecord | None:
        return self.waste_records.get_by_id(tenant.organization_id, waste_record_id)

    def update_waste_record(
        self,
        tenant: TenantContext,
        waste_record_id: UUID,
        data: WasteRecordUpdate,
    ) -> WasteRecord | None:
        waste_record = self.waste_records.get_by_id(tenant.organization_id, waste_record_id)
        if waste_record is None:
            return None

        payload = data.model_dump(exclude_unset=True)
        if "production_order_id" in payload and payload["production_order_id"] is None:
            raise ValueError("production_order_id cannot be set to null.")
        if "work_center_id" in payload and payload["work_center_id"] is None:
            raise ValueError("work_center_id cannot be set to null.")

        new_production_order_id = payload.get("production_order_id", waste_record.production_order_id)
        new_work_center_id = payload.get("work_center_id", waste_record.work_center_id)
        self._validate_required_links(tenant, new_production_order_id, new_work_center_id)

        if "shift_report_id" in payload:
            self._validate_optional_shift_report(tenant, payload["shift_report_id"])

        new_item_id = payload.get("production_order_item_id", waste_record.production_order_item_id)
        self._validate_optional_item(tenant, new_production_order_id, new_item_id)
        self._validate_positive_quantity(payload.get("quantity_wasted"))

        for field, value in payload.items():
            setattr(waste_record, field, value)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Waste record could not be saved due to invalid data.") from exc

        self.db.refresh(waste_record)
        return waste_record


from app.core.interfaces.activity_log import instrument_activity_methods

instrument_activity_methods(WorkCenterService, {"create_work_center": ("work_center.created", "work_center"), "update_work_center": ("work_center.updated", "work_center"), "delete_work_center": ("work_center.deleted", "work_center")})
instrument_activity_methods(ShiftDefinitionService, {"create_shift_definition": ("shift.created", "shift"), "update_shift_definition": ("shift.updated", "shift"), "delete_shift_definition": ("shift.deleted", "shift")})
instrument_activity_methods(ProductionOrderService, {"create_production_order": ("production_order.created", "production_order"), "update_production_order": ("production_order.updated", "production_order")})
instrument_activity_methods(ProductionOrderItemService, {"create_item": ("production_order_item.created", "production_order_item"), "update_item": ("production_order_item.updated", "production_order_item"), "delete_item": ("production_order_item.deleted", "production_order_item")})
instrument_activity_methods(ShiftReportService, {"create_shift_report": ("shift_report.created", "shift_report"), "update_shift_report": ("shift_report.updated", "shift_report")})
instrument_activity_methods(ProductionOutputService, {"create_production_output": ("production_output.created", "production_output"), "update_production_output": ("production_output.updated", "production_output")})
instrument_activity_methods(DowntimeEventService, {"create_downtime_event": ("downtime_event.created", "downtime_event"), "update_downtime_event": ("downtime_event.updated", "downtime_event")})
instrument_activity_methods(WasteRecordService, {"create_waste_record": ("waste_record.created", "waste_record"), "update_waste_record": ("waste_record.updated", "waste_record")})
