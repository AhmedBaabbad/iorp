from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.commercial.domain.enums import (
    CommercialOrderStatus,
    CustomerStatus,
    FollowUpStatus,
    InteractionType,
    PriorityLevel,
    QuoteStatus,
    RelationshipStage,
    SampleEvaluationNextAction,
    SampleEvaluationResultStatus,
    SampleStatus,
)


class CustomerCreate(BaseModel):
    customer_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    sector: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=120)
    status: CustomerStatus = CustomerStatus.ACTIVE
    relationship_stage: RelationshipStage = RelationshipStage.LEAD
    opportunity_source: str | None = Field(default=None, max_length=120)
    estimated_consumption: Decimal | None = None
    priority_level: PriorityLevel = PriorityLevel.MEDIUM
    assigned_sales_user_id: UUID | None = None
    notes: str | None = None


class CustomerUpdate(BaseModel):
    customer_code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    sector: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=120)
    status: CustomerStatus | None = None
    relationship_stage: RelationshipStage | None = None
    opportunity_source: str | None = Field(default=None, max_length=120)
    estimated_consumption: Decimal | None = None
    priority_level: PriorityLevel | None = None
    assigned_sales_user_id: UUID | None = None
    notes: str | None = None


class CustomerRead(BaseModel):
    id: UUID
    organization_id: UUID
    customer_code: str
    name: str
    sector: str | None
    city: str | None
    country: str | None
    status: CustomerStatus
    relationship_stage: RelationshipStage
    opportunity_source: str | None
    estimated_consumption: Decimal | None
    priority_level: PriorityLevel
    assigned_sales_user_id: UUID | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


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
    interaction_date: AwareDatetime
    subject: str
    summary: str | None
    outcome: str | None
    next_step_hint: str | None
    created_by_user_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FollowUpCreate(BaseModel):
    interaction_id: UUID | None = None
    assigned_user_id: UUID
    due_date: AwareDatetime
    priority: PriorityLevel = PriorityLevel.MEDIUM
    reason: str = Field(min_length=1, max_length=255)
    notes: str | None = None


class FollowUpComplete(BaseModel):
    completed_at: AwareDatetime | None = None
    notes: str | None = None


class FollowUpRead(BaseModel):
    id: UUID
    customer_id: UUID
    interaction_id: UUID | None
    assigned_user_id: UUID
    due_date: AwareDatetime
    priority: PriorityLevel
    status: FollowUpStatus
    reason: str
    notes: str | None
    completed_at: AwareDatetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SampleCreate(BaseModel):
    sample_code: str = Field(min_length=1, max_length=64)
    product_type: str = Field(min_length=1, max_length=120)
    requested_spec_json: dict[str, Any] | None = None
    quantity_requested: Decimal | None = None
    unit: str | None = Field(default=None, max_length=32)
    request_date: AwareDatetime
    notes: str | None = None


class SampleUpdate(BaseModel):
    sample_code: str | None = Field(default=None, min_length=1, max_length=64)
    product_type: str | None = Field(default=None, min_length=1, max_length=120)
    requested_spec_json: dict[str, Any] | None = None
    quantity_requested: Decimal | None = None
    unit: str | None = Field(default=None, max_length=32)
    request_date: AwareDatetime | None = None
    status: SampleStatus | None = None
    notes: str | None = None


class SampleListItem(BaseModel):
    id: UUID
    customer_id: UUID
    sample_code: str
    product_type: str
    requested_spec_json: dict[str, Any] | None
    quantity_requested: Decimal | None
    unit: str | None
    request_date: AwareDatetime
    status: SampleStatus
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime

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
    evaluation_date: AwareDatetime
    result_status: SampleEvaluationResultStatus
    comments: str | None
    next_action: SampleEvaluationNextAction
    evaluated_by_user_id: UUID
    created_at: datetime

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
    quote_number: str = Field(min_length=1, max_length=64)
    sample_id: UUID | None = None
    issue_date: AwareDatetime
    valid_until: AwareDatetime
    currency: str = Field(default="SAR", min_length=3, max_length=3)
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = None
    items: list[QuoteItemCreate] = Field(min_length=1)


class QuoteUpdate(BaseModel):
    quote_number: str | None = Field(default=None, min_length=1, max_length=64)
    sample_id: UUID | None = None
    issue_date: AwareDatetime | None = None
    valid_until: AwareDatetime | None = None
    status: QuoteStatus | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
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
    issue_date: AwareDatetime
    valid_until: AwareDatetime
    status: QuoteStatus
    currency: str
    subtotal_amount: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime

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
    order_number: str = Field(min_length=1, max_length=64)
    quote_id: UUID | None = None
    order_date: AwareDatetime
    requested_delivery_date: AwareDatetime | None = None
    notes: str | None = None
    items: list[CommercialOrderItemCreate] = Field(min_length=1)


class CommercialOrderUpdate(BaseModel):
    order_number: str | None = Field(default=None, min_length=1, max_length=64)
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
    order_date: AwareDatetime
    status: CommercialOrderStatus
    requested_delivery_date: AwareDatetime | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommercialOrderRead(CommercialOrderListItem):
    notes: str | None
    items: list[CommercialOrderItemRead]
