"""Shipping tables (SHIP-001, SHIP-004). Every table is prefixed shipping_; other modules are referenced by plain UUIDs
(a customer may also be unregistered), never by importing their models (ADR-004)."""
from datetime import date, datetime
from decimal import Decimal
import uuid

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.utils import TZDateTime, utc_now


class ShippingSettings(Base):
    """Per organization: the delivery note and return number prefixes, the return window and the weight tolerance."""
    __tablename__ = "shipping_settings"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), primary_key=True)
    note_prefix: Mapped[str] = mapped_column(String(20), nullable=False, default="DN-")
    return_prefix: Mapped[str] = mapped_column(String(20), nullable=False, default="RT-")
    return_window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)  # after delivery; later needs a note
    weight_tolerance_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("1.00"))
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now, onupdate=utc_now)


class ShippingCodeCounter(Base):
    """Per organization and year: the last delivery note number issued. Locked while numbering."""
    __tablename__ = "shipping_code_counters"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ShippingReturnCounter(Base):
    """Per organization and year: the last return number issued. Locked while numbering."""
    __tablename__ = "shipping_return_counters"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Shipment(Base):
    """One delivery note: the customer and recipient, how the goods leave, its lines and its lifecycle."""
    __tablename__ = "shipping_shipments"
    __table_args__ = (UniqueConstraint("organization_id", "shipment_no", name="uq_shipping_shipments_org_no"),
                      Index("ix_shipping_shipments_org_status", "organization_id", "status"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), nullable=False, index=True)
    shipment_no: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    delivery_method: Mapped[str] = mapped_column(String(20), nullable=False)
    shipment_date: Mapped[date] = mapped_column(nullable=False, index=True)
    # The customer: a registered one (customer_id) or only named; the name is always kept as printed.
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_reference: Mapped[str | None] = mapped_column(String(80), nullable=True)  # the customer's PO
    # The recipient, who may differ from the customer (a branch, a site, a contractor); contacts for notifications later.
    consignee_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    consignee_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    consignee_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notify_consignee: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    delivery_city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    location_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Who carries the goods: the customer's or the factory's driver, or a carrier company.
    driver_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    carrier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    driver_affiliation: Mapped[str | None] = mapped_column(String(16), nullable=True)
    customer_contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    delivery_site_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    driver_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    driver_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    driver_id_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
    vehicle_plate: Mapped[str | None] = mapped_column(String(40), nullable=True)
    vehicle_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    carrier_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tracking_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Lifecycle facts. attempt counts the times the goods set out (a returned note is rescheduled under its number).
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ready_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    dispatched_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id"), nullable=True)
    gate_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)  # the factory weighbridge, at dispatch
    received_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)  # the customer's, at delivery
    failed_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)  # the last failed delivery
    delivered_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    received_by_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    delivery_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id"), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    close_reason: Mapped[str | None] = mapped_column(Text, nullable=True)  # closed as not delivered
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now, onupdate=utc_now)
    lines: Mapped[list["ShipmentLine"]] = relationship(back_populates="shipment", cascade="all, delete-orphan",
                                                       order_by="ShipmentLine.line_no")


class ShipmentLine(Base):
    """What is shipped (SHIP-003): description, width and thickness (mm), quantity in a unit from the shared catalogue
    (app/core/units.py), and the full weight of those units in a weight unit."""
    __tablename__ = "shipping_shipment_lines"
    __table_args__ = (UniqueConstraint("shipment_id", "line_no", name="uq_shipping_shipment_lines_no"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shipping_shipments.id", ondelete="CASCADE"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    width_mm: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    thickness_mm: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    weight_unit: Mapped[str] = mapped_column(String(8), nullable=False, default="kg")
    # The production order (batch) the goods come from, for tracing a complaint back; its number is kept as printed.
    production_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    production_order_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    delivered_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)  # what the customer accepted
    shipment: Mapped[Shipment] = relationship(back_populates="lines")


class ShipmentEvent(Base):
    """Every lifecycle step of a shipment: its history, and the outbox a future notification workflow reads.

    `payload` carries what a message would need (status, recipient contacts, notify flag); `processed_at` stays
    empty until a notifier has handled the event. Nothing is sent by this module.
    """
    __tablename__ = "shipping_shipment_events"
    __table_args__ = (Index("ix_shipping_events_shipment", "organization_id", "shipment_id"),
                      Index("ix_shipping_events_unprocessed", "organization_id", "processed_at"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), nullable=False)
    shipment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shipping_shipments.id", ondelete="CASCADE"), nullable=False)
    return_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("shipping_returns.id", ondelete="CASCADE"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)  # e.g. shipment.dispatched
    from_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    to_status: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id", ondelete="SET NULL"), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)
    processed_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)


