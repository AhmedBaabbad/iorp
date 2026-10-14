"""Notification tables (PROJECT-NOTIFY-001); the notifications module is their only writer."""
from datetime import datetime
import uuid

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.utils import TZDateTime, utc_now


class Announcement(Base):
    """A message written by a person to named users, a role's members or the whole organization."""
    __tablename__ = "notifications_announcements"
    __table_args__ = (
        CheckConstraint("severity IN ('info', 'important', 'urgent')", name="ck_announcement_severity"),
        CheckConstraint("audience IN ('users', 'role', 'everyone')", name="ck_announcement_audience"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("foundation_organizations.id"), nullable=False, index=True)
    author_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("foundation_users.id"), nullable=False)
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    requires_ack: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    audience: Mapped[str] = mapped_column(String(20), nullable=False)
    audience_role_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("foundation_roles.id", ondelete="SET NULL"), nullable=True)
    audience_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recipient_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)
    withdrawn_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    withdrawn_by_name: Mapped[str | None] = mapped_column(String(255), nullable=True)


class NotificationItem(Base):
    """One notification of one user: an event of a module (its words live in the screens) or an announcement."""
    __tablename__ = "notifications_items"
    __table_args__ = (
        Index("ix_notification_inbox", "recipient_user_id", "read_at", "created_at"),
        Index("ix_notification_resource", "organization_id", "resource_type", "resource_id"),
        CheckConstraint("severity IN ('info', 'important', 'urgent')", name="ck_notification_severity"),
        CheckConstraint("category IN ('access', 'security', 'delegation', 'work', 'announcement')", name="ck_notification_category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("foundation_organizations.id"), nullable=False)
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("foundation_users.id", ondelete="CASCADE"), nullable=False)
    event: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    resource_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    announcement_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("notifications_announcements.id", ondelete="CASCADE"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)
    read_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    settled_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    hidden_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)  # the reader put it away (it stays until purged)
