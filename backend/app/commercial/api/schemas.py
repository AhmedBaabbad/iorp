from typing import Annotated
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import AliasChoices, AwareDatetime, BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator, StringConstraints

from app.core.types import ISOAwareDatetime, ISODatetime

from app.commercial.domain.enums import (
    CommercialOrderStatus,
    CustomerStatus,
    FollowUpPriority,
    FollowUpStatus,
    InteractionType,
    PriorityLevel,
    QuoteStatus,
    RelationshipStage,
    SampleDecision,
    SampleEvaluationNextAction,
    SampleEvaluationResultStatus,
    SampleStatus,
)

# MD-003: a key of one of the organization's reference lists (validated against the list by the service).
ListKey = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,59}$")]



class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    sector: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    status: CustomerStatus = CustomerStatus.ACTIVE
    relationship_stage: RelationshipStage = RelationshipStage.LEAD
    opportunity_source: str | None = Field(default=None, max_length=120)
    estimated_consumption: Decimal | None = None
    priority_level: PriorityLevel = PriorityLevel.MEDIUM
    sales_owner_user_id: UUID | None = None
    key_influencer_name: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    sector: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    status: CustomerStatus | None = None
    relationship_stage: RelationshipStage | None = None
    opportunity_source: str | None = Field(default=None, max_length=120)
    estimated_consumption: Decimal | None = None
    priority_level: PriorityLevel | None = None
    sales_owner_user_id: UUID | None = None
    key_influencer_name: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class RoleSummary(BaseModel):
    id: UUID
    code: str
    name: str


class WorkforceSummary(BaseModel):
    id: UUID
    employee_code: str
    worker_type: str
    display_name: str | None


class SalesOwnerSummary(BaseModel):
    id: UUID
    full_name: str
    email: str
    roles: list[RoleSummary] = Field(default_factory=list)
    workforce: WorkforceSummary | None = None


class CreatedBySummary(BaseModel):
    id: UUID
    full_name: str


class EligibleSalesOwnerResponse(BaseModel):
    id: UUID
    full_name: str
    email: str
    status: str
    roles: list[RoleSummary] = Field(default_factory=list)
    workforce: WorkforceSummary | None = None


class CustomerOwnerBulkReassignRequest(BaseModel):
    from_user_id: UUID
    to_user_id: UUID


class CustomerOwnerBulkReassignResponse(BaseModel):
    from_user_id: UUID
    to_user_id: UUID
    reassigned_count: int


class CustomerRead(BaseModel):
    id: UUID
    organization_id: UUID
    customer_code: str
    name: str
    sector: str | None
    city: str | None
    country: str | None
    phone: str | None
    email: str | None
    status: CustomerStatus
    relationship_stage: RelationshipStage
    opportunity_source: str | None
    estimated_consumption: Decimal | None
    priority_level: PriorityLevel
    sales_owner_user_id: UUID | None
    sales_owner: SalesOwnerSummary | None = None
    created_by: CreatedBySummary | None = None
    key_influencer_name: str | None
    notes: str | None
    created_at: ISODatetime
    updated_at: ISODatetime

    model_config = ConfigDict(from_attributes=True)


class CustomerPage(BaseModel):
    """One page of the customer list (core/pagination.py)."""
    items: list[CustomerRead]
    total: int
    page: int
    page_size: int
    pages: int


class CustomerLookupItem(BaseModel):
    """A customer as a picker shows it."""
    id: UUID
    customer_code: str
    name: str
    status: CustomerStatus

    model_config = ConfigDict(from_attributes=True)


class CustomerDeletionImpact(BaseModel):
    production_demands: int = 0
    interactions: int
    follow_ups: int
    samples: int
    quotes: int
    orders: int
    is_blocked: bool


class SampleDeletionImpact(BaseModel):
    evaluations: int
    quotes: int
    is_blocked: bool


class QuoteDeletionImpact(BaseModel):
    items: int
    orders: int
    is_blocked: bool


class OrderDeletionImpact(BaseModel):
    items: int
    is_blocked: bool


class CustomerInteractionCreate(BaseModel):
    interaction_type: ListKey
    interaction_date: AwareDatetime
    subject: str = Field(min_length=1, max_length=255)
    summary: str | None = None
    outcome: str | None = Field(default=None, max_length=255)
    next_step_hint: str | None = Field(default=None, max_length=255)


