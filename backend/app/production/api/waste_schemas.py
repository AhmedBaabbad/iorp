"""Request and response shapes for operational waste records (PROD-WASTE-001)."""
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.types import ISODatetime
from app.production.domain.enums import WasteCategory

QUANTITY = dict(max_digits=15, decimal_places=3)


class WasteRecordCreate(BaseModel):
    """organization_id never comes from the body; the work center defaults to the run's, then the order's."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    production_order_id: UUID
    production_order_item_id: UUID | None = None
    production_run_id: UUID | None = None
    work_center_id: UUID | None = None
    waste_date: date
    quantity_wasted: Decimal = Field(gt=0, **QUANTITY)
    unit: str = Field(min_length=1, max_length=32)
    waste_category: WasteCategory
    reason_code: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)


class WasteRecordUpdate(BaseModel):
    """The order cannot change: a record moved to another order is deleted and recorded there."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    production_order_item_id: UUID | None = None
    production_run_id: UUID | None = None
    work_center_id: UUID | None = None
    waste_date: date | None = None
    quantity_wasted: Decimal | None = Field(default=None, gt=0, **QUANTITY)
    unit: str | None = Field(default=None, min_length=1, max_length=32)
    waste_category: WasteCategory | None = None
    reason_code: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def reject_null_required_values(self):
        for field in ("waste_date", "quantity_wasted", "unit", "waste_category"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class WasteRecordListItem(BaseModel):
    id: UUID
    organization_id: UUID
    production_order_id: UUID
    production_order_item_id: UUID | None
    production_run_id: UUID | None
    work_center_id: UUID
    waste_date: date
    quantity_wasted: Decimal
    # A code of app/core/units.py; on a record flagged at migration, the text as written until a unit is chosen.
    unit: str
    # The unit as it was written before units became codes (kept for history); unit_needs_review: it matched no code.
    legacy_unit_text: str | None = None
    unit_needs_review: bool = False
    waste_category: WasteCategory
    reason_code: str | None
    created_by_user_id: UUID
    updated_by_user_id: UUID | None
    created_at: ISODatetime
    updated_at: ISODatetime
    # Display labels and the actions this user may take now (edit/delete), filled by the routes.
    labels: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class WasteRecordRead(WasteRecordListItem):
    notes: str | None


class WasteSummaryRead(BaseModel):
    order: dict[str, Any]
    available: bool
    locked: bool
    totals: list[dict[str, Any]]
    by_category: list[dict[str, Any]]
    actions: list[str]
