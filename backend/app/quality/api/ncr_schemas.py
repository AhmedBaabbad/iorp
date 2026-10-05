"""Non-conformance report API (QUAL-NCR-002). Create/Update never accept organization scope; errors answer {"code": ...}."""
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.types import ISODatetime
from app.core.units import UNITS
from app.quality.domain import ncr as N
from app.quality.domain.enums import NCRReportType, NCRSourceType

Severity = Literal["minor", "major", "critical"]
Disposition = Literal["return_to_supplier", "use_as_is", "sort", "rework", "regrade", "return_to_process", "scrap", "hold"]
SupplierAction = Literal["none", "notify", "return_goods", "scar"]
ClaimStatus = Literal["none", "claimed", "accepted", "rejected", "recovered"]
Category = Literal["man", "machine", "material", "method", "measurement", "environment"]
Method = Literal["five_whys", "fishbone", "other"]
ActionKind = Literal["correction", "corrective", "preventive"]
assert set(Severity.__args__) == set(N.SEVERITIES) and set(Disposition.__args__) == set(N.DISPOSITIONS)
assert set(SupplierAction.__args__) == set(N.SUPPLIER_ACTIONS) and set(ClaimStatus.__args__) == set(N.CLAIM_STATUSES)
assert set(Category.__args__) == set(N.ROOT_CAUSE_CATEGORIES) and set(ActionKind.__args__) == set(N.ACTION_KINDS)

Money = Field(default=None, ge=0, max_digits=14, decimal_places=2)
Text = Field(default=None, max_length=4000)


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ItemInput(_Input):
    item_name: str = Field(min_length=1, max_length=255)
    item_reference: str | None = Field(default=None, max_length=255)
    quantity_affected: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    unit: str | None = Field(default=None, max_length=32)
    issue_description: str = Field(min_length=1, max_length=4000)
    disposition: Disposition | None = None
    disposition_notes: str | None = Text
    notes: str | None = Text

    @field_validator("unit")
    @classmethod
    def known_unit(cls, value):
        if value and value not in UNITS:
            raise ValueError("UNIT_UNKNOWN")
        return value or None


class ItemUpdate(ItemInput):
    item_name: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore[assignment]
    issue_description: str | None = Field(default=None, min_length=1, max_length=4000)  # type: ignore[assignment]


class _Header(_Input):
    reference_code: str | None = Field(default=None, max_length=255)
    quality_check_id: UUID | None = None
    quality_rejection_id: UUID | None = None
    production_order_id: UUID | None = None
    customer_name: str | None = Field(default=None, max_length=255)
    supplier_id: UUID | None = None  # a registered supplier (procurement); its name is copied
    supplier_name: str | None = Field(default=None, max_length=255)
    supplier_reference: str | None = Field(default=None, max_length=120)
    owner_user_id: UUID | None = None
    due_date: date | None = None
    supplier_action: SupplierAction | None = None
    supplier_response: str | None = Text
    supplier_responded_at: date | None = None
    cost_material: Decimal | None = Money
    cost_labor: Decimal | None = Money
    cost_scrap: Decimal | None = Money
    cost_transport: Decimal | None = Money
    cost_other: Decimal | None = Money
    claim_amount: Decimal | None = Money
    claim_status: ClaimStatus | None = None


class NCRCreate(_Header):
    report_date: date
    source_type: NCRSourceType
    report_type: NCRReportType
    severity: Severity = "major"
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=8000)
    items: list[ItemInput] = Field(default_factory=list, max_length=50)


class NCRUpdate(_Header):
    report_date: date | None = None
    source_type: NCRSourceType | None = None
    report_type: NCRReportType | None = None
    severity: Severity | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=8000)


class ContainInput(_Input):
    containment: str = Field(min_length=1, max_length=4000)


class InvestigateInput(_Input):
    root_cause_category: Category
    root_cause_method: Method | None = None
    root_cause: str = Field(min_length=1, max_length=8000)
    action_required: bool = True
    no_action_justification: str | None = Text


class VerifyInput(_Input):
    effective: bool
    notes: str | None = Text
    # QUAL-CAPA-001: review the effectiveness again this many days after closing (0: no later review).
    review_days: int = Field(0, ge=0, le=365)


class ReviewInput(_Input):
    effective: bool
    notes: str | None = Text


class ReasonInput(_Input):
    reason: str = Field(min_length=1, max_length=2000)


class ActionInput(_Input):
    kind: ActionKind
    description: str = Field(min_length=1, max_length=4000)
    owner_user_id: UUID | None = None
    owner_name: str | None = Field(default=None, max_length=200)
    due_date: date | None = None


