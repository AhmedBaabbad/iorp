"""Index security actor/event probes used by permanent deletion."""
from alembic import op

revision = 'f6a1b2p2'
down_revision = 'f6a1b2p1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_foundation_security_actor_event', 'foundation_security_events', ['actor_id', 'event_type'])


def downgrade():
    op.drop_index('ix_foundation_security_actor_event', table_name='foundation_security_events')
