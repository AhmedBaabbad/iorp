"""Procurement tables (PROC-001). Every table is prefixed procurement_; other modules are referenced by plain UUIDs and
read through the shared metadata, never by importing their models (ADR-004)."""
from datetime import date, datetime
from decimal import Decimal
import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.utils import TZDateTime, utc_now


class ProcurementSettings(Base):
    """Per organization: the goods receipt number prefix."""
    __tablename__ = "procurement_settings"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), primary_key=True)
    receipt_prefix: Mapped[str] = mapped_column(String(20), nullable=False, default="GRN-")
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now, onupdate=utc_now)


class ProcurementCounter(Base):
    """Per organization, kind (SUP, MAT, GRN) and year (0 for codes that never restart): the last number issued."""
    __tablename__ = "procurement_counters"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(8), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Supplier(Base):
    """A supplier and its standing on the approved supplier list."""
    __tablename__ = "procurement_suppliers"
    __table_args__ = (UniqueConstraint("organization_id", "supplier_code", name="uq_procurement_suppliers_code"),
                      Index("ix_procurement_suppliers_org_status", "organization_id", "status"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), nullable=False, index=True)
    supplier_code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False, default="raw_material")
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="pending")
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_changed_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    status_changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id"), nullable=True)
    supplies: Mapped[str | None] = mapped_column(String(500), nullable=True)  # what it supplies, in words
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    vat_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    cr_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now, onupdate=utc_now)


class Material(Base):
    """A purchased material: its category, default unit, whether each lot is inspected on arrival, and the product key of
    its quality specification (matched by the incoming inspection)."""
    __tablename__ = "procurement_materials"
    __table_args__ = (UniqueConstraint("organization_id", "material_code", name="uq_procurement_materials_code"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), nullable=False, index=True)
    material_code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False, default="resin")
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="kg")
    inspection_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    spec_product_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now, onupdate=utc_now)


class GoodsReceipt(Base):
    """A delivery received from a supplier, with the supplier's own references."""
    __tablename__ = "procurement_receipts"
    __table_args__ = (UniqueConstraint("organization_id", "receipt_no", name="uq_procurement_receipts_no"),
                      Index("ix_procurement_receipts_org_status", "organization_id", "status"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), nullable=False, index=True)
    receipt_no: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="draft")
    receipt_date: Mapped[date] = mapped_column(nullable=False, index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("procurement_suppliers.id"), nullable=False, index=True)
    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False)  # as printed
    supplier_delivery_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
    supplier_invoice_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
    purchase_reference: Mapped[str | None] = mapped_column(String(80), nullable=True)  # the purchase order, until it is managed here
    vehicle_plate: Mapped[str | None] = mapped_column(String(40), nullable=True)
    driver_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    received_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id"), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now, onupdate=utc_now)
    lines: Mapped[list["GoodsReceiptLine"]] = relationship(back_populates="receipt", cascade="all, delete-orphan", order_by="GoodsReceiptLine.line_no")


class GoodsReceiptLine(Base):
    """A received lot: the material (or a described item), the supplier's lot, quantity, packages and weight; whether it is
    inspected on arrival is copied from the material."""
    __tablename__ = "procurement_receipt_lines"
    __table_args__ = (UniqueConstraint("receipt_id", "line_no", name="uq_procurement_receipt_lines_no"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    receipt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("procurement_receipts.id", ondelete="CASCADE"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    material_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("procurement_materials.id"), nullable=True, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    supplier_lot: Mapped[str | None] = mapped_column(String(80), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    package_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    weight_unit: Mapped[str] = mapped_column(String(8), nullable=False, default="kg")
    inspection_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    receipt: Mapped[GoodsReceipt] = relationship(back_populates="lines")


class ProcurementEvent(Base):
    """History of suppliers and receipts: what happened, who did it and why."""
    __tablename__ = "procurement_events"
    __table_args__ = (Index("ix_procurement_events_entity", "organization_id", "entity_type", "entity_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False)  # supplier | receipt
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id", ondelete="SET NULL"), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)
