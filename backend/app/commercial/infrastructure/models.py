from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.commercial.domain.enums import (
    CustomerStatus,
    FollowUpStatus,
    InteractionType,
    PriorityLevel,
    RelationshipStage,
)
from app.core.db import Base
from app.core.utils import utc_now


def enum_values(
    enum_class: (
        type[CustomerStatus]
        | type[RelationshipStage]
        | type[PriorityLevel]
        | type[InteractionType]
        | type[FollowUpStatus]
    ),
) -> list[str]:
    return [item.value for item in enum_class]


class Customer(Base):
    __tablename__ = "commercial_customers"
    __table_args__ = (
        UniqueConstraint("organization_id", "customer_code", name="uq_commercial_customers_org_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_organizations.id"),
        nullable=False,
        index=True,
    )
    customer_code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(120), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[CustomerStatus] = mapped_column(
        Enum(CustomerStatus, name="customer_status", values_callable=enum_values),
        nullable=False,
        default=CustomerStatus.ACTIVE,
    )
    relationship_stage: Mapped[RelationshipStage] = mapped_column(
        Enum(RelationshipStage, name="customer_relationship_stage", values_callable=enum_values),
        nullable=False,
        default=RelationshipStage.LEAD,
    )
    opportunity_source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    estimated_consumption: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    priority_level: Mapped[PriorityLevel] = mapped_column(
        Enum(PriorityLevel, name="customer_priority_level", values_callable=enum_values),
        nullable=False,
        default=PriorityLevel.MEDIUM,
    )
    assigned_sales_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_users.id"),
        nullable=True,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class CustomerInteraction(Base):
    __tablename__ = "commercial_customer_interactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("commercial_customers.id"),
        nullable=False,
        index=True,
    )
    interaction_type: Mapped[InteractionType] = mapped_column(
        Enum(InteractionType, name="customer_interaction_type", values_callable=enum_values),
        nullable=False,
    )
    interaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(255), nullable=True)
    next_step_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_users.id"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class FollowUp(Base):
    __tablename__ = "commercial_follow_ups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("commercial_customers.id"),
        nullable=False,
        index=True,
    )
    interaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("commercial_customer_interactions.id"),
        nullable=True,
        index=True,
    )
    assigned_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_users.id"),
        nullable=False,
        index=True,
    )
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    priority: Mapped[PriorityLevel] = mapped_column(
        Enum(PriorityLevel, name="follow_up_priority", values_callable=enum_values),
        nullable=False,
        default=PriorityLevel.MEDIUM,
    )
    status: Mapped[FollowUpStatus] = mapped_column(
        Enum(FollowUpStatus, name="follow_up_status", values_callable=enum_values),
        nullable=False,
        default=FollowUpStatus.PENDING,
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
