"""Quality check and rejection API (QUAL-001). Errors answer {"code": ...} like production."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.types import ISODatetime
from app.quality.domain.enums import (
    Disposition, DispositionStatus, QualityCheckResult, QualityCheckStatus, QualityCheckType, RejectionReason,
)

Quantity = Decimal  # three decimals, in the inspected line's unit


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ── checks ────────────────────────────────────────────────────────────────────────────────────
class QualityCheckCreate(_Input):
    check_type: QualityCheckType
    production_order_id: UUID | None = None
    production_order_item_id: UUID | None = None
    sample_id: UUID | None = None
    check_datetime: datetime
    # The sample size can be known before the inspection; accepted/rejected are given when closing.
    qty_inspected: Quantity = Field(default=Decimal("0"), ge=0, decimal_places=3, max_digits=14)
    notes: str | None = Field(default=None, max_length=2000)


class QualityCheckUpdate(_Input):
    check_type: QualityCheckType | None = None
    production_order_item_id: UUID | None = None
    sample_id: UUID | None = None
    check_datetime: datetime | None = None
    qty_inspected: Quantity | None = Field(default=None, ge=0, decimal_places=3, max_digits=14)
    notes: str | None = Field(default=None, max_length=2000)


class QualityCheckClose(_Input):
    result: QualityCheckResult
    qty_inspected: Quantity = Field(gt=0, decimal_places=3, max_digits=14)
    qty_accepted: Quantity = Field(ge=0, decimal_places=3, max_digits=14)
    qty_rejected: Quantity = Field(ge=0, decimal_places=3, max_digits=14)
    notes: str | None = Field(default=None, max_length=2000)
    # Reason of the rejection opened for the rejected quantity (default: failed quality check).
    rejection_reason: RejectionReason | None = None


class ReasonInput(_Input):
    reason: str = Field(min_length=1, max_length=1000)


class HistoryEntry(BaseModel):
    action: str
    from_status: str | None
    to_status: str
    reason: str | None
    detail: dict | None
    actor_name: str | None
    at: ISODatetime


class CheckRejectionSummary(BaseModel):
    id: UUID
    rejection_code: str
    disposition_status: DispositionStatus
    disposition: Disposition | None
    quantity_rejected: Decimal
    unit: str


class QualityCheckListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    inspection_code: str
    check_type: QualityCheckType
    status: QualityCheckStatus
    result: QualityCheckResult | None
    check_datetime: ISODatetime
    production_order_id: UUID | None
    production_order_item_id: UUID | None
    sample_id: UUID | None
    qty_inspected: Decimal
    qty_accepted: Decimal
    qty_rejected: Decimal
    unit: str | None
    order_number: str | None = None
    item_line_no: int | None = None
    sample_code: str | None = None
    checked_by_name: str | None = None
    actions: list[str] = []
    created_at: ISODatetime
    updated_at: ISODatetime


class QualityCheckRead(QualityCheckListItem):
    notes: str | None
    started_at: ISODatetime | None
    closed_at: ISODatetime | None
    closed_by_name: str | None = None
    cancel_reason: str | None
    history: list[HistoryEntry] = []
    rejections: list[CheckRejectionSummary] = []


# ── rejections ────────────────────────────────────────────────────────────────────────────────
class QualityRejectionCreate(_Input):
    # From a closed check (order, line, unit and quantity limit come from it) or for a named order.
    quality_check_id: UUID | None = None
    production_order_id: UUID | None = None
    production_order_item_id: UUID | None = None
    quality_defect_id: UUID | None = None
    rejection_date: date
    rejection_reason: RejectionReason
    rejection_notes: str = Field(min_length=1, max_length=2000)
    quantity_rejected: Quantity = Field(gt=0, decimal_places=3, max_digits=14)


class QualityRejectionUpdate(_Input):
    rejection_date: date | None = None
    rejection_reason: RejectionReason | None = None
    rejection_notes: str | None = Field(default=None, max_length=2000)
    quantity_rejected: Quantity | None = Field(default=None, gt=0, decimal_places=3, max_digits=14)


class RejectionDecision(_Input):
    disposition: Disposition
    decision_notes: str | None = Field(default=None, max_length=2000)
    # Required with use_as_is: who approved the concession (e.g. the customer's representative).
    concession_approved_by: str | None = Field(default=None, max_length=255)


class RejectionExecution(_Input):
    execution_notes: str | None = Field(default=None, max_length=2000)


class QualityRejectionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    rejection_code: str
    quality_check_id: UUID | None
    production_order_id: UUID | None
    production_order_item_id: UUID | None
    rejection_date: date
    rejection_reason: RejectionReason
    disposition: Disposition | None
    disposition_status: DispositionStatus
    quantity_rejected: Decimal
    unit: str
    order_number: str | None = None
    item_line_no: int | None = None
    inspection_code: str | None = None
    unresolved: bool = False
    actions: list[str] = []
    created_at: ISODatetime


class QualityRejectionRead(QualityRejectionListItem):
    quality_defect_id: UUID | None
    rejection_notes: str
    rejected_by_name: str | None = None
    decision_notes: str | None
    concession_approved_by: str | None
    decided_at: ISODatetime | None
    decided_by_name: str | None = None
    execution_notes: str | None
    executed_at: ISODatetime | None
    executed_by_name: str | None = None
    history: list[HistoryEntry] = []
    updated_at: ISODatetime


# ── lookups ───────────────────────────────────────────────────────────────────────────────────
class OrderLine(BaseModel):
    id: UUID
    line_no: int
    unit: str
    planned_quantity: Decimal
    spec: dict | None = None


class InspectableOrder(BaseModel):
    id: UUID
    number: str
    product_type: str
    status: str
    unit: str
    items: list[OrderLine]


class SampleOption(BaseModel):
    id: UUID
    code: str
    product_type: str
    unit: str | None
    customer: str
