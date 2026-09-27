"""add hardened JWT refresh sessions and security events

Revision ID: f6a1b2f5
Revises: f6a1b2f4
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f6a1b2f5"
down_revision: str | None = "f6a1b2f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "core_auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("jti_hash", sa.String(length=64), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_type", sa.String(length=16), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_jti_hash", sa.String(length=64), nullable=True),
        sa.Column("revocation_reason", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("account_type IN ('tenant', 'platform')", name="ck_auth_session_account_type"),
        sa.CheckConstraint("(account_type = 'tenant' AND organization_id IS NOT NULL) OR (account_type = 'platform' AND organization_id IS NULL)", name="ck_auth_session_scope"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jti_hash"),
    )
    op.create_index("ix_core_auth_sessions_jti_hash", "core_auth_sessions", ["jti_hash"], unique=True)
    op.create_index("ix_auth_sessions_family_id", "core_auth_sessions", ["family_id"])
    op.create_index("ix_auth_sessions_account", "core_auth_sessions", ["account_type", "account_id"])
    op.create_index("ix_auth_sessions_expires_at", "core_auth_sessions", ["expires_at"])
    op.create_table(
        "core_auth_security_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("account_type", sa.String(length=16), nullable=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("jti_hash", sa.String(length=64), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("reason", sa.String(length=120), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_core_auth_security_events_event_type", "core_auth_security_events", ["event_type"])
    op.create_index("ix_auth_events_account", "core_auth_security_events", ["account_type", "account_id"])


def downgrade() -> None:
    op.drop_index("ix_auth_events_account", table_name="core_auth_security_events")
    op.drop_index("ix_core_auth_security_events_event_type", table_name="core_auth_security_events")
    op.drop_table("core_auth_security_events")
    op.drop_index("ix_auth_sessions_expires_at", table_name="core_auth_sessions")
    op.drop_index("ix_auth_sessions_account", table_name="core_auth_sessions")
    op.drop_index("ix_auth_sessions_family_id", table_name="core_auth_sessions")
    op.drop_index("ix_core_auth_sessions_jti_hash", table_name="core_auth_sessions")
    op.drop_table("core_auth_sessions")
