"""SEC-001/002: sessions people can see and end, a limit per user, and passwords nobody chooses for someone else.

- core_auth_sessions: started_at (a sign-in's absolute lifetime counts from it), ip_address and user_agent (shown in "my
  sessions", and to tell a new device). Existing rows start at their creation.
- foundation_organizations.max_sessions_per_user (2): a further sign-in ends the oldest.
- (Passwords: an administrator only e-mails a reset link — SEC-002; nothing to store.)
"""
import sqlalchemy as sa
from alembic import op

revision = "f6a1b2o5"
down_revision = "f6a1b2o4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("core_auth_sessions", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("core_auth_sessions", sa.Column("ip_address", sa.String(64), nullable=True))
    op.add_column("core_auth_sessions", sa.Column("user_agent", sa.String(500), nullable=True))
    op.execute("UPDATE core_auth_sessions SET started_at = created_at WHERE started_at IS NULL")
    op.add_column("foundation_organizations", sa.Column("max_sessions_per_user", sa.Integer(), nullable=False, server_default="2"))


def downgrade():
    op.drop_column("foundation_organizations", "max_sessions_per_user")
    op.drop_column("core_auth_sessions", "user_agent")
    op.drop_column("core_auth_sessions", "ip_address")
    op.drop_column("core_auth_sessions", "started_at")
