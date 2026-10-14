"""PROJECT-NOTIFY-001: notifications and announcements.

- notifications_announcements: a message written by a person to named users, a role's members or the whole organization.
- notifications_items: one notification of one user (a module's event, or an announcement), with when it was read,
  acknowledged, or dealt with.
- notifications:announcements:send / manage for every organization, granted to the organization administrator. Each
  permission added is recorded for the downgrade.
"""
from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "f6a1b2n8"
down_revision = "f6a1b2n7"
branch_labels = None
depends_on = None

CODES = {"notifications:announcements:send": ("Send announcements", "Writes a message or announcement and follows who read and acknowledged it."),
         "notifications:announcements:manage": ("Manage all announcements", "Follows every announcement of the organization and withdraws any.")}
ADDED = "rbac_n8_added_permissions"


def upgrade():
    op.create_table(
        "notifications_announcements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("foundation_organizations.id"), nullable=False, index=True),
        sa.Column("author_user_id", sa.Uuid(), sa.ForeignKey("foundation_users.id"), nullable=False),
        sa.Column("author_name", sa.String(255), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="info"),
        sa.Column("requires_ack", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("audience", sa.String(20), nullable=False),
        sa.Column("audience_role_id", sa.Uuid(), sa.ForeignKey("foundation_roles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("audience_label", sa.String(255), nullable=True),
        sa.Column("recipient_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_by_name", sa.String(255), nullable=True),
        sa.CheckConstraint("severity IN ('info', 'important', 'urgent')", name="ck_announcement_severity"),
        sa.CheckConstraint("audience IN ('users', 'role', 'everyone')", name="ck_announcement_audience"),
    )
    op.create_table(
        "notifications_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("foundation_organizations.id"), nullable=False),
        sa.Column("recipient_user_id", sa.Uuid(), sa.ForeignKey("foundation_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event", sa.String(120), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="info"),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("link", sa.String(500), nullable=True),
        sa.Column("resource_type", sa.String(60), nullable=True),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_name", sa.String(255), nullable=True),
        sa.Column("announcement_id", sa.Uuid(), sa.ForeignKey("notifications_announcements.id", ondelete="CASCADE"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("severity IN ('info', 'important', 'urgent')", name="ck_notification_severity"),
        sa.CheckConstraint("category IN ('access', 'security', 'delegation', 'work', 'announcement')", name="ck_notification_category"),
    )
    op.create_index("ix_notification_inbox", "notifications_items", ["recipient_user_id", "read_at", "created_at"])
    op.create_index("ix_notification_resource", "notifications_items", ["organization_id", "resource_type", "resource_id"])

    bind = op.get_bind()
    op.create_table(ADDED, sa.Column("id", sa.Uuid(), primary_key=True))
    meta = sa.MetaData()
    orgs, permissions, roles, grants, added = (sa.Table(n, meta, autoload_with=bind) for n in (
        "foundation_organizations", "foundation_permissions", "foundation_roles", "foundation_role_permissions", ADDED))
    for table in (orgs, permissions, roles, grants, added):
        for column in table.c:
            if column.name == "id" or column.name.endswith("_id"):
                column.type = sa.Uuid()
    now = datetime.now(timezone.utc)
    created = 0
    for org in bind.scalars(sa.select(orgs.c.id)):
        admin = bind.scalar(sa.select(roles.c.id).where(roles.c.organization_id == org, roles.c.code == "organization_admin", roles.c.is_system.is_(True)))
        for code, (name, description) in CODES.items():
            pid = bind.scalar(sa.select(permissions.c.id).where(permissions.c.organization_id == org, permissions.c.code == code))
            if pid is None:
                pid = uuid4()
                module, resource, action = code.split(":")
                bind.execute(permissions.insert().values(id=pid, organization_id=org, code=code, name=name, description=description,
                                                         module_name=module, resource_name=resource, action_name=action, created_at=now, updated_at=now))
                bind.execute(added.insert().values(id=pid))
                created += 1
            if admin and bind.scalar(sa.select(grants.c.id).where(grants.c.role_id == admin, grants.c.permission_id == pid)) is None:
                bind.execute(grants.insert().values(id=uuid4(), role_id=admin, permission_id=pid, scope="organization"))
    print(f"notifications: {created} permission(s) created and granted to the organization administrators")


def downgrade():
    bind = op.get_bind()
    meta = sa.MetaData()
    permissions, grants, added = (sa.Table(n, meta, autoload_with=bind) for n in ("foundation_permissions", "foundation_role_permissions", ADDED))
    ids = sa.select(added.c.id)
    bind.execute(grants.delete().where(grants.c.permission_id.in_(ids)))
    bind.execute(permissions.delete().where(permissions.c.id.in_(ids)))
    op.drop_table(ADDED)
    op.drop_table("notifications_items")
    op.drop_table("notifications_announcements")