class CustomerInteractionUpdate(BaseModel):
    interaction_type: ListKey | None = None
    interaction_date: AwareDatetime | None = None
    subject: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = None
    outcome: str | None = Field(default=None, max_length=255)
    next_step_hint: str | None = Field(default=None, max_length=255)


class CustomerInteractionRead(BaseModel):
    id: UUID
    customer_id: UUID
    interaction_type: ListKey
    interaction_date: ISOAwareDatetime
    subject: str
    summary: str | None
    outcome: str | None
    next_step_hint: str | None
    created_by_user_id: UUID
    created_at: ISODatetime

    model_config = ConfigDict(from_attributes=True)


class CustomerInteractionPage(BaseModel):
    items: list[CustomerInteractionRead]
    total: int
    page: int
    page_size: int
    pages: int


class FollowUpCreate(BaseModel):
    interaction_id: UUID | None = None
    assigned_user_id: UUID | None = None
    due_date: AwareDatetime
    priority: FollowUpPriority = FollowUpPriority.MEDIUM
    reason: str = Field(min_length=1, max_length=255)
    notes: str | None = None


class FollowUpUpdate(BaseModel):
    due_date: AwareDatetime | None = None
    priority: FollowUpPriority | None = None
    reason: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = None
    assigned_user_id: UUID | None = None


class FollowUpComplete(BaseModel):
    completed_at: AwareDatetime | None = None
    notes: str | None = None


class FollowUpCustomerSummary(BaseModel):
    id: UUID
    customer_code: str
    customer_name: str


class FollowUpAssignedUser(BaseModel):
    id: UUID
    full_name: str
    email: str
    workforce: WorkforceSummary | None = None


class FollowUpRead(BaseModel):
    id: UUID
    customer: FollowUpCustomerSummary
    interaction_id: UUID | None
    assigned_user_id: UUID | None
    assigned_user: FollowUpAssignedUser | None = None
    created_by: CreatedBySummary | None = None
    due_date: ISOAwareDatetime
    priority: FollowUpPriority
    status: FollowUpStatus
    is_overdue: bool = False
    reason: str
    notes: str | None
    completed_at: ISOAwareDatetime | None
    created_at: ISODatetime
    updated_at: ISODatetime

    @computed_field
    @property
    def is_unassigned(self) -> bool:
        return self.assigned_user_id is None

    model_config = ConfigDict(from_attributes=True)


class FollowUpListResponse(BaseModel):
    items: list[FollowUpRead]
    total: int
    page: int
    page_size: int


class FollowUpBulkReassignRequest(BaseModel):
    from_user_id: UUID
    to_user_id: UUID


class FollowUpBulkReassignResponse(BaseModel):
    from_user_id: UUID
    to_user_id: UUID
    reassigned_count: int


class SampleSpecificationInput(BaseModel):
    @model_validator(mode='before')
    @classmethod
    def unambiguous_specification(cls, data):
        if isinstance(data,dict) and 'property_values' in data and 'requested_spec_json' in data:
            raise ValueError('Supply property_values only; the legacy alias cannot be combined with it.')
        return data


class SampleCreate(SampleSpecificationInput):
    product_type: str = Field(min_length=1, max_length=120)
    status: SampleStatus = SampleStatus.REQUESTED
    requested_spec_json: dict[str, Any] | None = Field(default=None, validation_alias=AliasChoices('property_values','requested_spec_json'))
    is_sample_requested: bool = False
    requested_sample_quantity: Decimal | None = None
    unit: str | None = Field(default=None, max_length=32)
    request_date: AwareDatetime
    notes: str | None = None


class SampleUpdate(SampleSpecificationInput):
    product_type: str | None = Field(default=None, min_length=1, max_length=120)
    requested_spec_json: dict[str, Any] | None = Field(default=None, validation_alias=AliasChoices('property_values','requested_spec_json'))
    is_sample_requested: bool | None = None
    requested_sample_quantity: Decimal | None = None
    unit: str | None = Field(default=None, max_length=32)
    request_date: AwareDatetime | None = None
    status: SampleStatus | None = None
    sample_decision: SampleDecision | None = None
    notes: str | None = None


class SampleListItem(BaseModel):
    id: UUID
    customer_id: UUID
    sample_code: str
    product_type: str
    requested_spec_json: dict[str, Any] | None
    is_sample_requested: bool
    requested_sample_quantity: Decimal | None
    unit: str | None
    request_date: ISOAwareDatetime
    status: SampleStatus
    sample_decision: SampleDecision | None = None
    created_by_user_id: UUID
    created_by_name: str | None = None
    created_at: ISODatetime
    updated_at: ISODatetime
    # On a list page only: the customer, read once for the whole page.
    customer_name: str | None = None
    customer_code: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SamplePage(BaseModel):
    items: list[SampleListItem]
    total: int
    page: int
    page_size: int
    pages: int


