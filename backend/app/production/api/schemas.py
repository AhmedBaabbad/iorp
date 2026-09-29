from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.types import ISODatetime
from app.production.domain.enums import (
    DowntimeCategory,
    DowntimeStatus,
    ProductionOutputStatus,
    ProductionOrderPriority,
    ProductionOrderStatus,
    ShiftDefinitionStatus,
    ShiftReportStatus,
    ShiftType,
    WasteCategory,
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
    shift_reports_count: int
    downtime_records_count: int
    waste_records_count: int
    production_outputs_count: int


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
    shift_reports: int
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


class ShiftReportCreate(BaseModel):
    work_center_id: UUID
    shift_definition_id: UUID
    production_order_id: UUID | None = None
    report_date: date
    shift_started_at: datetime | None = None
    shift_ended_at: datetime | None = None
    summary: str = Field(min_length=1)
    notes: str | None = None


class ShiftReportUpdate(BaseModel):
    work_center_id: UUID | None = None
    shift_definition_id: UUID | None = None
    production_order_id: UUID | None = None
    report_date: date | None = None
    shift_started_at: datetime | None = None
    shift_ended_at: datetime | None = None
    status: ShiftReportStatus | None = None
    summary: str | None = Field(default=None, min_length=1)
    notes: str | None = None


class ShiftReportListItem(BaseModel):
    id: UUID
    organization_id: UUID
    work_center_id: UUID
    shift_definition_id: UUID
    production_order_id: UUID | None
    report_date: date
    shift_started_at: ISODatetime | None
    shift_ended_at: ISODatetime | None
    status: ShiftReportStatus
    summary: str
    created_by_user_id: UUID
    created_at: ISODatetime
    updated_at: ISODatetime

    model_config = ConfigDict(from_attributes=True)


class ShiftReportRead(ShiftReportListItem):
    notes: str | None


class ProductionOutputCreate(BaseModel):
    production_order_id: UUID
    work_center_id: UUID
    shift_report_id: UUID | None = None
    production_order_item_id: UUID | None = None
    output_date: date
    recorded_at: datetime | None = None
    quantity_produced: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=32)
    notes: str | None = None


class ProductionOutputUpdate(BaseModel):
    production_order_id: UUID | None = None
    work_center_id: UUID | None = None
    shift_report_id: UUID | None = None
    production_order_item_id: UUID | None = None
    output_date: date | None = None
    recorded_at: datetime | None = None
    quantity_produced: Decimal | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, min_length=1, max_length=32)
    output_status: ProductionOutputStatus | None = None
    notes: str | None = None


class ProductionOutputListItem(BaseModel):
    id: UUID
    organization_id: UUID
    production_order_id: UUID
    work_center_id: UUID
    shift_report_id: UUID | None
    production_order_item_id: UUID | None
    output_date: date
    recorded_at: ISODatetime | None
    quantity_produced: Decimal
    unit: str
    output_status: ProductionOutputStatus
    created_by_user_id: UUID
    created_at: ISODatetime
    updated_at: ISODatetime

    model_config = ConfigDict(from_attributes=True)


class ProductionOutputRead(ProductionOutputListItem):
    notes: str | None


class DowntimeEventCreate(BaseModel):
    work_center_id: UUID
    shift_report_id: UUID | None = None
    production_order_id: UUID | None = None
    start_time: datetime
    end_time: datetime | None = None
    category: DowntimeCategory
    reason_code: str = Field(min_length=1, max_length=255)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_time_window(self) -> "DowntimeEventCreate":
        if self.end_time is not None and self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time.")
        return self


class DowntimeEventUpdate(BaseModel):
    work_center_id: UUID | None = None
    shift_report_id: UUID | None = None
    production_order_id: UUID | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    category: DowntimeCategory | None = None
    reason_code: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_time_window(self) -> "DowntimeEventUpdate":
        if self.start_time is not None and self.end_time is not None and self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time.")
        return self


class DowntimeEventListItem(BaseModel):
    id: UUID
    organization_id: UUID
    work_center_id: UUID
    shift_report_id: UUID | None
    production_order_id: UUID | None
    start_time: ISODatetime
    end_time: ISODatetime | None
    duration_minutes: int | None
    category: DowntimeCategory
    reason_code: str
    status: DowntimeStatus
    created_by_user_id: UUID
    created_at: ISODatetime
    updated_at: ISODatetime

    model_config = ConfigDict(from_attributes=True)


class DowntimeEventRead(DowntimeEventListItem):
    notes: str | None


class WasteRecordCreate(BaseModel):
    production_order_id: UUID
    work_center_id: UUID
    shift_report_id: UUID | None = None
    production_order_item_id: UUID | None = None
    waste_date: date
    quantity_wasted: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=32)
    waste_category: WasteCategory
    reason_code: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class WasteRecordUpdate(BaseModel):
    production_order_id: UUID | None = None
    work_center_id: UUID | None = None
    shift_report_id: UUID | None = None
    production_order_item_id: UUID | None = None
    waste_date: date | None = None
    quantity_wasted: Decimal | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, min_length=1, max_length=32)
    waste_category: WasteCategory | None = None
    reason_code: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class WasteRecordListItem(BaseModel):
    id: UUID
    organization_id: UUID
    production_order_id: UUID
    work_center_id: UUID
    shift_report_id: UUID | None
    production_order_item_id: UUID | None
    waste_date: date
    quantity_wasted: Decimal
    unit: str
    waste_category: WasteCategory
    reason_code: str | None
    created_by_user_id: UUID
    created_at: ISODatetime
    updated_at: ISODatetime

    model_config = ConfigDict(from_attributes=True)


class WasteRecordRead(WasteRecordListItem):
    notes: str | None
