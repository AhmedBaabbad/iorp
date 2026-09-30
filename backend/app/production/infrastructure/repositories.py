from datetime import date
from uuid import UUID

from sqlalchemy import Integer, func, select
from sqlalchemy.orm import Session

from app.production.domain.enums import (
    DowntimeCategory,
    DowntimeStatus,
    ProductionOutputStatus,
    ProductionOrderPriority,
    ProductionOrderStatus,
    WasteCategory,
)
from app.production.infrastructure.models import (
    DowntimeEvent,
    ProductionOutput,
    ProductionOrder,
    ProductionOrderItem,
    ShiftDefinition,
    WasteRecord,
    WorkCenter,
)


class WorkCenterRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, work_center: WorkCenter) -> WorkCenter:
        self.db.add(work_center)
        self.db.flush()
        return work_center

    def get_by_id(self, organization_id: UUID, work_center_id: UUID) -> WorkCenter | None:
        statement = select(WorkCenter).where(
            WorkCenter.organization_id == organization_id,
            WorkCenter.id == work_center_id,
        )
        return self.db.scalar(statement)

    def get_by_code(self, organization_id: UUID, code: str) -> WorkCenter | None:
        statement = select(WorkCenter).where(
            WorkCenter.organization_id == organization_id,
            WorkCenter.code == code,
        )
        return self.db.scalar(statement)

    def list_by_organization(self, organization_id: UUID) -> list[WorkCenter]:
        statement = (
            select(WorkCenter)
            .where(WorkCenter.organization_id == organization_id)
            .order_by(WorkCenter.code.asc())
        )
        return list(self.db.scalars(statement))

    def get_highest_sequence_for_prefix(self, organization_id: UUID, prefix: str) -> int:
        pattern = f"^WC-{prefix}-([0-9]+)$"
        sequence_text = func.substring(WorkCenter.code, pattern)
        statement = select(func.coalesce(func.max(sequence_text.cast(Integer)), 0)).where(
            WorkCenter.organization_id == organization_id,
        )
        return int(self.db.scalar(statement) or 0)

    def get_work_center_delete_summary(
        self, organization_id: UUID, work_center_id: UUID
    ) -> dict | None:
        work_center = self.get_by_id(organization_id, work_center_id)
        if work_center is None:
            return None

        production_orders_count = int(self.db.scalar(
            select(func.count(ProductionOrder.id)).where(
                ProductionOrder.work_center_id == work_center_id,
            )
        ) or 0)

        shifts_count = 0

        downtime_records_count = int(self.db.scalar(
            select(func.count(DowntimeEvent.id)).where(
                DowntimeEvent.work_center_id == work_center_id,
            )
        ) or 0)

        waste_records_count = int(self.db.scalar(
            select(func.count(WasteRecord.id)).where(
                WasteRecord.work_center_id == work_center_id,
            )
        ) or 0)

        production_outputs_count = int(self.db.scalar(
            select(func.count(ProductionOutput.id)).where(
                ProductionOutput.work_center_id == work_center_id,
            )
        ) or 0)

        return {
            "production_orders_count": production_orders_count,
            "shifts_count": shifts_count,
            "downtime_records_count": downtime_records_count,
            "waste_records_count": waste_records_count,
            "production_outputs_count": production_outputs_count,
        }

    def delete_work_center(self, organization_id: UUID, work_center_id: UUID) -> bool:
        work_center = self.get_by_id(organization_id, work_center_id)
        if work_center is None:
            return False
        self.db.delete(work_center)
        return True


class ShiftDefinitionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, shift_definition: ShiftDefinition) -> ShiftDefinition:
        self.db.add(shift_definition)
        self.db.flush()
        return shift_definition

    def get_by_id(self, organization_id: UUID, shift_definition_id: UUID) -> ShiftDefinition | None:
        statement = select(ShiftDefinition).where(
            ShiftDefinition.organization_id == organization_id,
            ShiftDefinition.id == shift_definition_id,
        )
        return self.db.scalar(statement)

    def get_by_code(self, organization_id: UUID, code: str) -> ShiftDefinition | None:
        statement = select(ShiftDefinition).where(
            ShiftDefinition.organization_id == organization_id,
            ShiftDefinition.code == code,
        )
        return self.db.scalar(statement)

    def list_by_organization(self, organization_id: UUID) -> list[ShiftDefinition]:
        statement = (
            select(ShiftDefinition)
            .where(ShiftDefinition.organization_id == organization_id)
            .order_by(ShiftDefinition.code.asc())
        )
        return list(self.db.scalars(statement))



class ProductionOrderRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, production_order: ProductionOrder) -> ProductionOrder:
        self.db.add(production_order)
        self.db.flush()
        return production_order

    def get_by_id(self, organization_id: UUID, production_order_id: UUID) -> ProductionOrder | None:
        statement = select(ProductionOrder).where(
            ProductionOrder.organization_id == organization_id,
            ProductionOrder.id == production_order_id,
        )
        return self.db.scalar(statement)

    def get_by_id_for_update(self, organization_id: UUID, production_order_id: UUID) -> ProductionOrder | None:
        # Row lock shared with cancellation, so a status change cannot interleave with it.
        statement = select(ProductionOrder).where(
            ProductionOrder.organization_id == organization_id,
            ProductionOrder.id == production_order_id,
        ).with_for_update().execution_options(populate_existing=True)
        return self.db.scalar(statement)

    def get_by_number(
        self,
        organization_id: UUID,
        production_order_number: str,
    ) -> ProductionOrder | None:
        statement = select(ProductionOrder).where(
            ProductionOrder.organization_id == organization_id,
            ProductionOrder.production_order_number == production_order_number,
        )
        return self.db.scalar(statement)

    def list_by_organization(
        self,
        organization_id: UUID,
        status: ProductionOrderStatus | None = None,
        work_center_id: UUID | None = None,
        priority: ProductionOrderPriority | None = None,
    ) -> list[ProductionOrder]:
        statement = select(ProductionOrder).where(ProductionOrder.organization_id == organization_id)

        if status is not None:
            statement = statement.where(ProductionOrder.status == status)
        if work_center_id is not None:
            statement = statement.where(ProductionOrder.work_center_id == work_center_id)
        if priority is not None:
            statement = statement.where(ProductionOrder.priority == priority)

        statement = statement.order_by(
            ProductionOrder.planned_start_date.asc(),
            ProductionOrder.production_order_number.asc(),
        )
        return list(self.db.scalars(statement))

    def count_by_organization(self, organization_id: UUID) -> int:
        statement = select(func.count(ProductionOrder.id)).where(
            ProductionOrder.organization_id == organization_id
        )
        return self.db.scalar(statement) or 0



class ProductionOrderItemRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, item: ProductionOrderItem) -> ProductionOrderItem:
        self.db.add(item)
        self.db.flush()
        return item

    def list_by_order(self, organization_id: UUID, production_order_id: UUID) -> list[ProductionOrderItem]:
        statement = (
            select(ProductionOrderItem)
            .join(ProductionOrder, ProductionOrder.id == ProductionOrderItem.production_order_id)
            .where(
                ProductionOrder.organization_id == organization_id,
                ProductionOrderItem.production_order_id == production_order_id,
            )
            .order_by(ProductionOrderItem.line_no.asc())
        )
        return list(self.db.scalars(statement))

    def get_by_id(
        self,
        organization_id: UUID,
        production_order_id: UUID,
        item_id: UUID,
    ) -> ProductionOrderItem | None:
        statement = (
            select(ProductionOrderItem)
            .join(ProductionOrder, ProductionOrder.id == ProductionOrderItem.production_order_id)
            .where(
                ProductionOrder.organization_id == organization_id,
                ProductionOrderItem.production_order_id == production_order_id,
                ProductionOrderItem.id == item_id,
            )
        )
        return self.db.scalar(statement)

    def get_by_id_with_parent_org(
        self,
        organization_id: UUID,
        item_id: UUID,
    ) -> ProductionOrderItem | None:
        statement = (
            select(ProductionOrderItem)
            .join(ProductionOrder, ProductionOrderItem.production_order_id == ProductionOrder.id)
            .where(
                ProductionOrder.organization_id == organization_id,
                ProductionOrderItem.id == item_id,
            )
        )
        return self.db.scalar(statement)

    def get_by_line_no(self, organization_id: UUID, production_order_id: UUID, line_no: int) -> ProductionOrderItem | None:
        statement = (
            select(ProductionOrderItem)
            .join(ProductionOrder, ProductionOrder.id == ProductionOrderItem.production_order_id)
            .where(
                ProductionOrder.organization_id == organization_id,
                ProductionOrderItem.production_order_id == production_order_id,
                ProductionOrderItem.line_no == line_no,
            )
        )
        return self.db.scalar(statement)

    def next_line_no(self, organization_id: UUID, production_order_id: UUID) -> int:
        statement = (
            select(func.max(ProductionOrderItem.line_no))
            .join(ProductionOrder, ProductionOrder.id == ProductionOrderItem.production_order_id)
            .where(
                ProductionOrder.organization_id == organization_id,
                ProductionOrderItem.production_order_id == production_order_id,
            )
        )
        return (self.db.scalar(statement) or 0) + 1

    def delete(self, item: ProductionOrderItem) -> None:
        self.db.delete(item)


class ProductionOutputRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, production_output: ProductionOutput) -> ProductionOutput:
        self.db.add(production_output)
        self.db.flush()
        return production_output

    def get_by_id(self, organization_id: UUID, production_output_id: UUID) -> ProductionOutput | None:
        statement = select(ProductionOutput).where(
            ProductionOutput.organization_id == organization_id,
            ProductionOutput.id == production_output_id,
        )
        return self.db.scalar(statement)

    def list_by_organization(
        self,
        organization_id: UUID,
        production_order_id: UUID | None = None,
        work_center_id: UUID | None = None,
        output_date: date | None = None,
        output_status: ProductionOutputStatus | None = None,
    ) -> list[ProductionOutput]:
        statement = select(ProductionOutput).where(ProductionOutput.organization_id == organization_id)

        if production_order_id is not None:
            statement = statement.where(ProductionOutput.production_order_id == production_order_id)
        if work_center_id is not None:
            statement = statement.where(ProductionOutput.work_center_id == work_center_id)
        if output_date is not None:
            statement = statement.where(ProductionOutput.output_date == output_date)
        if output_status is not None:
            statement = statement.where(ProductionOutput.output_status == output_status)

        statement = statement.order_by(
            ProductionOutput.output_date.desc(),
            ProductionOutput.recorded_at.desc(),
            ProductionOutput.created_at.desc(),
        )
        return list(self.db.scalars(statement))


class DowntimeEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, downtime_event: DowntimeEvent) -> DowntimeEvent:
        self.db.add(downtime_event)
        self.db.flush()
        return downtime_event

    def get_by_id(self, organization_id: UUID, downtime_event_id: UUID) -> DowntimeEvent | None:
        statement = select(DowntimeEvent).where(
            DowntimeEvent.organization_id == organization_id,
            DowntimeEvent.id == downtime_event_id,
        )
        return self.db.scalar(statement)

    def list_by_organization(
        self,
        organization_id: UUID,
        work_center_id: UUID | None = None,
        production_order_id: UUID | None = None,
        status: DowntimeStatus | None = None,
        category: DowntimeCategory | None = None,
    ) -> list[DowntimeEvent]:
        statement = select(DowntimeEvent).where(DowntimeEvent.organization_id == organization_id)

        if work_center_id is not None:
            statement = statement.where(DowntimeEvent.work_center_id == work_center_id)
        if production_order_id is not None:
            statement = statement.where(DowntimeEvent.production_order_id == production_order_id)
        if status is not None:
            statement = statement.where(DowntimeEvent.status == status)
        if category is not None:
            statement = statement.where(DowntimeEvent.category == category)

        statement = statement.order_by(
            DowntimeEvent.start_time.desc(),
            DowntimeEvent.created_at.desc(),
        )
        return list(self.db.scalars(statement))


class WasteRecordRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, waste_record: WasteRecord) -> WasteRecord:
        self.db.add(waste_record)
        self.db.flush()
        return waste_record

    def get_by_id(self, organization_id: UUID, waste_record_id: UUID) -> WasteRecord | None:
        statement = select(WasteRecord).where(
            WasteRecord.organization_id == organization_id,
            WasteRecord.id == waste_record_id,
        )
        return self.db.scalar(statement)

    def list_by_organization(
        self,
        organization_id: UUID,
        production_order_id: UUID | None = None,
        work_center_id: UUID | None = None,
        waste_category: WasteCategory | None = None,
        waste_date: date | None = None,
    ) -> list[WasteRecord]:
        statement = select(WasteRecord).where(WasteRecord.organization_id == organization_id)

        if production_order_id is not None:
            statement = statement.where(WasteRecord.production_order_id == production_order_id)
        if work_center_id is not None:
            statement = statement.where(WasteRecord.work_center_id == work_center_id)
        if waste_category is not None:
            statement = statement.where(WasteRecord.waste_category == waste_category)
        if waste_date is not None:
            statement = statement.where(WasteRecord.waste_date == waste_date)

        statement = statement.order_by(
            WasteRecord.waste_date.desc(),
            WasteRecord.created_at.desc(),
        )
        return list(self.db.scalars(statement))
