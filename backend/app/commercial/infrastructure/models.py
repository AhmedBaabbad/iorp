from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy import JSON, DateTime, Enum as SqlEnum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
from app.core.db import Base
from app.core.utils import TZDateTime, enum_values, utc_now


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
        SqlEnum(CustomerStatus, name="customer_status", values_callable=enum_values),
        nullable=False,
        default=CustomerStatus.ACTIVE,
    )
    relationship_stage: Mapped[RelationshipStage] = mapped_column(
        SqlEnum(RelationshipStage, name="customer_relationship_stage", values_callable=enum_values),
        nullable=False,
        default=RelationshipStage.LEAD,
    )
    opportunity_source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    estimated_consumption: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    priority_level: Mapped[PriorityLevel] = mapped_column(
        SqlEnum(PriorityLevel, name="customer_priority_level", values_callable=enum_values),
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


class Sample(Base):
    __tablename__ = "commercial_samples"

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
    sample_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    product_type: Mapped[str] = mapped_column(String(120), nullable=False)
    requested_spec_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)  # customer-facing commercial spec only
    quantity_requested: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    request_date: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    status: Mapped[SampleStatus] = mapped_column(
        SqlEnum(SampleStatus, name="sample_status", values_callable=enum_values),
        nullable=False,
        default=SampleStatus.REQUESTED,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


# Commercial journey outcome only — structured quality/defect data belongs in app/quality/
class SampleEvaluation(Base):
    __tablename__ = "commercial_sample_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    sample_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("commercial_samples.id"),
        nullable=False,
        index=True,
    )
    evaluation_date: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    result_status: Mapped[SampleEvaluationResultStatus] = mapped_column(
        SqlEnum(
            SampleEvaluationResultStatus,
            name="sample_evaluation_result_status",
            values_callable=enum_values,
        ),
        nullable=False,
    )
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_action: Mapped[SampleEvaluationNextAction] = mapped_column(
        SqlEnum(
            SampleEvaluationNextAction,
            name="sample_evaluation_next_action",
            values_callable=enum_values,
        ),
        nullable=False,
    )
    evaluated_by_user_id: Mapped[uuid.UUID] = mapped_column(
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


class Quote(Base):
    __tablename__ = "commercial_quotes"
    __table_args__ = (
        UniqueConstraint("organization_id", "quote_number", name="uq_commercial_quotes_org_number"),
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
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("commercial_customers.id"),
        nullable=False,
        index=True,
    )
    sample_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("commercial_samples.id"),
        nullable=True,
        index=True,
    )
    quote_number: Mapped[str] = mapped_column(String(64), nullable=False)
    issue_date: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    valid_until: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    status: Mapped[QuoteStatus] = mapped_column(
        SqlEnum(QuoteStatus, name="quote_status", values_callable=enum_values),
        nullable=False,
        default=QuoteStatus.DRAFT,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
    items: Mapped[list["QuoteItem"]] = relationship(
        back_populates="quote",
        cascade="all, delete-orphan",
    )


class QuoteItem(Base):
    __tablename__ = "commercial_quote_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    quote_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("commercial_quotes.id"),
        nullable=False,
        index=True,
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    product_type: Mapped[str] = mapped_column(String(120), nullable=False)
    requested_spec_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)  # customer-facing commercial spec only
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    quote: Mapped[Quote] = relationship(back_populates="items")


class CommercialOrder(Base):
    __tablename__ = "commercial_orders"
    __table_args__ = (
        UniqueConstraint("organization_id", "order_number", name="uq_commercial_orders_org_number"),
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
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("commercial_customers.id"),
        nullable=False,
        index=True,
    )
    quote_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("commercial_quotes.id"),
        nullable=True,
        index=True,
    )
    order_number: Mapped[str] = mapped_column(String(64), nullable=False)
    order_date: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    status: Mapped[CommercialOrderStatus] = mapped_column(
        SqlEnum(CommercialOrderStatus, name="commercial_order_status", values_callable=enum_values),
        nullable=False,
        default=CommercialOrderStatus.DRAFT,
    )
    requested_delivery_date: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
    items: Mapped[list["CommercialOrderItem"]] = relationship(
        back_populates="commercial_order",
        cascade="all, delete-orphan",
    )


class CommercialOrderItem(Base):
    __tablename__ = "commercial_order_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    commercial_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("commercial_orders.id"),
        nullable=False,
        index=True,
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    product_type: Mapped[str] = mapped_column(String(120), nullable=False)
    requested_spec_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)  # customer-facing commercial spec only
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    agreed_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    line_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    commercial_order: Mapped[CommercialOrder] = relationship(back_populates="items")


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
        SqlEnum(InteractionType, name="customer_interaction_type", values_callable=enum_values),
        nullable=False,
    )
    interaction_date: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
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
    due_date: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    priority: Mapped[PriorityLevel] = mapped_column(
        SqlEnum(PriorityLevel, name="follow_up_priority", values_callable=enum_values),
        nullable=False,
        default=PriorityLevel.MEDIUM,
    )
    status: Mapped[FollowUpStatus] = mapped_column(
        SqlEnum(FollowUpStatus, name="follow_up_status", values_callable=enum_values),
        nullable=False,
        default=FollowUpStatus.PENDING,
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
