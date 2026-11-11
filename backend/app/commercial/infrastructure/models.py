from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy import Boolean, CheckConstraint, JSON, DateTime, Enum as SqlEnum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # status is the operational record state; relationship_stage is business progression.
    # Keep them independent and never derive one from the other.
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
    sales_owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_users.id"),
        nullable=True,
        index=True,
    )
    # Deprecated: superseded by sales_owner_user_id. Retained (renamed, not
    # dropped) only so historical free-text values aren't lost.
    sales_owner_name_legacy: Mapped[str | None] = mapped_column(String(255), nullable=True)
    key_influencer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
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
    interactions: Mapped[list["CustomerInteraction"]] = relationship(
        cascade="all, delete-orphan",
    )
    follow_ups: Mapped[list["FollowUp"]] = relationship(
        cascade="all, delete-orphan",
    )


class CustomerCodeCounter(Base):
    __tablename__ = "commercial_customer_code_counters"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_organizations.id"),
        primary_key=True,
    )
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class SampleCodeCounter(Base):
    __tablename__ = "commercial_sample_code_counters"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_organizations.id"),
        primary_key=True,
    )
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class QuoteCodeCounter(Base):
    __tablename__ = "commercial_quote_code_counters"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_organizations.id"),
        primary_key=True,
    )
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class OrderCodeCounter(Base):
    __tablename__ = "commercial_order_code_counters"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_organizations.id"),
        primary_key=True,
    )
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


class Sample(Base):
    __tablename__ = "commercial_samples"
    __table_args__ = (UniqueConstraint("customer_id", "sample_code", name="uq_commercial_samples_customer_code"),)

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
    is_sample_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requested_sample_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    request_date: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    # sample_status tracks operational lifecycle
    # sample_decision tracks the final commercial decision on the sample
    # These are independent -- do not derive one from the other
    status: Mapped[SampleStatus] = mapped_column(
        SqlEnum(SampleStatus, name="sample_status", values_callable=enum_values),
        nullable=False,
        default=SampleStatus.REQUESTED,
    )
    sample_decision: Mapped[SampleDecision | None] = mapped_column(
        SqlEnum(SampleDecision, name="sampledecision_enum", values_callable=enum_values),
        nullable=True,
        default=None,
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
    # Raised each time an issued, rejected or expired quotation goes back to a draft (SALES-001).
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # VAT percentage the server applies to (subtotal - discount); null on quotes saved before it existed.
    tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    attention: Mapped[str | None] = mapped_column(String(255), nullable=True)  # "Attn: Procurement Manager"
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
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
    # The line's discount, a percentage taken before VAT, and its amount (domain/pricing.py).
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0"), server_default="0")
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"), server_default="0")
    # The line as printed on the quotation; empty falls back to the product and its specification.
    description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    quote: Mapped[Quote] = relationship(back_populates="items")

    __table_args__ = (CheckConstraint("discount_percent >= 0 AND discount_percent <= 100", name="ck_quote_item_discount_percent"),)

    @property
    def net_total(self) -> Decimal:
        return Decimal(self.line_total) - Decimal(self.discount_amount or 0)


class QuoteSettings(Base):
    """Per-organization quotation document settings: the language quotations are printed in, and who signs them.
    The terms are QuoteTerm rows."""
    __tablename__ = "commercial_quote_settings"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), primary_key=True)
    # ar | en: every quotation is printed in this language, with the settings written in it (nothing from the other one).
    document_language: Mapped[str] = mapped_column(String(2), nullable=False, default="ar", server_default="ar")
    quote_validity_days: Mapped[int] = mapped_column(Integer, nullable=False, default=10, server_default="10")
    signature_title_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signature_title_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    show_preparer_name: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class QuoteTerm(Base):
    """One term of the organization's quotation terms and conditions (e.g. Delivery, Payment), in both languages.

    Drafts use these settings. Issued revisions print their immutable terms snapshot.
    """
    __tablename__ = "commercial_quote_terms"
    __table_args__ = (Index("ix_commercial_quote_terms_org_order", "organization_id", "sort_order"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Written in one language or both; a quotation prints a term only in its own language.
    title_ar: Mapped[str | None] = mapped_column(String(120), nullable=True)
    title_en: Mapped[str | None] = mapped_column(String(120), nullable=True)
    body_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


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
    confirmed_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    currency: Mapped[str | None] = mapped_column(String(3))
    customer_reference: Mapped[str | None] = mapped_column(String(120))
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
    # Four places: a price after a quotation's percentage discount (e.g. 12.35 less 7 % = 11.4855).
    agreed_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    line_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    commercial_order: Mapped[CommercialOrder] = relationship(back_populates="items")


class CommercialStatusHistory(Base):
    """One row per lifecycle step of a quotation or a sales order (SALES-001); never updated or deleted."""
    __tablename__ = "commercial_status_history"
    __table_args__ = (Index("ix_commercial_status_history_entity", "organization_id", "entity_type", "entity_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)  # quote | sales_order
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)  # create, issue, accept, reject, expire, revise, confirm, cancel
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reason: Mapped[str | None] = mapped_column(String(500))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)


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
    interaction_type: Mapped[str] = mapped_column(String(60), nullable=False)  # MD-003: a key of the interaction_type list
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
    __table_args__ = (
        Index("ix_commercial_follow_ups_status_due_date", "status", "due_date"),
    )

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
        ForeignKey("commercial_customer_interactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Nullable despite being conceptually "required": ON DELETE SET NULL means
    # a follow-up must survive its assignee's user account being deleted, which
    # is incompatible with a NOT NULL constraint. Application code always sets
    # this on create; it can only become NULL via a foundation_users deletion.
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    due_date: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, index=True)
    priority: Mapped[FollowUpPriority] = mapped_column(
        SqlEnum(FollowUpPriority, name="follow_up_priority", values_callable=enum_values),
        nullable=False,
        default=FollowUpPriority.MEDIUM,
    )
    status: Mapped[FollowUpStatus] = mapped_column(
        SqlEnum(FollowUpStatus, name="follow_up_status", values_callable=enum_values),
        nullable=False,
        default=FollowUpStatus.PENDING,
        index=True,
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
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

# Register complaint-owned tables with the commercial metadata.
from .complaint_models import Complaint, ComplaintItem, ComplaintItemProperty, ComplaintEvent, ComplaintLink, ComplaintAttachment, ComplaintCodeCounter  # noqa: F401

from .quote_terms_models import QuoteTermsSnapshot  # noqa: F401,E402

from .contact_models import CustomerContact, CustomerSite  # noqa: E402,F401
