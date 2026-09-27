from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, computed_field

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
    interaction_type: InteractionType
    interaction_date: AwareDatetime
    subject: str = Field(min_length=1, max_length=255)
    summary: str | None = None
    outcome: str | None = Field(default=None, max_length=255)
    next_step_hint: str | None = Field(default=None, max_length=255)


class CustomerInteractionRead(BaseModel):
    id: UUID
    customer_id: UUID
    interaction_type: InteractionType
    interaction_date: ISOAwareDatetime
    subject: str
    summary: str | None
    outcome: str | None
    next_step_hint: str | None
    created_by_user_id: UUID
    created_at: ISODatetime

    model_config = ConfigDict(from_attributes=True)


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


class SampleCreate(BaseModel):
    product_type: str = Field(min_length=1, max_length=120)
    status: SampleStatus = SampleStatus.REQUESTED
    requested_spec_json: dict[str, Any] | None = None
    is_sample_requested: bool = False
    requested_sample_quantity: Decimal | None = None
    unit: str | None = Field(default=None, max_length=32)
    request_date: AwareDatetime
    notes: str | None = None


class SampleUpdate(BaseModel):
    product_type: str | None = Field(default=None, min_length=1, max_length=120)
    requested_spec_json: dict[str, Any] | None = None
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

    model_config = ConfigDict(from_attributes=True)


class SampleRead(SampleListItem):
    notes: str | None


class SampleEvaluationCreate(BaseModel):
    evaluation_date: AwareDatetime
    result_status: SampleEvaluationResultStatus
    comments: str | None = None
    next_action: SampleEvaluationNextAction


class SampleEvaluationRead(BaseModel):
    id: UUID
    sample_id: UUID
    evaluation_date: ISOAwareDatetime
    result_status: SampleEvaluationResultStatus
    comments: str | None
    next_action: SampleEvaluationNextAction
    evaluated_by_user_id: UUID
    created_at: ISODatetime

    model_config = ConfigDict(from_attributes=True)


class QuoteItemCreate(BaseModel):
    line_no: int = Field(ge=1)
    product_type: str = Field(min_length=1, max_length=120)
    requested_spec_json: dict[str, Any] | None = None
    quantity: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=32)
    unit_price: Decimal = Field(ge=0)


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

    model_config = ConfigDict(from_attributes=True)


class QuoteCreate(BaseModel):
    sample_id: UUID | None = None
    issue_date: AwareDatetime
    valid_until: AwareDatetime
    currency: str = Field(default="SAR", pattern="^(SAR|USD)$")
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = None
    items: list[QuoteItemCreate] = Field(min_length=1)


class QuoteUpdate(BaseModel):
    sample_id: UUID | None = None
    issue_date: AwareDatetime | None = None
    valid_until: AwareDatetime | None = None
    status: QuoteStatus | None = None
    currency: str | None = Field(default=None, pattern="^(SAR|USD)$")
    discount_amount: Decimal | None = Field(default=None, ge=0)
    tax_amount: Decimal | None = Field(default=None, ge=0)
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

    model_config = ConfigDict(from_attributes=True)


class QuoteRead(QuoteListItem):
    notes: str | None
    items: list[QuoteItemRead]


class CommercialOrderItemCreate(BaseModel):
    line_no: int = Field(ge=1)
    product_type: str = Field(min_length=1, max_length=120)
    requested_spec_json: dict[str, Any] | None = None
    quantity: Decimal = Field(gt=0)
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


class CommercialOrderCreate(BaseModel):
    quote_id: UUID | None = None
    order_date: AwareDatetime
    requested_delivery_date: AwareDatetime | None = None
    notes: str | None = None
    items: list[CommercialOrderItemCreate] = Field(min_length=1)


class CommercialOrderUpdate(BaseModel):
    quote_id: UUID | None = None
    order_date: AwareDatetime | None = None
    status: CommercialOrderStatus | None = None
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
    created_by_user_id: UUID
    created_at: ISODatetime
    updated_at: ISODatetime

    model_config = ConfigDict(from_attributes=True)


class CommercialOrderRead(CommercialOrderListItem):
    notes: str | None
    items: list[CommercialOrderItemRead]