class ActionUpdate(_Input):
    kind: ActionKind | None = None
    description: str | None = Field(default=None, min_length=1, max_length=4000)
    owner_user_id: UUID | None = None
    owner_name: str | None = Field(default=None, max_length=200)
    due_date: date | None = None


class EvidenceInput(_Input):
    evidence: str = Field(min_length=1, max_length=4000)


class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    line_no: int
    item_name: str
    item_reference: str | None
    quantity_affected: Decimal | None
    unit: str | None
    issue_description: str
    disposition: str | None
    disposition_notes: str | None
    notes: str | None


class ActionRead(BaseModel):
    id: UUID
    ncr_id: UUID
    line_no: int
    kind: str
    description: str
    owner_user_id: UUID | None
    owner_name: str | None
    due_date: date | None
    status: str
    evidence: str | None
    completed_at: ISODatetime | None
    completed_by_name: str | None
    cancel_reason: str | None
    overdue: bool
    report_number: str | None = None
    report_title: str | None = None
    report_status: str | None = None


class AttachmentRead(BaseModel):
    id: UUID
    file_name: str
    content_type: str
    size_bytes: int
    uploaded_by_name: str | None
    uploaded_at: ISODatetime


class HistoryEntry(BaseModel):
    action: str
    from_status: str | None
    to_status: str
    reason: str | None
    detail: dict | None = None
    actor_name: str | None
    at: ISODatetime


class RelatedReport(BaseModel):
    id: UUID
    report_number: str
    report_date: date
    title: str
    status: str
    severity: str
    matched_on: list[str]
    earlier: bool


class Recurrence(BaseModel):
    window_days: int
    earlier: int
    since_closing: int
    recurring: bool
    related: list[RelatedReport]


class AlertItem(BaseModel):
    kind: str
    ncr_id: UUID
    report_number: str
    title: str
    due_date: date | None


class Alerts(BaseModel):
    total: int
    open_actions: int
    overdue: int
    report_overdue: int
    review_due: int
    due_soon: int
    items: list[AlertItem]


class NCRListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    report_number: str
    report_date: date
    source_type: NCRSourceType
    report_type: NCRReportType
    status: str
    severity: str
    title: str
    reference_code: str | None
    supplier_name: str | None
    customer_name: str | None
    owner_user_id: UUID | None
    owner_name: str | None = None
    due_date: date | None
    overdue: bool = False
    open_actions: int = 0
    overdue_actions: int = 0
    total_cost: Decimal | None = None
    review_pending: bool = False
    review_due: bool = False
    actions: list[str] = []
    created_at: ISODatetime


class NCRRead(NCRListItem):
    description: str
    quality_check_id: UUID | None
    quality_rejection_id: UUID | None
    production_order_id: UUID | None
    return_id: UUID | None
    supplier_id: UUID | None
    supplier_reference: str | None
    inspection_code: str | None = None
    rejection_code: str | None = None
    order_number: str | None = None
    return_no: str | None = None
    detected_by_name: str | None = None
    containment: str | None
    contained_at: ISODatetime | None
    contained_by_name: str | None = None
    root_cause_category: str | None
    root_cause_method: str | None
    root_cause: str | None
    action_required: bool | None
    no_action_justification: str | None
    investigated_at: ISODatetime | None
    investigated_by_name: str | None = None
    verification_attempts: int
    verification_notes: str | None
    verified_at: ISODatetime | None
    verified_by_name: str | None = None
    closed_at: ISODatetime | None
    cancel_reason: str | None
    effectiveness_due_date: date | None
    effectiveness_result: str | None
    effectiveness_notes: str | None
    effectiveness_reviewed_at: ISODatetime | None
    effectiveness_reviewed_by_name: str | None = None
    recurrence: Recurrence | None = None
    supplier_action: str
    supplier_response: str | None
    supplier_responded_at: date | None
    cost_material: Decimal | None
    cost_labor: Decimal | None
    cost_scrap: Decimal | None
    cost_transport: Decimal | None
    cost_other: Decimal | None
    claim_amount: Decimal | None
    claim_status: str
    items: list[ItemRead] = []
    corrective_actions: list[ActionRead] = []
    attachments: list[AttachmentRead] = []
    history: list[HistoryEntry] = []
    can_complete_actions: bool = False
    updated_at: ISODatetime


class SupplierOption(BaseModel):
    id: UUID
    supplier_code: str
    name: str
    status: str


class UserOption(BaseModel):
    id: UUID
    name: str
