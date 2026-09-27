"""Add separate tenant and platform password reset token tables."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f6a1b2g3"
down_revision = "f6a1b2g2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("foundation_password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("foundation_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("foundation_organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_foundation_password_reset_token_hash", "foundation_password_reset_tokens", ["token_hash"], unique=True)
    op.create_index("ix_foundation_password_reset_user", "foundation_password_reset_tokens", ["user_id"])
    op.create_index("ix_foundation_password_reset_expires", "foundation_password_reset_tokens", ["expires_at"])
    op.create_table("system_password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("system_platform_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_system_password_reset_token_hash", "system_password_reset_tokens", ["token_hash"], unique=True)
    op.create_index("ix_system_password_reset_account", "system_password_reset_tokens", ["account_id"])
    op.create_index("ix_system_password_reset_expires", "system_password_reset_tokens", ["expires_at"])


def downgrade():
    op.drop_table("system_password_reset_tokens")
    op.drop_table("foundation_password_reset_tokens")
