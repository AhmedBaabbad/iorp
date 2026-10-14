from datetime import datetime
import uuid

from sqlalchemy import CheckConstraint, DateTime, Index, JSON, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.utils import TZDateTime, utc_now


class AuthSession(Base):
    __tablename__ = "core_auth_sessions"
    __table_args__ = (
        CheckConstraint("account_type IN ('tenant', 'platform')", name="ck_auth_session_account_type"),
        CheckConstraint(
            "(account_type = 'tenant' AND organization_id IS NOT NULL) OR "
            "(account_type = 'platform' AND organization_id IS NULL)",
            name="ck_auth_session_scope",
        ),
        Index("ix_auth_sessions_family_id", "family_id"),
        Index("ix_auth_sessions_account", "account_type", "account_id"),
        Index("ix_auth_sessions_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jti_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True, unique=True)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    account_type: Mapped[str] = mapped_column(String(16), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    token_version: Mapped[int] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    replaced_by_jti_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    # SEC-001: one sign-in is a family of rotated tokens. When it began (its absolute lifetime counts from here), and the
    # device it began on — shown to the user ("my sessions") and used to tell a new device.
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)


class AuthSecurityEvent(Base):
    __tablename__ = "core_auth_security_events"
    __table_args__ = (
        CheckConstraint("category IN ('identity','organization','authentication','authorization','security','configuration','audit')", name="ck_auth_event_category"),
        CheckConstraint("outcome IN ('success','failure','denied')", name="ck_auth_event_outcome"),
        CheckConstraint("severity IN ('info','warning','critical')", name="ck_auth_event_severity"),
        CheckConstraint("actor_type IN ('platform','tenant','system','anonymous')", name="ck_auth_event_actor_type"),
        Index("ix_auth_events_account", "account_type", "account_id"),
        Index("ix_auth_events_target", "target_type", "target_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(24), nullable=False, default="security", server_default="security", index=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, default="success", server_default="success", index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="info", server_default="info", index=True)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False, default="system", server_default="system")
    actor_email_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_name_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    target_display_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    jti_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    changes: Mapped[dict | list | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    event_metadata: Mapped[dict | list | None] = mapped_column("metadata", JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now, index=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)
