from datetime import date
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.production.domain.enums import ProductionOrderPriority
from app.core.types import ISODatetime
from app.production.api.schemas import ProductionOrderRead
from typing import Any, Literal


class PlanningOrderRead(ProductionOrderRead):
    allocations: list[dict[str, Any]] = Field(default_factory=list)
    # Sum of ACTIVE allocations; equals planned_quantity until the order is cancelled.
    active_allocated_quantity: Decimal = Decimal(0)
    # Specification lines ordered width -> color -> thickness -> weight.
    lines: list[dict[str, Any]] = Field(default_factory=list)
    # The order is a draft (its header and lines are still being arranged).
    editable: bool = False
    # Allocations can be added, changed and released: the order is open (draft, released, in progress, on hold).
    allocation_open: bool = False
    # Status, actual dates, late flags and the actions this user may take now.
    lifecycle: dict[str, Any] | None = None


class EligibleOrder(BaseModel):
    id: UUID
    production_order_number: str
    status: str
    work_center_name: str | None
    product_type: str
    unit: str
    planned_quantity: Decimal
    planned_start_date: date
    planned_end_date: date


class EligibleDemandItem(BaseModel):
    production_demand_item_id: UUID
    production_demand_id: UUID
    demand_number: str
    customer_name: str | None
    line_no: int
    product_type: str | None
    unit: str
    target_spec_json: dict[str, Any] | None
    required_quantity: Decimal
    remaining_quantity: Decimal
    priority: str | None
    requested_delivery_date: date | None


class AllocationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    production_demand_item_id: UUID
    allocated_quantity: Decimal = Field(gt=0, max_digits=15, decimal_places=3)


class PlanningPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allocations: list[AllocationInput] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_items(self):
        ids = [a.production_demand_item_id for a in self.allocations]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate demand item")
        return self


class AllocationQuantityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allocated_quantity: Decimal = Field(gt=0, max_digits=15, decimal_places=3)


class PlanningOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allocations: list[AllocationInput] = Field(min_length=1, max_length=100)
    work_center_id: UUID
    priority: ProductionOrderPriority = ProductionOrderPriority.NORMAL
    planned_start_date: date
    planned_end_date: date
    notes: str | None = None

    @model_validator(mode="after")
    def validate_request(self):
        ids = [a.production_demand_item_id for a in self.allocations]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate demand item")
        if self.planned_end_date < self.planned_start_date:
            raise ValueError("Invalid date range")
        if sum(a.allocated_quantity for a in self.allocations) >= Decimal("1000000000000"):
            raise ValueError("Quantity exceeds storage precision")
        return self


class ReleaseRequest(BaseModel):
    """Reason is mandatory: a release changes planning history for other planners."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=1, max_length=500)


class TransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    action: Literal["release", "return_to_draft", "start", "hold", "resume", "complete", "close", "cancel"]
    reason: str | None = Field(default=None, max_length=500)
    # The status_version the user saw; a newer one means someone else changed the status first.
    expected_version: int | None = Field(default=None, ge=1)
    # close only: the order produced nothing. Requires a reason; allowed only when no result entries exist.
    zero_output: bool = False


class StatusHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    from_status: str
    to_status: str
    action: str
    trigger: str
    actor_user_id: UUID | None
    actor_name: str | None = None
    reason: str | None
    created_at: ISODatetime
