"""Master data tables (MD-001). Every table is prefixed masterdata_; other modules read them through the shared metadata
and never import these models, and this module imports none of theirs (ADR-004)."""
from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.utils import TZDateTime, utc_now


class MasterDataSettings(Base):
    """Per organization: the VAT rate and the default currency of new quotations and purchase orders."""
    __tablename__ = "masterdata_settings"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), primary_key=True)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("15"))
    default_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="SAR")
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now, onupdate=utc_now)


class MasterDataCounter(Base):
    """Per organization and kind (PRD): the last number issued."""
    __tablename__ = "masterdata_counters"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(8), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Product(Base):
    """A product the organization makes (finished) or buys (material). Other modules store its key."""
    __tablename__ = "masterdata_products"
    __table_args__ = (UniqueConstraint("organization_id", "key", name="uq_masterdata_products_key"),
                      UniqueConstraint("organization_id", "code", name="uq_masterdata_products_code"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False)  # PRD-0001
    key: Mapped[str] = mapped_column(String(60), nullable=False)  # pp_strap: fixed once created
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(12), nullable=False, default="finished")
    default_unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now, onupdate=utc_now)
    properties: Mapped[list["ProductProperty"]] = relationship(back_populates="product", cascade="all, delete-orphan",
                                                               order_by="ProductProperty.line_no")


class ProductProperty(Base):
    """One property of a product's specification template: a number (with its unit), a text, or a choice."""
    __tablename__ = "masterdata_product_properties"
    __table_args__ = (UniqueConstraint("product_id", "key", name="uq_masterdata_product_properties_key"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("masterdata_products.id", ondelete="CASCADE"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    key: Mapped[str] = mapped_column(String(60), nullable=False)  # width_mm
    name_ar: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False, default="text")  # number | text | choice
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [{value, label_ar, label_en}] for a choice
    product: Mapped[Product] = relationship(back_populates="properties")


class ListItem(Base):
    """An item of a reference list (MD-002): a sector, opportunity source, country or city (a city belongs to a country,
    named by its key). Other modules store the key."""
    __tablename__ = "masterdata_list_items"
    __table_args__ = (UniqueConstraint("organization_id", "list", "key", name="uq_masterdata_list_items_key"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), nullable=False, index=True)
    list: Mapped[str] = mapped_column(String(20), nullable=False)
    key: Mapped[str] = mapped_column(String(60), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(200), nullable=False)
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    parent_key: Mapped[str | None] = mapped_column(String(60), nullable=True)  # a city's country
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now, onupdate=utc_now)
