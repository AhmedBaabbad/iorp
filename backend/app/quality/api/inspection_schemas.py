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
    return_id: UUID | None = None
    return_line_id: UUID | None = None
    return_source: "ReturnSource | None" = None
    receipt_id: UUID | None = None
    receipt_line_id: UUID | None = None
    incoming_source: "IncomingSource | None" = None
    actions: list[str] = []
    # The defects found on this inspection (one per type, with how many) and the highest severity among them.
    defects: list["CheckDefect"] = []
    severity: str | None = None
    created_at: ISODatetime
    updated_at: ISODatetime


class CheckDefect(BaseModel):
    defect_category: str
    severity: str
    defect_count: int


class IncomingSource(BaseModel):
    """The received lot an incoming inspection is about (QUAL-INC-001), read from procurement."""
    receipt_id: UUID
    receipt_no: str
    receipt_date: date
    supplier_id: UUID
    supplier_name: str
    line_no: int
    description: str
    material_code: str | None
    supplier_lot: str | None
    spec_product_type: str | None


class ReturnSource(BaseModel):
    """The returned goods an inspection is about (QUAL-RET-001), read from shipping."""
    return_id: UUID
    return_no: str
    kind: str
    reason: str
    responsibility: str
    details: str | None
    shipment_id: UUID
    shipment_no: str
    customer_name: str
    line_no: int
    description: str
    production_order_no: str | None


class MeasurementRead(BaseModel):
    """A plan line of the inspection (QUAL-SPEC-001): limits resolved for the lot, readings and the verdict."""
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    position: int
    parameter_code: str
    name_ar: str
    name_en: str
    kind: str
    unit: str | None
    method: str | None
    requirement: str | None
    acceptance: str | None
    target: Decimal | None
    lower_limit: Decimal | None
    upper_limit: Decimal | None
    readings_required: int
    readings: list[str] | None
    attribute_result: str | None
    observation: str | None
    reading_count: int
    minimum: Decimal | None
    maximum: Decimal | None
    mean: Decimal | None
    status: str
    measured_at: ISODatetime | None


class QualityCheckRead(QualityCheckListItem):
    notes: str | None
    started_at: ISODatetime | None
    closed_at: ISODatetime | None
    closed_by_name: str | None = None
    cancel_reason: str | None
    specification_id: UUID | None = None
    specification_code: str | None = None
    specification_revision: int | None = None
    lot_values: dict[str, str] | None = None
    history: list[HistoryEntry] = []
    rejections: list[CheckRejectionSummary] = []
    measurements: list[MeasurementRead] = []


class PlanInput(_Input):
    specification_id: UUID
    # Values the order line lacks, e.g. {"width_mm": "5", "thickness_mm": "0.35"}; the order line's own values win.
    lot_values: dict[str, str] | None = Field(default=None, max_length=20)


class PlanCandidate(BaseModel):
    """A specification in force the check can take: whether it is for the order's product, and the lot values it still needs."""
    id: UUID
    code: str
    revision: int
    title: str
    product_type: str
    grade: str | None
    matches_product: bool
    missing_keys: list[str]


class MeasurementInput(_Input):
    # Numeric parameters: the readings as typed ("5.02"); attributes: conforming / nonconforming.
    readings: list[str] = Field(default_factory=list, max_length=50)
    attribute_result: str | None = Field(default=None, pattern="^(conforming|nonconforming)$")
    observation: str | None = Field(default=None, max_length=255)


# ── rejections ────────────────────────────────────────────────────────────────────────────────
class RejectionDefectInput(_Input):
    # A defect recorded on the rejection's inspection; how many of the rejected units it affects is optional.
    quality_defect_id: UUID
    affected_quantity: Quantity | None = Field(default=None, gt=0, decimal_places=3, max_digits=15)


class RejectionDefect(BaseModel):
    quality_defect_id: UUID
    defect_category: str
    severity: str
    defect_count: int
    description: str
    # Per defect only: defects overlap (one unit may carry several), so these are never added up.
    affected_quantity: Decimal | None = None


