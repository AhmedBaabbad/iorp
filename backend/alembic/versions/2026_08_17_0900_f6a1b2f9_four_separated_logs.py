"""Create four separated append-only log tables.

Revision ID: f6a1b2f9
Revises: f6a1b2f8
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f6a1b2f9"
down_revision = "f6a1b2f8"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")

def upgrade():
    op.create_table("system_security_events",
        sa.Column("id", UUID, primary_key=True), sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("actor_id", UUID, sa.ForeignKey("system_platform_accounts.id"), nullable=True),
        sa.Column("actor_email", sa.String(255)), sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.String(500)), sa.Column("details", JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_system_security_events_event_type", "system_security_events", ["event_type"])
    op.create_index("ix_system_security_events_actor_id", "system_security_events", ["actor_id"])
    op.create_index("ix_system_security_events_created_at", "system_security_events", ["created_at"])
    op.create_table("system_platform_activity_log",
        sa.Column("id", UUID, primary_key=True), sa.Column("action", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False), sa.Column("entity_id", UUID),
        sa.Column("entity_name", sa.String(255)), sa.Column("actor_id", UUID, sa.ForeignKey("system_platform_accounts.id")),
        sa.Column("actor_name", sa.String(255)), sa.Column("details", JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    for name, cols in (("ix_system_platform_activity_action", ["action"]), ("ix_system_platform_activity_entity_type", ["entity_type"]), ("ix_system_platform_activity_actor_id", ["actor_id"]), ("ix_system_platform_activity_created_at", ["created_at"])):
        op.create_index(name, "system_platform_activity_log", cols)
    op.create_table("foundation_security_events",
        sa.Column("id", UUID, primary_key=True), sa.Column("organization_id", UUID, sa.ForeignKey("foundation_organizations.id"), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False), sa.Column("actor_id", UUID, sa.ForeignKey("foundation_users.id")),
        sa.Column("actor_email", sa.String(255)), sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.String(500)), sa.Column("details", JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_foundation_security_events_organization_id", "foundation_security_events", ["organization_id"])
    op.create_index("ix_foundation_security_org_event", "foundation_security_events", ["organization_id", "event_type"])
    op.create_index("ix_foundation_security_org_created", "foundation_security_events", ["organization_id", "created_at"])
    op.create_index("ix_foundation_security_actor_id", "foundation_security_events", ["actor_id"])
    op.create_table("foundation_activity_log",
        sa.Column("id", UUID, primary_key=True), sa.Column("organization_id", UUID, sa.ForeignKey("foundation_organizations.id"), nullable=False),
        sa.Column("action", sa.String(80), nullable=False), sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", UUID), sa.Column("entity_name", sa.String(255)),
        sa.Column("actor_id", UUID, sa.ForeignKey("foundation_users.id")), sa.Column("actor_name", sa.String(255)),
        sa.Column("details", JSON), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_foundation_activity_log_organization_id", "foundation_activity_log", ["organization_id"])
    op.create_index("ix_foundation_activity_org_entity", "foundation_activity_log", ["organization_id", "entity_type"])
    op.create_index("ix_foundation_activity_org_created", "foundation_activity_log", ["organization_id", "created_at"])
    op.create_index("ix_foundation_activity_actor_id", "foundation_activity_log", ["actor_id"])
    op.create_index("ix_foundation_activity_action", "foundation_activity_log", ["action"])

    # Safe one-time copy. The legacy table remains as a deprecated safety net.
    op.execute(sa.text("""INSERT INTO system_security_events (id,event_type,actor_id,actor_email,ip_address,user_agent,details,created_at)
      SELECT e.id, left(e.event_type,80), CASE WHEN EXISTS (SELECT 1 FROM system_platform_accounts a WHERE a.id=e.account_id) THEN e.account_id ELSE NULL END,
      e.actor_email_snapshot,left(e.ip_address,45),e.user_agent,COALESCE(e.changes,e.metadata),e.occurred_at
      FROM core_auth_security_events e WHERE e.organization_id IS NULL ON CONFLICT (id) DO NOTHING"""))
    op.execute(sa.text("""INSERT INTO foundation_security_events (id,organization_id,event_type,actor_id,actor_email,ip_address,user_agent,details,created_at)
      SELECT e.id,e.organization_id,left(e.event_type,80),CASE WHEN EXISTS (SELECT 1 FROM foundation_users u WHERE u.id=e.account_id) THEN e.account_id ELSE NULL END,
      e.actor_email_snapshot,left(e.ip_address,45),e.user_agent,COALESCE(e.changes,e.metadata),e.occurred_at
      FROM core_auth_security_events e WHERE e.organization_id IS NOT NULL ON CONFLICT (id) DO NOTHING"""))
    op.execute(sa.text("""INSERT INTO foundation_permissions (id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at)
      SELECT gen_random_uuid(),o.id,p.code,p.name,p.description,'foundation',p.resource,'read',now(),now()
      FROM foundation_organizations o CROSS JOIN (VALUES
        ('foundation:security_log:read','View Security Events','View organization security events.','security_log'),
        ('foundation:activity_log:read','View Activity Log','View organization activity log.','activity_log')) p(code,name,description,resource)
      WHERE NOT EXISTS (SELECT 1 FROM foundation_permissions x WHERE x.organization_id=o.id AND x.code=p.code)"""))
    op.execute(sa.text("""INSERT INTO foundation_role_permissions (id,role_id,permission_id)
      SELECT gen_random_uuid(),r.id,p.id FROM foundation_roles r JOIN foundation_permissions p ON p.organization_id=r.organization_id
      WHERE r.code='organization_admin' AND p.code IN ('foundation:security_log:read','foundation:activity_log:read')
      AND NOT EXISTS (SELECT 1 FROM foundation_role_permissions rp WHERE rp.role_id=r.id AND rp.permission_id=p.id)"""))

def downgrade():
    op.execute(sa.text("DELETE FROM foundation_role_permissions WHERE permission_id IN (SELECT id FROM foundation_permissions WHERE code IN ('foundation:security_log:read','foundation:activity_log:read'))"))
    op.execute(sa.text("DELETE FROM foundation_permissions WHERE code IN ('foundation:security_log:read','foundation:activity_log:read')"))
    op.drop_table("foundation_activity_log")
    op.drop_table("foundation_security_events")
    op.drop_table("system_platform_activity_log")
    op.drop_table("system_security_events")
