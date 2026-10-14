"""Customer complaint tables (COMPLAINTS-001). Commercial is their only writer; other modules are linked by id only."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base
from app.core.utils import TZDateTime, utc_now


class Complaint(Base):
    __tablename__ = 'commercial_complaints'
    __table_args__ = (UniqueConstraint('organization_id', 'number', name='uq_complaint_number'),
                     Index('ix_complaint_org_status_due', 'organization_id', 'status', 'due_date'),
                     Index('ix_complaint_org_created', 'organization_id', 'created_at', 'id'))
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey('foundation_organizations.id'), index=True)
    number: Mapped[str] = mapped_column(String(40))
    customer_id: Mapped[UUID] = mapped_column(ForeignKey('commercial_customers.id'), index=True)
    title: Mapped[str] = mapped_column(String(255))
    statement: Mapped[str] = mapped_column(Text)
    contact: Mapped[str | None] = mapped_column(String(255))
    channel: Mapped[str] = mapped_column(String(32))
    received_date: Mapped[date]
    category: Mapped[str] = mapped_column(String(32))
    priority: Mapped[str] = mapped_column(String(16), default='medium')
    department: Mapped[str] = mapped_column(String(32), default='commercial')
    owner_user_id: Mapped[UUID | None] = mapped_column(ForeignKey('foundation_users.id'), index=True)
    response_due_date: Mapped[date | None]
    due_date: Mapped[date | None]
    status: Mapped[str] = mapped_column(String(24), default='new')
    version: Mapped[int] = mapped_column(Integer, default=1)
    external_reference: Mapped[str | None] = mapped_column(String(255))
    finding: Mapped[str] = mapped_column(String(24), default='pending')
    investigation: Mapped[str | None] = mapped_column(Text)
    containment: Mapped[str | None] = mapped_column(Text)
    resolution: Mapped[str | None] = mapped_column(Text)
    implementation_evidence: Mapped[str | None] = mapped_column(Text)
    customer_response: Mapped[str | None] = mapped_column(Text)
    closure_requested_by: Mapped[UUID | None] = mapped_column(ForeignKey('foundation_users.id'))
    closed_by: Mapped[UUID | None] = mapped_column(ForeignKey('foundation_users.id'))
    closed_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    created_by: Mapped[UUID] = mapped_column(ForeignKey('foundation_users.id'))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utc_now, onupdate=utc_now)
    items: Mapped[list['ComplaintItem']] = relationship(cascade='all, delete-orphan', lazy='selectin', order_by='ComplaintItem.line_no')


class ComplaintItem(Base):
    """A product the complaint is about. Three quantities are kept apart: delivered, reported by the customer, and the
    quantity the investigation confirmed as affected (empty until it is confirmed)."""
    __tablename__ = 'commercial_complaint_items'
    __table_args__ = (CheckConstraint('reported_quantity >= 0 AND delivered_quantity >= 0 AND reported_quantity <= delivered_quantity', name='ck_complaint_quantities'),
                      CheckConstraint('confirmed_quantity IS NULL OR (confirmed_quantity >= 0 AND confirmed_quantity <= delivered_quantity)', name='ck_complaint_confirmed'),
                      CheckConstraint("source_kind IN ('order', 'sample', 'manual')", name='ck_complaint_item_source'))
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey('foundation_organizations.id'), index=True)
    complaint_id: Mapped[UUID] = mapped_column(ForeignKey('commercial_complaints.id'), index=True)
    line_no: Mapped[int] = mapped_column(Integer, default=1)
    product_key: Mapped[str] = mapped_column(String(120))
    product_name: Mapped[str] = mapped_column(String(255))
    batch_reference: Mapped[str | None] = mapped_column(String(255))
    unit: Mapped[str] = mapped_column(String(32))
    delivered_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 3))
    reported_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 3))
    confirmed_quantity: Mapped[Decimal | None] = mapped_column(Numeric(15, 3))
    # Where the agreed specification came from: a sales order line or a sample of this customer (copied when chosen,
    # so later changes there never rewrite the complaint), or typed by hand.
    source_kind: Mapped[str] = mapped_column(String(16), default='manual')
    source_id: Mapped[UUID | None]
    source_label: Mapped[str | None] = mapped_column(String(120))
    properties: Mapped[list['ComplaintItemProperty']] = relationship(cascade='all, delete-orphan', lazy='selectin',
                                                                     order_by='ComplaintItemProperty.line_no')


class ComplaintItemProperty(Base):
    """One property of a complained product, with three values kept apart: agreed, reported by the customer, measured
    by the investigation. The property's names and unit are copied from master data when recorded."""
    __tablename__ = 'commercial_complaint_item_properties'
    __table_args__ = (UniqueConstraint('item_id', 'key', name='uq_complaint_item_property'),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey('foundation_organizations.id'), index=True)
    item_id: Mapped[UUID] = mapped_column(ForeignKey('commercial_complaint_items.id', ondelete='CASCADE'), index=True)
    line_no: Mapped[int] = mapped_column(Integer, default=1)
    key: Mapped[str] = mapped_column(String(120))
    name_ar: Mapped[str] = mapped_column(String(255))
    name_en: Mapped[str] = mapped_column(String(255))
    unit: Mapped[str | None] = mapped_column(String(32))
    expected: Mapped[str] = mapped_column(String(1000), default='')
    reported: Mapped[str] = mapped_column(String(1000), default='')
    measured: Mapped[str] = mapped_column(String(1000), default='')


class ComplaintEvent(Base):
    """One entry of the decision and follow-up history. `details` holds the decision's facts by name (department, owner,
    dates, statuses, references); `notes` holds what the person wrote. Screens and reports word them in the reader's
    language, so no code or id is ever shown as text."""
    __tablename__ = 'commercial_complaint_events'
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey('foundation_organizations.id'), index=True)
    complaint_id: Mapped[UUID] = mapped_column(ForeignKey('commercial_complaints.id'), index=True)
    action: Mapped[str] = mapped_column(String(40))
    notes: Mapped[str] = mapped_column(Text, default='')
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey('foundation_users.id'))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utc_now)


class ComplaintLink(Base):
    __tablename__ = 'commercial_complaint_links'
    __table_args__ = (UniqueConstraint('complaint_id', 'kind', 'record_id', name='uq_complaint_link'),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey('foundation_organizations.id'), index=True)
    complaint_id: Mapped[UUID] = mapped_column(ForeignKey('commercial_complaints.id'), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    record_id: Mapped[UUID]
    created_by: Mapped[UUID] = mapped_column(ForeignKey('foundation_users.id'))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utc_now)


class ComplaintAttachment(Base):
    __tablename__ = 'commercial_complaint_attachments'
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey('foundation_organizations.id'), index=True)
    complaint_id: Mapped[UUID] = mapped_column(ForeignKey('commercial_complaints.id'), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(500))  # the storage key (core/storage.py)
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, server_default='0')  # as stored, after processing
    checksum: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[UUID] = mapped_column(ForeignKey('foundation_users.id'))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utc_now)


class ComplaintCodeCounter(Base):
    """The last complaint number of each organization and year (CC-2026-0001), taken under a row lock."""
    __tablename__ = 'commercial_complaint_code_counters'
    organization_id: Mapped[UUID] = mapped_column(ForeignKey('foundation_organizations.id'), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, default=0)


from app.core.files import register_file_table  # noqa: E402  (PROJECT-FILES-003: counted in the organization's quota)

register_file_table("commercial_complaint_attachments")
