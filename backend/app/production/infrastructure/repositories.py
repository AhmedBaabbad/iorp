from uuid import UUID

from sqlalchemy import Integer, func, select
from sqlalchemy.orm import Session

from app.production.domain.enums import (
    ProductionOrderPriority,
    ProductionOrderStatus,
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

        # Final results on this center's orders block the delete (they are kept as records).
        production_results_count = int(self.db.scalar(
            select(func.count(ProductionResultEntry.id)).where(
                ProductionResultEntry.organization_id == organization_id,
                ProductionResultEntry.production_order_id.in_(
                    select(ProductionOrder.id).where(ProductionOrder.organization_id == organization_id, ProductionOrder.work_center_id == work_center_id)),
            )
        ) or 0)

        return {
            "production_orders_count": production_orders_count,
            "shifts_count": shifts_count,
            "downtime_records_count": downtime_records_count,
            "waste_records_count": waste_records_count,
            "production_results_count": production_results_count,
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

    def list_statement(
        self,
        organization_id: UUID,
        status: ProductionOrderStatus | None = None,
        work_center_id: UUID | None = None,
        priority: ProductionOrderPriority | None = None,
        search: str | None = None,
    ):
        """The organization's orders matching the filters, earliest planned start first; id last, so pages never overlap."""
        statement = select(ProductionOrder).where(ProductionOrder.organization_id == organization_id)

        if status is not None:
            statement = statement.where(ProductionOrder.status == status)
        if work_center_id is not None:
            statement = statement.where(ProductionOrder.work_center_id == work_center_id)
        if priority is not None:
            statement = statement.where(ProductionOrder.priority == priority)
        if search:
            statement = statement.where(ProductionOrder.production_order_number.icontains(search, autoescape=True)
                                        | ProductionOrder.product_type.icontains(search, autoescape=True))

        return statement.order_by(
            ProductionOrder.planned_start_date.asc(),
            ProductionOrder.production_order_number.asc(),
            ProductionOrder.id.asc(),
        )

    def list_by_organization(self, organization_id: UUID, **filters) -> list[ProductionOrder]:
        return list(self.db.scalars(self.list_statement(organization_id, **filters)))



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