class QualityRejectionCreate(_Input):
    # From a closed check (order, line, unit and quantity limit come from it) or for a named order.
    quality_check_id: UUID | None = None
    production_order_id: UUID | None = None
    production_order_item_id: UUID | None = None
    # The defects of the inspection this rejection is made for (none, one or several; each once).
    defects: list[RejectionDefectInput] = Field(default_factory=list, max_length=50)
    rejection_date: date
    rejection_reason: RejectionReason
    rejection_notes: str = Field(min_length=1, max_length=2000)
    quantity_rejected: Quantity = Field(gt=0, decimal_places=3, max_digits=14)


class QualityRejectionUpdate(_Input):
    rejection_date: date | None = None
    rejection_reason: RejectionReason | None = None
    rejection_notes: str | None = Field(default=None, max_length=2000)
    quantity_rejected: Quantity | None = Field(default=None, gt=0, decimal_places=3, max_digits=14)
    # Replaces the rejection's defects while it is pending.
    defects: list[RejectionDefectInput] | None = Field(default=None, max_length=50)


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
    return_id: UUID | None = None
    return_no: str | None = None
    unresolved: bool = False
    actions: list[str] = []
    # The highest severity among the rejection's defects (critical > major > minor); null without defects.
    severity: str | None = None
    defects: list[RejectionDefect] = []
    created_at: ISODatetime


class QualityRejectionRead(QualityRejectionListItem):
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


# ── returned goods (QUAL-RET-001) ─────────────────────────────────────────────────────────────
Part = Field(default=Decimal("0"), ge=0, decimal_places=3, max_digits=14)


class ReturnDecision(_Input):
    """Where the inspected quantity goes; the parts add up to it."""
    to_stock: Quantity = Part
    use_as_is: Quantity = Part  # second grade, under a concession
    rework: Quantity = Part
    return_to_process: Quantity = Part  # ground and fed back to the process
    scrap: Quantity = Part  # هالك
    hold: Quantity = Part
    notes: str | None = Field(default=None, max_length=2000)
    concession_approved_by: str | None = Field(default=None, max_length=255)
    open_ncr: bool = False


class AwaitingReturnLine(BaseModel):
    line_id: UUID
    line_no: int
    description: str
    width_mm: Decimal | None
    thickness_mm: Decimal | None
    unit: str
    production_order_id: UUID | None
    production_order_no: str | None
    received_quantity: Decimal | None
    inspection_id: UUID | None
    inspection_code: str | None
    inspection_status: str | None


class AwaitingReturn(BaseModel):
    return_id: UUID
    return_no: str
    kind: str
    reason: str
    responsibility: str
    details: str | None
    customer_name: str
    received_at: ISODatetime | None
    shipment_id: UUID
    shipment_no: str
    lines: list[AwaitingReturnLine]


class BatchShipment(BaseModel):
    """A delivery note that carried the same production order (containment)."""
    shipment_id: UUID
    shipment_no: str
    status: str
    shipment_date: date
    customer_name: str
    quantity: Decimal
    delivered_quantity: Decimal | None
    unit: str


# ── incoming inspection (QUAL-INC-001) ────────────────────────────────────────────────────────
class LotDecision(_Input):
    """Where the inspected lot goes; the parts add up to it. Anything not released opens a non-conformance report."""
    released: Quantity = Part
    use_as_is: Quantity = Part  # under a concession
    sort: Quantity = Part  # sorted and re-inspected
    return_to_supplier: Quantity = Part
    scrap: Quantity = Part
    hold: Quantity = Part
    notes: str | None = Field(default=None, max_length=2000)
    concession_approved_by: str | None = Field(default=None, max_length=255)


class AwaitingLot(BaseModel):
    line_id: UUID
    line_no: int
    description: str
    material_code: str | None
    spec_product_type: str | None
    supplier_lot: str | None
    quantity: Decimal
    unit: str
    inspection_id: UUID | None
    inspection_code: str | None
    inspection_status: str | None


class AwaitingReceipt(BaseModel):
    receipt_id: UUID
    receipt_no: str
    receipt_date: date
    received_at: ISODatetime | None
    supplier_id: UUID
    supplier_name: str
    supplier_delivery_no: str | None
    lines: list[AwaitingLot]
