"""secure platform bootstrap

Revision ID: f6a1b2d9
Revises: f6a1b2d8
"""
from collections.abc import Sequence
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f6a1b2d9"
down_revision: str | None = "f6a1b2d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    status = postgresql.ENUM(
        "active", "inactive", name="platform_account_status", create_type=False
    )
    status.create(op.get_bind(), checkfirst=True)
    op.add_column("foundation_organizations", sa.Column("default_locale", sa.String(10), nullable=False, server_default="ar"))
    op.add_column("foundation_organizations", sa.Column("logo_path", sa.String(500), nullable=True))
    op.create_table(
        "system_platform_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(500), nullable=False),
        sa.Column("status", status, nullable=False, server_default="active"),
        sa.Column("is_root", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("password_changed_at", sa.DateTime(timezone=True)),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "system_bootstrap_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("is_initialized", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("initialized_at", sa.DateTime(timezone=True)),
        sa.Column("initialized_by_platform_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("system_platform_accounts.id")),
        sa.Column("first_organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("foundation_organizations.id")),
        sa.Column("installation_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("id = 1", name="ck_system_bootstrap_state_singleton"),
    )
    op.execute(
        sa.text("INSERT INTO system_bootstrap_state (id, is_initialized, installation_id) VALUES (1, false, :installation_id)")
        .bindparams(installation_id=uuid.uuid4())
    )


def downgrade() -> None:
    op.drop_table("system_bootstrap_state")
    op.drop_table("system_platform_accounts")
    op.drop_column("foundation_organizations", "logo_path")
    op.drop_column("foundation_organizations", "default_locale")
    postgresql.ENUM(name="platform_account_status").drop(op.get_bind(), checkfirst=True)
