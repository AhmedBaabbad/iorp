from datetime import datetime
import uuid

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.utils import TZDateTime, enum_values, utc_now
from app.foundation.domain.enums import OrganizationStatus, UserStatus


class Organization(Base):
    __tablename__ = "foundation_organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[OrganizationStatus] = mapped_column(
        Enum(
            OrganizationStatus,
            name="organization_status",
            values_callable=enum_values,
        ),
        nullable=False,
        default=OrganizationStatus.ACTIVE,
    )
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status_changed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("system_platform_accounts.id"), nullable=True
    )
    status_change_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    industry_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    default_locale: Mapped[str] = mapped_column(String(10), nullable=False, default="ar")
    logo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Bytes this organization's files may occupy; empty = the platform default (FILE_ORGANIZATION_QUOTA, core/files.py).
    storage_quota_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # SEC-001: how many devices one user may be signed in on at once; a further sign-in ends the oldest.
    max_sessions_per_user: Mapped[int] = mapped_column(Integer, nullable=False, default=2, server_default="2")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    users: Mapped[list["User"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    roles: Mapped[list["Role"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    permissions: Mapped[list["Permission"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )


class User(Base):
    __tablename__ = "foundation_users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_foundation_users_email_global"),
        Index("ix_foundation_users_email_lookup", "email"),
        CheckConstraint(
            "preferred_locale IS NULL OR preferred_locale IN ('ar', 'en')",
            name="ck_foundation_users_preferred_locale",
        ),
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
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    preferred_locale: Mapped[str | None] = mapped_column(String(10), nullable=True, default=None)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    account_change_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    token_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    is_organization_root: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(
            UserStatus,
            name="user_status",
            values_callable=enum_values,
        ),
        nullable=False,
        default=UserStatus.ACTIVE,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    auto_locked_until: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True, default=None)
    last_failed_login_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    organization: Mapped[Organization] = relationship(back_populates="users")
    user_roles: Mapped[list["UserRole"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="UserRole.user_id",
    )

    def to_safe_dict(self) -> dict:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "preferred_locale": self.preferred_locale,
            "status": self.status,
            "is_organization_root": self.is_organization_root,
        }


class Role(Base):
    __tablename__ = "foundation_roles"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_foundation_roles_org_code"),
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
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_protected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_editable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    organization: Mapped[Organization] = relationship(back_populates="roles")
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
    )
    user_roles: Mapped[list["UserRole"]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
    )


class Permission(Base):
    __tablename__ = "foundation_permissions"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_foundation_permissions_org_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("foundation_organizations.id", ondelete="CASCADE", name="fk_foundation_permissions_organization"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    module_name: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_name: Mapped[str] = mapped_column(String(80), nullable=False)
    action_name: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    organization: Mapped[Organization] = relationship(back_populates="permissions")

    role_permissions: Mapped[list["RolePermission"]] = relationship(
        back_populates="permission",
        cascade="all, delete-orphan",
    )


class RolePermission(Base):
    __tablename__ = "foundation_role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_foundation_role_permissions_pair"),
        CheckConstraint("scope IN ('own', 'team', 'organization')", name="ck_foundation_role_permissions_scope"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_roles.id"),
        nullable=False,
        index=True,
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_permissions.id"),
        nullable=False,
        index=True,
    )
    scope: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="organization",
        server_default="organization",
    )

    role: Mapped[Role] = relationship(back_populates="role_permissions")
    permission: Mapped[Permission] = relationship(back_populates="role_permissions")


class UserRole(Base):
    __tablename__ = "foundation_user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_foundation_user_roles_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_users.id"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("foundation_roles.id"),
        nullable=False,
        index=True,
    )
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("foundation_users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    user: Mapped[User] = relationship(back_populates="user_roles", foreign_keys=[user_id])
    role: Mapped[Role] = relationship(back_populates="user_roles")
    assigner: Mapped[User | None] = relationship(foreign_keys=[assigned_by])


class RoleAssignmentRemoval(Base):
    __tablename__ = "foundation_role_assignment_removals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    removed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("foundation_users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    removed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class TenantSecurityEvent(Base):
    __tablename__ = "foundation_security_events"
    __table_args__ = (
        Index("ix_foundation_security_org_event", "organization_id", "event_type"),
        Index("ix_foundation_security_org_created", "organization_id", "created_at"),
        Index("ix_foundation_security_actor_id", "actor_id"),
        Index("ix_foundation_security_actor_event", "actor_id", "event_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id"), nullable=True)
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    details: Mapped[dict | list | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)
    # A routine success repeated from the same device shortly after is counted here (security_log.MERGE_WINDOW).
    occurrences: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    last_seen_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)


class TenantActivityLog(Base):
    __tablename__ = "foundation_activity_log"
    __table_args__ = (
        Index("ix_foundation_activity_org_entity", "organization_id", "entity_type"),
        Index("ix_foundation_activity_org_created", "organization_id", "created_at"),
        Index("ix_foundation_activity_actor_id", "actor_id"),
        Index("ix_foundation_activity_action", "action"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    entity_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id"), nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details: Mapped[dict | list | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)


class TenantPasswordResetToken(Base):
    __tablename__ = "foundation_password_reset_tokens"
    __table_args__ = (
        Index("ix_foundation_password_reset_user", "user_id"),
        Index("ix_foundation_password_reset_expires", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id", ondelete="CASCADE"), nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)


class TenantAuditEntry(Base):
    """The organization's audit trail (ORG-AUDIT-002): who changed what in its administration and governance — users,
    roles, permissions, the organization's settings, delegations, announcements — when, and the values before and after.
    Written in the transaction of the change; never updated nor deleted."""
    __tablename__ = "foundation_audit_log"
    __table_args__ = (
        Index("ix_foundation_audit_org_created", "organization_id", "created_at"),
        Index("ix_foundation_audit_org_entity", "organization_id", "entity_type"),
        Index("ix_foundation_audit_action", "action"),
        Index("ix_foundation_audit_actor", "actor_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details: Mapped[dict | list | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, default=utc_now)


class ActivityArchive(Base):
    """One month of the activity log past its retention (ORG-AUDIT-003): when its holders were told, reminded, when it
    was downloaded and by whom, and when it was deleted. The archive file itself is never stored: it is built from the
    log when downloaded."""
    __tablename__ = "foundation_activity_archives"
    __table_args__ = (UniqueConstraint("organization_id", "month", name="uq_activity_archive_month"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), nullable=False)
    month: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notified_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    reminded_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    downloaded_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    downloaded_by_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    deleted_by_name: Mapped[str | None] = mapped_column(String(255), nullable=True)


class UserEmailChange(Base):
    __tablename__ = "foundation_user_email_changes"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_users.id"), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("foundation_organizations.id"), nullable=False)
    old_email: Mapped[str] = mapped_column(String(255), nullable=False)
    new_email: Mapped[str] = mapped_column(String(255), nullable=False)
    old_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    new_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    token_version: Mapped[int] = mapped_column(Integer, nullable=False)
