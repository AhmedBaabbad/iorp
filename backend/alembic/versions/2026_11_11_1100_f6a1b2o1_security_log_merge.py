"""ORG-AUDIT-003: the security log counts a routine sign-in repeated from the same device instead of adding entries.

foundation_security_events.occurrences (how many times) and last_seen_at (the last one). Existing entries count once.
"""
import sqlalchemy as sa
from alembic import op

revision = "f6a1b2o1"
down_revision = "f6a1b2n9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("foundation_security_events", sa.Column("occurrences", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("foundation_security_events", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("foundation_security_events", "last_seen_at")
    op.drop_column("foundation_security_events", "occurrences")
