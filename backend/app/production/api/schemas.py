from datetime import date, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.types import ISODatetime
from app.production.domain.enums import (
    ProductionOrderPriority,
    ProductionOrderStatus,
    ShiftDefinitionStatus,
    ShiftType,
    WorkCenterStatus,
    WorkCenterType,
)


class WorkCenterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    center_type: WorkCenterType = WorkCenterType.GENERIC
    status: WorkCenterStatus = WorkCenterStatus.ACTIVE
    location: str | None = Field(default=None, max_length=255)
    commissioned_date: date | None = None
    notes: str | None = None


class WorkCenterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    center_type: WorkCenterType | None = None
    status: WorkCenterStatus | None = None
    location: str | None = Field(default=None, max_length=255)
    commissioned_date: date | None = None
    notes: str | None = None


class WorkCenterListItem(BaseModel):
    id: UUID
    organization_id: UUID
    code: str
    name: str
    center_type: WorkCenterType
    status: WorkCenterStatus
    location: str | None
    commissioned_date: date | None
    created_at: ISODatetime
    updated_at: ISODatetime

    model_config = ConfigDict(from_attributes=True)


class WorkCenterRead(WorkCenterListItem):
    notes: str | None


class WorkCenterDeleteSummary(BaseModel):
    production_orders_count: int
    shifts_count: int
    downtime_records_count: int
    waste_records_count: int
    production_results_count: int = 0


class ShiftDefinitionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    shift_type: ShiftType = ShiftType.CUSTOM
    start_time: time
    end_time: time
    status: ShiftDefinitionStatus = ShiftDefinitionStatus.ACTIVE
    notes: str | None = None


class ShiftDefinitionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    shift_type: ShiftType | None = None
    start_time: time | None = None
    end_time: time | None = None
    status: ShiftDefinitionStatus | None = None
    notes: str | None = None


class ShiftDefinitionListItem(BaseModel):
    id: UUID
    organization_id: UUID
    code: str
    name: str
    shift_type: ShiftType
    start_time: time
    end_time: time
    duration_hours: Decimal
    crosses_midnight: bool
    status: ShiftDefinitionStatus
    created_at: ISODatetime
    updated_at: ISODatetime

    model_config = ConfigDict(from_attributes=True)


class ShiftDefinitionRead(ShiftDefinitionListItem):
    notes: str | None


class ShiftDeletionImpact(BaseModel):
    production_orders: int
    is_blocked: bool


class ProductionOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    production_order_number: str | None = Field(default=None, min_length=1, max_length=64)
    work_center_id: UUID
    product_type: str = Field(min_length=1, max_length=120)
    target_spec_json: dict[str, Any] | None = None
    planned_quantity: Decimal = Field(gt=0, max_digits=15, decimal_places=3)
    unit: str = Field(min_length=1, max_length=32)
    priority: ProductionOrderPriority = ProductionOrderPriority.NORMAL
    planned_start_date: date
    planned_end_date: date
    notes: str | None = None


class ProductionOrderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    production_order_number: str | None = Field(default=None, min_length=1, max_length=64)
    work_center_id: UUID | None = None
    product_type: str | None = Field(default=None, min_length=1, max_length=120)
    target_spec_json: dict[str, Any] | None = None
    planned_quantity: Decimal | None = Field(default=None, gt=0, max_digits=15, decimal_places=3)
    unit: str | None = Field(default=None, min_length=1, max_length=32)
    priority: ProductionOrderPriority | None = None
    # No status here: status changes only through POST /production-orders/{id}/transitions.
    planned_start_date: date | None = None
    planned_end_date: date | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def reject_null_required_values(self):
        for field in ("production_order_number", "work_center_id", "product_type", "planned_quantity", "unit", "priority", "planned_start_date", "planned_end_date"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ProductionOrderListItem(BaseModel):
    id: UUID
    organization_id: UUID
    production_order_number: str
    work_center_id: UUID
    product_type: str
    planned_quantity: Decimal
    unit: str
    priority: ProductionOrderPriority
    status: ProductionOrderStatus
    planned_start_date: date
    planned_end_date: date
    created_by_user_id: UUID
    created_at: ISODatetime
    updated_at: ISODatetime

    model_config = ConfigDict(from_attributes=True)


class ProductionOrderRead(ProductionOrderListItem):
    work_center: dict[str, Any] | None = None
    target_spec_json: dict[str, Any] | None
    notes: str | None


class ProductionOrderItemCreate(BaseModel):
    line_no: int | None = Field(default=None, ge=1)
    # Line-specific variation only; product_type lives on the ProductionOrder header.
    target_spec_json: dict[str, Any] | None = None
    planned_quantity: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=32)
    notes: str | None = None


class ProductionOrderItemUpdate(BaseModel):
    line_no: int | None = Field(default=None, ge=1)
    # Line-specific variation only; product_type lives on the ProductionOrder header.
    target_spec_json: dict[str, Any] | None = None
    planned_quantity: Decimal | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, min_length=1, max_length=32)
    notes: str | None = None


class ProductionOrderItemListItem(BaseModel):
    id: UUID
    production_order_id: UUID
    line_no: int
    target_spec_json: dict[str, Any] | None
    planned_quantity: Decimal
    unit: str
    created_at: ISODatetime
    updated_at: ISODatetime

    model_config = ConfigDict(from_attributes=True)


class ProductionOrderItemRead(ProductionOrderItemListItem):
    notes: str | None


