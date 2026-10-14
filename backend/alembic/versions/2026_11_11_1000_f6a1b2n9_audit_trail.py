"""ORG-AUDIT-002: the organization's audit trail in its own table, and each log keeping one kind of event.

- foundation_audit_log: who changed what in the administration (users, roles, permissions, the organization,
  delegations, announcements), when, and the values before and after. The audit page read a frozen legacy table
  (core_auth_security_events, last written in August); it now reads this one.
- The administrative entries that were written to the activity log (user.*, role.*, role_assignment.*, organization.*)
  move to the audit trail; the activity log keeps the daily work.
- The administrative entries copied long ago into the security log (user.updated, role_assignment.added,
  organization_activated/suspended) move to the audit trail too.
- Token mechanics (access/refresh token issued, rotated, revoked, session renewed) are deleted from the security log, as
  agreed: they say nothing a sign-in does not, and they made up most of it. They are no longer written.
The downgrade moves the audit entries back to the activity log; the deleted token entries cannot come back.
"""
import sqlalchemy as sa
from alembic import op

revision = "f6a1b2n9"
down_revision = "f6a1b2n8"
branch_labels = None
depends_on = None

GOVERNANCE = ("user.", "role.", "role_assignment.", "organization.")
LEGACY_IN_SECURITY = {"user.updated": ("user.updated", "user"), "role_assignment.added": ("role_assignment.added", "role_assignment"),
                      "organization_activated": ("organization.activated", "organization"),
                      "organization_suspended": ("organization.suspended", "organization")}
TOKEN_NOISE = [f"{prefix}{name}" for prefix in ("", "tenant.") for name in (
    "access_token_issued", "refresh_token_issued", "refresh_token_rotated", "refresh_token_revoked", "token_refreshed")]


def _tables(bind):
    meta = sa.MetaData()
    tables = [sa.Table(n, meta, autoload_with=bind) for n in ("foundation_audit_log", "foundation_activity_log", "foundation_security_events", "foundation_users")]
    for table in tables:
        for column in table.c:
            if column.name in ("id", "organization_id", "actor_id") or (column.name == "entity_id" and table.name != "foundation_audit_log"):
                column.type = sa.Uuid()
    return tables


def upgrade():
    op.create_table(
        "foundation_audit_log",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("foundation_organizations.id"), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=True),
        sa.Column("entity_name", sa.String(255), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_name", sa.String(255), nullable=True),
        sa.Column("details", sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_foundation_audit_org_created", "foundation_audit_log", ["organization_id", "created_at"])
    op.create_index("ix_foundation_audit_org_entity", "foundation_audit_log", ["organization_id", "entity_type"])
    op.create_index("ix_foundation_audit_action", "foundation_audit_log", ["action"])
    op.create_index("ix_foundation_audit_actor", "foundation_audit_log", ["actor_id"])

    bind = op.get_bind()
    audit, activity, security, users = _tables(bind)
    governance = sa.or_(*[activity.c.action.like(f"{p}%") for p in GOVERNANCE])
    moved = 0
    for r in bind.execute(sa.select(activity).where(governance)).mappings().all():
        bind.execute(audit.insert().values(id=r["id"], organization_id=r["organization_id"], action=r["action"], entity_type=r["entity_type"],
                                           entity_id=str(r["entity_id"]) if r["entity_id"] else None, entity_name=r["entity_name"],
                                           actor_id=r["actor_id"], actor_name=r["actor_name"], details=r["details"], created_at=r["created_at"]))
        moved += 1
    bind.execute(activity.delete().where(governance))

    names = dict(bind.execute(sa.select(users.c.id, users.c.full_name)).all())
    copied = 0
    for r in bind.execute(sa.select(security).where(security.c.event_type.in_(list(LEGACY_IN_SECURITY)))).mappings().all():
        action, entity = LEGACY_IN_SECURITY[r["event_type"]]
        bind.execute(audit.insert().values(id=r["id"], organization_id=r["organization_id"], action=action, entity_type=entity,
                                           actor_id=r["actor_id"], actor_name=names.get(r["actor_id"]) or r["actor_email"],
                                           details=r["details"], created_at=r["created_at"]))
        copied += 1
    bind.execute(security.delete().where(security.c.event_type.in_(list(LEGACY_IN_SECURITY))))
    removed = bind.execute(security.delete().where(security.c.event_type.in_(TOKEN_NOISE))).rowcount
    print(f"audit trail: {moved} entries moved from the activity log, {copied} from the security log; {removed} token entries removed")


def downgrade():
    bind = op.get_bind()
    audit, activity, _security, _users = _tables(bind)
    for r in bind.execute(sa.select(audit)).mappings().all():
        entity_id = r["entity_id"]
        try:
            entity_id = sa.Uuid().python_type(entity_id) if entity_id else None
        except ValueError:
            entity_id = None
        bind.execute(activity.insert().values(id=r["id"], organization_id=r["organization_id"], action=r["action"], entity_type=r["entity_type"],
                                              entity_id=entity_id, entity_name=r["entity_name"], actor_id=r["actor_id"], actor_name=r["actor_name"],
                                              details=r["details"], created_at=r["created_at"]))
    op.drop_table("foundation_audit_log")
