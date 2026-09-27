from datetime import datetime
import uuid

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.utils import TZDateTime, enum_values, utc_now
from app.platform.domain.enums import PlatformAccountRole, PlatformAccountStatus


class PlatformAccount(Base):
    __tablename__ = "system_platform_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[PlatformAccountStatus] = mapped_column(
        Enum(PlatformAccountStatus, name="platform_account_status", values_callable=enum_values),
        nullable=False,
        default=PlatformAccountStatus.ACTIVE,
    )
    is_root: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    role: Mapped[PlatformAccountRole] = mapped_column(
        Enum(PlatformAccountRole, name="platform_account_role", values_callable=enum_values),
        nullable=False,
        default=PlatformAccountRole.ADMIN,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    auto_locked_until: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True, default=None)
    last_failed_login_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True, default=None)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class BootstrapState(Base):
    __tablename__ = "system_bootstrap_state"
    __table_args__ = (CheckConstraint("id = 1", name="ck_system_bootstrap_state_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    is_initialized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    initialized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    initialized_by_platform_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("system_platform_accounts.id")
    )
    first_organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("foundation_organizations.id")
    )
    installation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, default=uuid.uuid4, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class PlatformSecurityEvent(Base):
    __tablename__ = "system_security_events"
    __table_args__ = (
        Index("ix_system_security_events_event_type", "event_type"),
        Index("ix_system_security_events_actor_id", "actor_id"),
        Index("ix_system_security_events_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("system_platform_accounts.id"), nullable=True)
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    details: Mapped[dict | list | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)


class PlatformActivityLog(Base):
    __tablename__ = "system_platform_activity_log"
    __table_args__ = (
        Index("ix_system_platform_activity_action", "action"),
        Index("ix_system_platform_activity_entity_type", "entity_type"),
        Index("ix_system_platform_activity_actor_id", "actor_id"),
        Index("ix_system_platform_activity_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    entity_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("system_platform_accounts.id"), nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details: Mapped[dict | list | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)


class PlatformPasswordResetToken(Base):
    __tablename__ = "system_password_reset_tokens"
    __table_args__ = (
        Index("ix_system_password_reset_account", "account_id"),
        Index("ix_system_password_reset_expires", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("system_platform_accounts.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)
