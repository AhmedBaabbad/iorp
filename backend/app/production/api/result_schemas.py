"""Request and response shapes for the final order result (PROD-OUTPUT-001)."""
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.types import ISODatetime
from app.production.domain.enums import ResultDisposition

QUANTITY = dict(max_digits=15, decimal_places=3)


class ResultEntryCreate(BaseModel):
    """organization_id is never accepted: it comes from the signed-in user."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    # Optional for single-item orders (auto-assigned), required for multi-item orders.
    production_order_item_id: UUID | None = None
    disposition: ResultDisposition
    quantity: Decimal = Field(gt=0, **QUANTITY)
    # Optional; when sent it must equal the order item's unit.
    unit: str | None = Field(default=None, max_length=32)
    secondary_quantity: Decimal | None = Field(default=None, gt=0, **QUANTITY)
    secondary_unit: str | None = Field(default=None, min_length=1, max_length=32)
    # Required for samples; forced by the server for every other disposition.
    counts_as_loss: bool | None = None
    reason_code: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=2000)


class ResultEntryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    production_order_item_id: UUID | None = None
    disposition: ResultDisposition | None = None
    quantity: Decimal | None = Field(default=None, gt=0, **QUANTITY)
    unit: str | None = Field(default=None, max_length=32)
    secondary_quantity: Decimal | None = Field(default=None, gt=0, **QUANTITY)
    secondary_unit: str | None = Field(default=None, min_length=1, max_length=32)
    counts_as_loss: bool | None = None
    reason_code: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def reject_null_required_values(self):
        for field in ("disposition", "quantity"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ResultCorrectionCreate(BaseModel):
    """Signed delta against an original entry; disposition, item and unit are the original's."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    quantity: Decimal = Field(**QUANTITY)
    secondary_quantity: Decimal | None = Field(default=None, **QUANTITY)
    correction_reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def non_zero(self):
        if self.quantity == 0:
            raise ValueError("quantity cannot be zero")
        return self


class ResultEntryRead(BaseModel):
    id: UUID
    production_order_item_id: UUID | None
    line_no: int | None
    disposition: ResultDisposition
    quantity: Decimal
    unit: str
    secondary_quantity: Decimal | None
    secondary_unit: str | None
    counts_as_loss: bool
    reason_code: str | None
    notes: str | None
    entry_type: str
    corrects_entry_id: UUID | None
    correction_reason: str | None
    created_by_user_id: UUID
    created_by_name: str | None
    updated_by_user_id: UUID | None
    created_at: ISODatetime
    updated_at: ISODatetime


class ResultOriginalRead(ResultEntryRead):
    effective_quantity: Decimal
    corrections: list[ResultEntryRead]
    actions: list[str]


class OrderResultRead(BaseModel):
    order: dict[str, Any]
    available: bool
    editable: bool
    locked: bool
    allocation_level: str
    items: list[dict[str, Any]]
    totals: list[dict[str, Any]]
    entries: list[ResultOriginalRead]
    close_check: dict[str, Any]
    actions: list[str]


class ResultOverviewRow(BaseModel):
    id: UUID
    number: str
    status: str
    product_type: str
    entry_count: int
    correction_count: int
    # Completed orders only: every item has an entry, so the order can be closed.
    ready_to_close: bool
    totals: list[dict[str, Any]]
