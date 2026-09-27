"""expand security events into platform administrative audit log

Revision ID: f6a1b2f7
Revises: f6a1b2f6
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f6a1b2f7"
down_revision: str | None = "f6a1b2f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "core_auth_security_events"
    op.add_column(table, sa.Column("category", sa.String(24), server_default="security", nullable=False))
    op.add_column(table, sa.Column("outcome", sa.String(16), server_default="success", nullable=False))
    op.add_column(table, sa.Column("severity", sa.String(16), server_default="info", nullable=False))
    op.add_column(table, sa.Column("actor_type", sa.String(16), server_default="system", nullable=False))
    op.add_column(table, sa.Column("actor_email_snapshot", sa.String(255), nullable=True))
    op.add_column(table, sa.Column("actor_name_snapshot", sa.String(255), nullable=True))
    op.add_column(table, sa.Column("target_type", sa.String(64), nullable=True))
    op.add_column(table, sa.Column("target_id", sa.String(128), nullable=True))
    op.add_column(table, sa.Column("target_display_snapshot", sa.String(255), nullable=True))
    op.add_column(table, sa.Column("request_id", sa.String(64), nullable=True))
    op.add_column(table, sa.Column("correlation_id", sa.String(64), nullable=True))
    op.add_column(table, sa.Column("changes", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column(table, sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column(table, sa.Column("error_code", sa.String(64), nullable=True))
    op.add_column(table, sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE core_auth_security_events SET actor_type = COALESCE(account_type, 'system'), created_at = occurred_at")
    op.alter_column(table, "created_at", nullable=False)
    op.create_check_constraint("ck_auth_event_category", table, "category IN ('identity','organization','authentication','authorization','security','configuration','audit')")
    op.create_check_constraint("ck_auth_event_outcome", table, "outcome IN ('success','failure','denied')")
    op.create_check_constraint("ck_auth_event_severity", table, "severity IN ('info','warning','critical')")
    op.create_check_constraint("ck_auth_event_actor_type", table, "actor_type IN ('platform','tenant','system','anonymous')")
    op.create_index("ix_core_auth_security_events_category", table, ["category"])
    op.create_index("ix_core_auth_security_events_outcome", table, ["outcome"])
    op.create_index("ix_core_auth_security_events_severity", table, ["severity"])
    op.create_index("ix_core_auth_security_events_account_id", table, ["account_id"])
    op.create_index("ix_core_auth_security_events_organization_id", table, ["organization_id"])
    op.create_index("ix_core_auth_security_events_occurred_at", table, ["occurred_at"])
    op.create_index("ix_core_auth_security_events_request_id", table, ["request_id"])
    op.create_index("ix_core_auth_security_events_correlation_id", table, ["correlation_id"])
    op.create_index("ix_auth_events_target", table, ["target_type", "target_id"])


def downgrade() -> None:
    table = "core_auth_security_events"
    for name in ["ix_auth_events_target", "ix_core_auth_security_events_correlation_id", "ix_core_auth_security_events_request_id", "ix_core_auth_security_events_occurred_at", "ix_core_auth_security_events_organization_id", "ix_core_auth_security_events_account_id", "ix_core_auth_security_events_severity", "ix_core_auth_security_events_outcome", "ix_core_auth_security_events_category"]:
        op.drop_index(name, table_name=table)
    for name in ["ck_auth_event_actor_type", "ck_auth_event_severity", "ck_auth_event_outcome", "ck_auth_event_category"]:
        op.drop_constraint(name, table, type_="check")
    for column in ["created_at", "error_code", "metadata", "changes", "correlation_id", "request_id", "target_display_snapshot", "target_id", "target_type", "actor_name_snapshot", "actor_email_snapshot", "actor_type", "severity", "outcome", "category"]:
        op.drop_column(table, column)
