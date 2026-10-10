from datetime import date
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.core.types import ISODatetime
from app.production.domain.enums import ProductionAllocationStatus, ProductionDemandPriority, ProductionDemandStatus


class DemandInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CreateDemandItemRequest(DemandInput):
    line_no: int | None = Field(default=None, ge=1)
    product_type: str | None = Field(default=None, max_length=100)
    target_spec_json: dict[str, Any] | None = None
    required_quantity: Decimal = Field(gt=0, max_digits=15, decimal_places=3)
    unit: str = Field(min_length=1, max_length=20)
    notes: str | None = None


class UpdateDemandItemRequest(DemandInput):
    line_no: int | None = Field(default=None, ge=1)
    product_type: str | None = Field(default=None, max_length=100)
    target_spec_json: dict[str, Any] | None = None
    required_quantity: Decimal | None = Field(default=None, gt=0, max_digits=15, decimal_places=3)
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    notes: str | None = None

    @model_validator(mode="after")
    def required_values(self):
        for field in ("line_no", "required_quantity", "unit"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class CreateDemandRequest(DemandInput):
    customer_id: UUID
    quote_id: UUID | None = None
    request_date: date | None = None
    requested_delivery_date: date | None = None
    priority: ProductionDemandPriority = ProductionDemandPriority.NORMAL
    notes: str | None = None
    items: list[CreateDemandItemRequest] = Field(default_factory=list)


class SalesOrderLineTransfer(DemandInput):
    order_item_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=15, decimal_places=3)
    notes: str | None = None


class DemandFromSalesOrderRequest(DemandInput):
    """Part (or all) of a confirmed sales order's lines (SALES-001). transfer_key, set once per form by the screen,
    makes a repeated request return the same demand."""
    sales_order_id: UUID
    lines: list[SalesOrderLineTransfer] = Field(min_length=1)
    transfer_key: UUID | None = None
    requested_delivery_date: date | None = None
    priority: ProductionDemandPriority = ProductionDemandPriority.NORMAL
    notes: str | None = None


class SalesOrderLookupLine(BaseModel):
    id: UUID
    line_no: int
    product_type: str
    target_spec_json: dict[str, Any] | None
    unit: str
    ordered_quantity: Decimal
    transferred_quantity: Decimal
    remaining_quantity: Decimal


class SalesOrderLookup(BaseModel):
    id: UUID
    number: str
    quote_id: UUID | None
    requested_delivery_date: ISODatetime | None
    lines: list[SalesOrderLookupLine]


class UpdateDemandRequest(DemandInput):
    customer_id: UUID | None = None
    quote_id: UUID | None = None
    request_date: date | None = None
    requested_delivery_date: date | None = None
    priority: ProductionDemandPriority | None = None
    notes: str | None = None
    # An atomic replacement is used by the edit form; individual item routes remain available.
    items: list[CreateDemandItemRequest] | None = None

    @model_validator(mode="after")
    def required_values(self):
        for field in ("customer_id", "request_date", "priority", "items"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class DemandItemAllocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    production_order_id: UUID
    production_order_number: str
    production_order_status: str
    allocated_quantity: Decimal
    status: ProductionAllocationStatus
    created_at: ISODatetime
    released_at: ISODatetime | None
    release_reason: str | None


class DemandItemResponse(CreateDemandItemRequest):
    source_order_item_id: UUID | None = None
    # allocated_quantity is kept as an alias of active_allocated_quantity for existing clients.
    allocated_quantity: Decimal
    active_allocated_quantity: Decimal
    released_allocated_quantity: Decimal
    remaining_quantity: Decimal
    planning_state: Literal["ready_for_planning", "partially_planned", "planned"]
    allocations: list[DemandItemAllocationResponse] = Field(default_factory=list)
    id: UUID
    line_no: int
    model_config = ConfigDict(from_attributes=True)


class CustomerSummaryResponse(BaseModel):
    id: UUID
    code: str
    name: str


class QuoteSummaryResponse(BaseModel):
    id: UUID
    number: str
    status: str


class SalesOrderSummaryResponse(BaseModel):
    id: UUID
    number: str | None


class DemandResponse(BaseModel):
    sales_order: SalesOrderSummaryResponse | None = None
    total_required: Decimal
    total_allocated: Decimal
    total_active_allocated: Decimal
    total_released_allocated: Decimal
    total_remaining: Decimal
    allocation_percentage: Decimal
    id: UUID
    demand_number: str
    customer: CustomerSummaryResponse
    quote: QuoteSummaryResponse | None
    request_date: date
    requested_delivery_date: date | None
    priority: ProductionDemandPriority
    status: ProductionDemandStatus
    planning_sequence: int | None
    notes: str | None
    item_count: int
    total_quantity: Decimal
    quantities_by_unit: dict[str, Decimal]
    created_by: str | None
    created_at: ISODatetime
    updated_at: ISODatetime


class DemandDetailResponse(DemandResponse):
    items: list[DemandItemResponse]


class PlanningDemandResponse(DemandDetailResponse):
    spec_summary: dict[str, Any] | None


class PaginatedDemandList(BaseModel):
    items: list[DemandResponse]
    total: int
    page: int
    page_size: int
    # Demands matching the other filters but outside the requested statuses; null when no statuses were given.
    hidden_by_status: int | None = None


class PaginatedPlanningList(PaginatedDemandList):
    items: list[PlanningDemandResponse]


class DemandStatusRequest(DemandInput):
    status: ProductionDemandStatus


class ReorderRequest(DemandInput):
    new_position: int = Field(ge=1)


class PlanningFilters(BaseModel):
    # Planning queue view: active (default) = plannable with remaining quantity; planned; all.
    view: Literal["active", "planned", "all"] = "active"
    has_remaining: bool = False
    customer_id: UUID | None = None
    quote_id: UUID | None = None
    status: ProductionDemandStatus | None = None
    priority: ProductionDemandPriority | None = None
    requested_delivery_from: date | None = None
    requested_delivery_to: date | None = None
    product_type: str | None = None
    search: str = Field(default="", max_length=255)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: Literal["planning_sequence", "priority", "requested_delivery_date", "created_at", "demand_number"] = "planning_sequence"
    sort_order: Literal["asc", "desc"] = "asc"