class SamplePropertyOption(BaseModel):
    value: str
    label_ar: str
    label_en: str


class SamplePropertyDefinition(BaseModel):
    key: str
    name_ar: str
    name_en: str
    kind: str
    unit: str | None = None
    required: bool = False
    options: list[SamplePropertyOption] = Field(default_factory=list)


class SampleProductDefinition(BaseModel):
    key: str
    name_ar: str
    name_en: str
    active: bool
    default_unit: str | None = None
    properties: list[SamplePropertyDefinition]


class SampleRead(SampleListItem):
    notes: str | None
    product_definition: SampleProductDefinition | None = None

    @computed_field
    @property
    def property_values(self) -> dict[str, Any] | None:
        return self.requested_spec_json


class SampleEvaluationCreate(BaseModel):
    evaluation_date: AwareDatetime
    result_status: SampleEvaluationResultStatus
    comments: str | None = None
    next_action: SampleEvaluationNextAction


class SampleEvaluationUpdate(BaseModel):
    evaluation_date: AwareDatetime | None = None
    result_status: SampleEvaluationResultStatus | None = None
    comments: str | None = None
    next_action: SampleEvaluationNextAction | None = None


class SampleEvaluationRead(BaseModel):
    id: UUID
    sample_id: UUID
    evaluation_date: ISOAwareDatetime
    result_status: SampleEvaluationResultStatus
    comments: str | None
    next_action: SampleEvaluationNextAction
    evaluated_by_user_id: UUID
    evaluated_by_name: str | None = None
    created_at: ISODatetime

    model_config = ConfigDict(from_attributes=True)


class QuoteItemCreate(BaseModel):
    line_no: int = Field(ge=1)
    product_type: str = Field(min_length=1, max_length=120)
    requested_spec_json: dict[str, Any] | None = None
    quantity: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=32)  # a code from commercial/domain/units.py (older free text is kept)
    unit_price: Decimal = Field(ge=0)
    # Percentage of this line taken before VAT (0 = no discount on the line).
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100, max_digits=5, decimal_places=2)
    description_ar: str | None = Field(default=None, max_length=1000)
    description_en: str | None = Field(default=None, max_length=1000)


class QuoteItemRead(BaseModel):
    id: UUID
    quote_id: UUID
    line_no: int
    product_type: str
    requested_spec_json: dict[str, Any] | None
    quantity: Decimal
    unit: str
    unit_price: Decimal
    line_total: Decimal
    discount_percent: Decimal = Decimal("0")
    discount_amount: Decimal = Decimal("0")
    net_total: Decimal | None = None
    description_ar: str | None = None
    description_en: str | None = None

    model_config = ConfigDict(from_attributes=True)


class QuoteCreate(BaseModel):
    sample_id: UUID | None = None
    issue_date: AwareDatetime
    valid_until: AwareDatetime
    currency: str = Field(default="SAR", pattern="^(SAR|USD)$")
    # The discount is a percentage on each line (QuoteItemCreate.discount_percent); the quotation's amount is their sum.
    # With tax_rate (VAT %), the server computes tax_amount and ignores the one sent.
    tax_rate: Decimal | None = Field(default=None, ge=0, le=100)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0)
    attention: str | None = Field(default=None, max_length=255)
    subject: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    items: list[QuoteItemCreate] = Field(min_length=1)


class QuoteUpdate(BaseModel):
    sample_id: UUID | None = None
    issue_date: AwareDatetime | None = None
    valid_until: AwareDatetime | None = None
    # The status changes through issue, accept, reject, expire and revise (SALES-001), never here.
    currency: str | None = Field(default=None, pattern="^(SAR|USD)$")
    tax_rate: Decimal | None = Field(default=None, ge=0, le=100)
    tax_amount: Decimal | None = Field(default=None, ge=0)
    attention: str | None = Field(default=None, max_length=255)
    subject: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    items: list[QuoteItemCreate] | None = Field(default=None, min_length=1)


