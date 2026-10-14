"""ORG-AUDIT-003: the activity log keeps 12 months; each older month is archived (downloaded) then deleted, or deleted
automatically 30 days after it is due. And a reader may put away their own notifications.

- foundation_activity_archives: per organization and month — told, reminded, downloaded (by whom), deleted.
- foundation:activity_log:archive for every organization, granted to the organization administrator (recorded for the
  downgrade).
- notifications_items.hidden_at.
"""
from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "f6a1b2o2"
down_revision = "f6a1b2o1"
branch_labels = None
depends_on = None

CODE, NAME = "foundation:activity_log:archive", "Archive and delete old activity"
ADDED = "rbac_o2_added_permissions"


def upgrade():
    op.create_table(
        "foundation_activity_archives",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("foundation_organizations.id"), nullable=False),
        sa.Column("month", sa.String(7), nullable=False),
        sa.Column("rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reminded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("downloaded_by_name", sa.String(255), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_name", sa.String(255), nullable=True),
        sa.UniqueConstraint("organization_id", "month", name="uq_activity_archive_month"),
    )
    op.add_column("notifications_items", sa.Column("hidden_at", sa.DateTime(timezone=True), nullable=True))

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
    for org in bind.scalars(sa.select(orgs.c.id)):
        admin = bind.scalar(sa.select(roles.c.id).where(roles.c.organization_id == org, roles.c.code == "organization_admin", roles.c.is_system.is_(True)))
        pid = bind.scalar(sa.select(permissions.c.id).where(permissions.c.organization_id == org, permissions.c.code == CODE))
        if pid is None:
            pid = uuid4()
            bind.execute(permissions.insert().values(id=pid, organization_id=org, code=CODE, name=NAME, description=NAME, module_name="foundation",
                                                     resource_name="activity_log", action_name="archive", created_at=now, updated_at=now))
            bind.execute(added.insert().values(id=pid))
        if admin and bind.scalar(sa.select(grants.c.id).where(grants.c.role_id == admin, grants.c.permission_id == pid)) is None:
            bind.execute(grants.insert().values(id=uuid4(), role_id=admin, permission_id=pid, scope="organization"))


def downgrade():
    bind = op.get_bind()
    meta = sa.MetaData()
    permissions, grants, added = (sa.Table(n, meta, autoload_with=bind) for n in ("foundation_permissions", "foundation_role_permissions", ADDED))
    ids = sa.select(added.c.id)
    bind.execute(grants.delete().where(grants.c.permission_id.in_(ids)))
    bind.execute(permissions.delete().where(permissions.c.id.in_(ids)))
    op.drop_table(ADDED)
    op.drop_column("notifications_items", "hidden_at")
    op.drop_table("foundation_activity_archives")
