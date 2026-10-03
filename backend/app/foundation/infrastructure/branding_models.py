from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base
from app.core.utils import TZDateTime, utc_now


class StoredAsset(Base):
    __tablename__ = 'foundation_stored_assets'
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey('foundation_organizations.id'), index=True)
    storage_key: Mapped[str] = mapped_column(String(500))
    media_type: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utc_now)


class OrganizationBranding(Base):
    __tablename__ = 'foundation_organization_branding'
    organization_id: Mapped[UUID] = mapped_column(ForeignKey('foundation_organizations.id'), primary_key=True)
    legal_name_ar: Mapped[str | None] = mapped_column(String(255))
    legal_name_en: Mapped[str | None] = mapped_column(String(255))
    trade_name_ar: Mapped[str | None] = mapped_column(String(255))
    trade_name_en: Mapped[str | None] = mapped_column(String(255))
    commercial_registration_no: Mapped[str | None] = mapped_column(String(100))
    vat_number: Mapped[str | None] = mapped_column(String(100))
    unified_number: Mapped[str | None] = mapped_column(String(10))  # الرقم الموحد (700...)
    # Optional tagline under the company name on external documents ("Industrial Strapping & Packaging Solutions").
    descriptor_ar: Mapped[str | None] = mapped_column(String(255))
    descriptor_en: Mapped[str | None] = mapped_column(String(255))
    address_ar: Mapped[str | None] = mapped_column(String(500))
    address_en: Mapped[str | None] = mapped_column(String(500))
    city: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(30))
    phone: Mapped[str | None] = mapped_column(String(60))
    email: Mapped[str | None] = mapped_column(String(255))
    website: Mapped[str | None] = mapped_column(String(255))
    report_footer_note_ar: Mapped[str | None] = mapped_column(Text)
    report_footer_note_en: Mapped[str | None] = mapped_column(Text)
    primary_color: Mapped[str | None] = mapped_column(String(7))
    logo_asset_id: Mapped[UUID | None] = mapped_column(ForeignKey('foundation_stored_assets.id'))
    secondary_logo_asset_id: Mapped[UUID | None] = mapped_column(ForeignKey('foundation_stored_assets.id'))
    updated_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey('foundation_users.id', ondelete='SET NULL'))
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utc_now, onupdate=utc_now)


class BankAccount(Base):
    """A company bank account printed in the footer of customer documents (quotations). Several are allowed."""
    __tablename__ = 'foundation_bank_accounts'
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey('foundation_organizations.id'), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    bank_name_ar: Mapped[str] = mapped_column(String(255))
    bank_name_en: Mapped[str | None] = mapped_column(String(255))
    account_name: Mapped[str | None] = mapped_column(String(255))
    account_number: Mapped[str | None] = mapped_column(String(64))
    iban: Mapped[str] = mapped_column(String(34))
    swift_code: Mapped[str | None] = mapped_column(String(11))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
