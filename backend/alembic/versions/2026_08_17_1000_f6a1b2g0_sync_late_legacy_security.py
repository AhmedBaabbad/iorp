"""Synchronize legacy security events created during deployment restart window."""
from alembic import op
import sqlalchemy as sa

revision = "f6a1b2g0"
down_revision = "f6a1b2f9"
branch_labels = None
depends_on = None

def upgrade():
    op.execute(sa.text("""INSERT INTO system_security_events (id,event_type,actor_id,actor_email,ip_address,user_agent,details,created_at)
      SELECT e.id,left(e.event_type,80),CASE WHEN EXISTS(SELECT 1 FROM system_platform_accounts a WHERE a.id=e.account_id) THEN e.account_id ELSE NULL END,
      e.actor_email_snapshot,left(e.ip_address,45),e.user_agent,COALESCE(e.changes,e.metadata),e.occurred_at
      FROM core_auth_security_events e WHERE e.organization_id IS NULL ON CONFLICT(id) DO NOTHING"""))
    op.execute(sa.text("""INSERT INTO foundation_security_events (id,organization_id,event_type,actor_id,actor_email,ip_address,user_agent,details,created_at)
      SELECT e.id,e.organization_id,left(e.event_type,80),CASE WHEN EXISTS(SELECT 1 FROM foundation_users u WHERE u.id=e.account_id) THEN e.account_id ELSE NULL END,
      e.actor_email_snapshot,left(e.ip_address,45),e.user_agent,COALESCE(e.changes,e.metadata),e.occurred_at
      FROM core_auth_security_events e WHERE e.organization_id IS NOT NULL ON CONFLICT(id) DO NOTHING"""))

def downgrade():
    pass
