from datetime import date, datetime
from uuid import UUID, uuid4
from sqlalchemy import ForeignKey, String, UniqueConstraint, CheckConstraint, Date, Text, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base
from app.core.utils import TZDateTime, utc_now


class DirectoryRecord:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey('foundation_organizations.id'), index=True)
    name: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(default=True)
    version: Mapped[int] = mapped_column(default=1)
    created_by: Mapped[UUID] = mapped_column(ForeignKey('foundation_users.id'))
    updated_by: Mapped[UUID] = mapped_column(ForeignKey('foundation_users.id'))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=utc_now, onupdate=utc_now)


class Carrier(DirectoryRecord, Base):
    __tablename__ = 'shipping_carriers'
    __table_args__ = (UniqueConstraint('organization_id','name',name='uq_shipping_carrier_name'),)
    phone: Mapped[str | None] = mapped_column(String(30))


class Driver(DirectoryRecord, Base):
    __tablename__ = 'shipping_drivers'
    __table_args__ = (CheckConstraint("affiliation IN ('internal','external')",name='ck_driver_affiliation'),
        CheckConstraint("affiliation != 'internal' OR workforce_member_id IS NOT NULL",name='ck_driver_internal_worker'),
        UniqueConstraint('organization_id','workforce_member_id',name='uq_driver_worker'),
        Index('uq_shipping_drivers_org_identity', 'organization_id', 'identity_no', unique=True,
              postgresql_where=text('identity_no IS NOT NULL'), sqlite_where=text('identity_no IS NOT NULL')))
    email: Mapped[str | None] = mapped_column(String(255))
    license_no: Mapped[str | None] = mapped_column(String(40))
    license_expiry: Mapped[date | None] = mapped_column(Date)
    default_vehicle_id: Mapped[UUID | None] = mapped_column(ForeignKey('shipping_vehicles.id'))
    vehicle_type: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)
    affiliation: Mapped[str] = mapped_column(String(16))
    workforce_member_id: Mapped[UUID | None]  # Workforce owns the employee; no login required.
    phone: Mapped[str | None] = mapped_column(String(30))
    identity_no: Mapped[str | None] = mapped_column(String(40))
    carrier_id: Mapped[UUID | None] = mapped_column(ForeignKey('shipping_carriers.id'))


class Vehicle(DirectoryRecord, Base):
    __tablename__ = 'shipping_vehicles'
    __table_args__ = (UniqueConstraint('organization_id','plate',name='uq_shipping_vehicle_plate'),)
    plate: Mapped[str] = mapped_column(String(40))
    vehicle_type: Mapped[str | None] = mapped_column(String(80))
    carrier_id: Mapped[UUID | None] = mapped_column(ForeignKey('shipping_carriers.id'))
