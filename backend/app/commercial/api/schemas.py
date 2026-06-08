from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.commercial.domain.enums import (
    CustomerStatus,
    FollowUpStatus,
    InteractionType,
    PriorityLevel,
    RelationshipStage,
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