class ShipmentReturn(Base):
    """Goods coming back after they left (SHIP-004): numbered on its own, always against its delivery note.

    kind "delivery": not received at the door (a failed delivery, or the refused part of a partial one);
    kind "customer": returned by the customer after receiving them. The customer and the method are those of the note.
    """
    __tablename__ = "shipping_returns"
    __table_args__ = (UniqueConstraint("organization_id", "return_no", name="uq_shipping_returns_org_no"),
                      Index("ix_shipping_returns_org_status", "organization_id", "status"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), nullable=False, index=True)
    return_no: Mapped[str] = mapped_column(String(40), nullable=False)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False)
    shipment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shipping_shipments.id"), nullable=False, index=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # the delivery attempt it came back from
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    responsibility: Mapped[str] = mapped_column(String(16), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_reference: Mapped[str | None] = mapped_column(String(80), nullable=True)  # the customer's complaint / return ref
    carrier_claim_ref: Mapped[str | None] = mapped_column(String(80), nullable=True)  # a claim against the carrier
    requested_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)
    is_late: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # SHIP-005: the goods go to quality before any decision (a quality reason, transit damage, "other", or the warehouse
    # sent them); otherwise the warehouse puts them back to stock on receipt.
    quality_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    decided_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id"), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)  # the approval note, or the rejection reason
    received_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    received_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id"), nullable=True)
    receipt_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now, onupdate=utc_now)
    lines: Mapped[list["ShipmentReturnLine"]] = relationship(back_populates="shipment_return", cascade="all, delete-orphan",
                                                             order_by="ShipmentReturnLine.line_no")


class ShipmentReturnLine(Base):
    """A delivery note line coming back: how much is expected, and what actually arrived. The line's description and
    units are copied, so the return prints what the note printed."""
    __tablename__ = "shipping_return_lines"
    __table_args__ = (UniqueConstraint("return_id", "line_no", name="uq_shipping_return_lines_no"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    return_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shipping_returns.id", ondelete="CASCADE"), nullable=False, index=True)
    shipment_line_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shipping_shipment_lines.id"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    width_mm: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    thickness_mm: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    weight_unit: Mapped[str] = mapped_column(String(8), nullable=False, default="kg")
    production_order_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    received_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    received_weight: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    shipment_return: Mapped[ShipmentReturn] = relationship(back_populates="lines")


class ShippingAttachment(Base):
    """A file kept with a shipment or one of its returns: the signed delivery note (proof of delivery), photos of
    damage. Uploaded by users, so it is stored (unlike generated documents, which never are)."""
    __tablename__ = "shipping_attachments"
    __table_args__ = (Index("ix_shipping_attachments_owner", "organization_id", "shipment_id", "return_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), nullable=False)
    shipment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shipping_shipments.id"), nullable=False)
    return_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("shipping_returns.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)  # proof_of_delivery | photo | document
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(80), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)  # the storage key (core/storage.py)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id"), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)
    # A file of a finished shipment or return is archived, never deleted: it stays as part of the record.
    archived_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    archived_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id"), nullable=True)


from app.core.files import register_file_table  # noqa: E402  (PROJECT-FILES-003: counted in the organization's quota)

register_file_table("shipping_attachments")

from .directory_models import Driver, Vehicle, Carrier  # noqa: F401,E402
