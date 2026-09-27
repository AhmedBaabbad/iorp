from datetime import datetime
import uuid

from sqlalchemy import Enum as SqlEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.utils import TZDateTime, enum_values, utc_now
from app.workforce.domain.enums import EmploymentType, WorkforceMemberStatus, WorkerType


class WorkforceMember(Base):
    __tablename__ = "workforce_members"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "employee_code",
            name="uq_workforce_members_org_code",
        ),
        UniqueConstraint("user_id", name="uq_workforce_members_user_id"),
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
    employee_code: Mapped[str] = mapped_column(String(20), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    worker_type: Mapped[WorkerType] = mapped_column(
        SqlEnum(WorkerType, name="workforce_worker_type", values_callable=enum_values),
        nullable=False,
    )
    employment_type: Mapped[EmploymentType] = mapped_column(
        SqlEnum(
            EmploymentType,
            name="workforce_employment_type",
            values_callable=enum_values,
        ),
        nullable=False,
    )
    status: Mapped[WorkforceMemberStatus] = mapped_column(
        SqlEnum(
            WorkforceMemberStatus,
            name="workforce_member_status",
            values_callable=enum_values,
        ),
        nullable=False,
        default=WorkforceMemberStatus.ACTIVE,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    primary_skill: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    @hybrid_property
    def is_system_user(self) -> bool:
        return self.user_id is not None

    @is_system_user.expression
    def is_system_user(cls):  # noqa: N805
        return cls.user_id.is_not(None)


class WorkforceCodeCounter(Base):
    __tablename__ = "workforce_code_counters"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_organizations.id"),
        primary_key=True,
    )
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
