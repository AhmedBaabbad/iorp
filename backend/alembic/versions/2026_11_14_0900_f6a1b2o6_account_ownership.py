"""Account ownership, archival and verified email changes."""
from alembic import op
import sqlalchemy as sa
revision = "f6a1b2o6"
down_revision = "f6a1b2o5"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("foundation_users", sa.Column("timezone", sa.String(64), nullable=True))
    op.add_column("foundation_users", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("foundation_users", sa.Column("account_change_reason", sa.String(500), nullable=True))
    op.create_table("foundation_user_email_changes",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("foundation_users.id"), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("foundation_organizations.id"), nullable=False),
        sa.Column("old_email", sa.String(255), nullable=False),
        sa.Column("new_email", sa.String(255), nullable=False),
        sa.Column("old_hash", sa.String(64), nullable=False),
        sa.Column("new_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False))

def downgrade():
    db = op.get_bind()
    if db.execute(sa.text("SELECT 1 FROM foundation_users WHERE timezone IS NOT NULL OR archived_at IS NOT NULL OR account_change_reason IS NOT NULL LIMIT 1")).first() or db.execute(sa.text("SELECT 1 FROM foundation_user_email_changes LIMIT 1")).first():
        raise RuntimeError("Account policy data exists; downgrade would discard it.")
    op.drop_table("foundation_user_email_changes")
    for name in ("account_change_reason", "archived_at", "timezone"):
        op.drop_column("foundation_users", name)
