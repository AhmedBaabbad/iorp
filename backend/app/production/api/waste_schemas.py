"""Request and response shapes for operational waste records (PROD-WASTE-001)."""
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.types import ISODatetime
from app.production.domain.enums import WasteCategory

QUANTITY = dict(max_digits=15, decimal_places=3)


class WasteCategoryLine(BaseModel):
    """One category of a record and its share of the quantity; the share may be left out when it is the only one."""
    model_config = ConfigDict(extra="forbid")
    category: WasteCategory
    quantity: Decimal | None = Field(default=None, **QUANTITY)


class WasteCategoryLineRead(BaseModel):
    category: WasteCategory
    quantity: Decimal

    model_config = ConfigDict(from_attributes=True)


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
    # One or more categories; their quantities add up to quantity_wasted (a single one may omit its quantity).
    categories: list[WasteCategoryLine] = Field(min_length=1, max_length=8)
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
    # Replaces all the record's categories. Left out, a single category follows a changed quantity.
    categories: list[WasteCategoryLine] | None = Field(default=None, min_length=1, max_length=8)
    reason_code: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def reject_null_required_values(self):
        for field in ("waste_date", "quantity_wasted", "unit", "categories"):
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
    # Largest share first; the shares add up to quantity_wasted, in the record's unit.
    categories: list[WasteCategoryLineRead]
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