class QuoteListItem(BaseModel):
    id: UUID
    organization_id: UUID
    customer_id: UUID
    sample_id: UUID | None
    quote_number: str
    issue_date: ISOAwareDatetime
    valid_until: ISOAwareDatetime
    status: QuoteStatus
    currency: str
    subtotal_amount: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    created_by_user_id: UUID
    created_at: ISODatetime
    updated_at: ISODatetime

    customer_name: str | None = None
    customer_code: str | None = None

    model_config = ConfigDict(from_attributes=True)


class StatusHistoryEntry(BaseModel):
    action: str
    from_status: str | None = None
    to_status: str
    revision: int
    reason: str | None = None
    actor_name: str | None = None
    created_at: ISODatetime


class LifecycleReason(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class OptionalReason(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class QuoteOrderSummary(BaseModel):
    id: UUID
    order_number: str
    status: CommercialOrderStatus


class QuotePage(BaseModel):
    items: list[QuoteListItem]
    total: int
    page: int
    page_size: int
    pages: int


class QuoteRead(QuoteListItem):
    revision: int = 1
    allowed_actions: list[str] = Field(default_factory=list)
    history: list[StatusHistoryEntry] = Field(default_factory=list)
    orders: list[QuoteOrderSummary] = Field(default_factory=list)
    notes: str | None
    tax_rate: Decimal | None = None
    attention: str | None = None
    subject: str | None = None
    items: list[QuoteItemRead]


class CommercialOrderItemCreate(BaseModel):
    line_no: int = Field(ge=1)
    product_type: str = Field(min_length=1, max_length=120)
    requested_spec_json: dict[str, Any] | None = None
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    unit: str = Field(min_length=1, max_length=32)
    agreed_unit_price: Decimal | None = Field(default=None, ge=0)


class CommercialOrderItemRead(BaseModel):
    id: UUID
    commercial_order_id: UUID
    line_no: int
    product_type: str
    requested_spec_json: dict[str, Any] | None
    quantity: Decimal
    unit: str
    agreed_unit_price: Decimal | None
    line_total: Decimal | None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("agreed_unit_price")
    @classmethod
    def _price_places(cls, value):
        # Stored with four places for a discounted price (11.4855); a whole-halala price reads as before (2.50).
        if value is None:
            return value
        short = value.quantize(Decimal("0.01"))
        return short if short == value else value.normalize()


class CommercialOrderCreate(BaseModel):
    # Prices are optional; a priced order has a currency (the quotation's, or the organization's default).
    currency: str | None = Field(default=None, pattern='^(SAR|USD)$')
    customer_reference: str | None = Field(default=None, max_length=120)
    quote_id: UUID | None = None
    order_date: AwareDatetime
    requested_delivery_date: AwareDatetime | None = None
    notes: str | None = None
    items: list[CommercialOrderItemCreate] = Field(min_length=1)


class CommercialOrderUpdate(BaseModel):
    """A draft only. The status changes through confirm, revise and cancel (SALES-001)."""
    currency: str | None = Field(default=None, pattern='^(SAR|USD)$')
    customer_reference: str | None = Field(default=None, max_length=120)
    quote_id: UUID | None = None
    order_date: AwareDatetime | None = None
    requested_delivery_date: AwareDatetime | None = None
    notes: str | None = None
    items: list[CommercialOrderItemCreate] | None = Field(default=None, min_length=1)


class CommercialOrderListItem(BaseModel):
    id: UUID
    organization_id: UUID
    customer_id: UUID
    quote_id: UUID | None
    order_number: str
    order_date: ISOAwareDatetime
    status: CommercialOrderStatus
    requested_delivery_date: ISOAwareDatetime | None
    customer_reference: str | None = None
    revision: int = 1
    created_by_user_id: UUID
    created_at: ISODatetime
    updated_at: ISODatetime

    customer_name: str | None = None
    customer_code: str | None = None
    quote_number: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CommercialOrderPage(BaseModel):
    items: list[CommercialOrderListItem]
    total: int
    page: int
    page_size: int
    pages: int


class CommercialOrderRead(CommercialOrderListItem):
    currency: str | None = None
    confirmed_at: ISODatetime | None = None
    confirmed_by_user_id: UUID | None = None
    allowed_actions: list[str] = Field(default_factory=list)
    # {line id: quantity the production demands in force took}; fulfilment: none · partial · full.
    transferred_quantities: dict[str, Decimal] = Field(default_factory=dict)
    fulfilment: str = "none"
    history: list[StatusHistoryEntry] = Field(default_factory=list)
    notes: str | None
    items: list[CommercialOrderItemRead]
