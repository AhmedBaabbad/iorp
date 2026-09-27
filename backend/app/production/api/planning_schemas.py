from datetime import date
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.production.domain.enums import ProductionOrderPriority
from app.production.api.schemas import ProductionOrderRead
from typing import Any


class PlanningOrderRead(ProductionOrderRead):
    allocations: list[dict[str, Any]] = Field(default_factory=list)
    # Sum of ACTIVE allocations; equals planned_quantity until the order is cancelled.
    active_allocated_quantity: Decimal = Decimal(0)


class AllocationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    production_demand_item_id: UUID
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
