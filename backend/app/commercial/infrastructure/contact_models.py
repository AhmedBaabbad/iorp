from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base
from app.core.utils import TZDateTime, utc_now


class CustomerRecord:
    id:Mapped[UUID]=mapped_column(primary_key=True,default=uuid4)
    organization_id:Mapped[UUID]=mapped_column(ForeignKey('foundation_organizations.id'),index=True)
    customer_id:Mapped[UUID]=mapped_column(ForeignKey('commercial_customers.id'),index=True)
    name:Mapped[str]=mapped_column(String(200))
    active:Mapped[bool]=mapped_column(default=True)
    is_default:Mapped[bool]=mapped_column(default=False)
    version:Mapped[int]=mapped_column(default=1)
    created_by:Mapped[UUID]=mapped_column(ForeignKey('foundation_users.id'))
    updated_by:Mapped[UUID]=mapped_column(ForeignKey('foundation_users.id'))
    created_at:Mapped[datetime]=mapped_column(TZDateTime,default=utc_now)
    updated_at:Mapped[datetime]=mapped_column(TZDateTime,default=utc_now,onupdate=utc_now)


class CustomerContact(CustomerRecord,Base):
    __tablename__='commercial_customer_contacts'
    phone:Mapped[str|None]=mapped_column(String(30))
    email:Mapped[str|None]=mapped_column(String(255))
    role:Mapped[str|None]=mapped_column(String(120))


class CustomerSite(CustomerRecord,Base):
    __tablename__='commercial_customer_sites'
    address:Mapped[str]=mapped_column(String(1000))
    city:Mapped[str|None]=mapped_column(String(120))
    location_url:Mapped[str|None]=mapped_column(String(500))
    contact_id:Mapped[UUID|None]=mapped_column(ForeignKey('commercial_customer_contacts.id'))
