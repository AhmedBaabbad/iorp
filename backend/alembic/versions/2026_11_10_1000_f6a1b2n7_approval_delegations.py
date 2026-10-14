"""PROJECT-GOV-004: approval delegations and the record of every signed step.

- foundation_approval_delegations: a temporary grant of one approval permission its delegator holds, in force once the
  other side agrees (a delegation manager for a holder's request, the holder for a manager's), never deleted.
- foundation_approval_records: whose authority each signed step was and who signed it, fixed when signed.
- foundation:delegations:read / manage for every organization, granted to the organization administrator. A holder
  delegates their own approvals with no further permission. Each permission added is recorded for the downgrade.
"""
from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "f6a1b2n7"
down_revision = "f6a1b2n6"
branch_labels = None
depends_on = None

CODES = {"foundation:delegations:read": ("View delegations", "Shows every approval delegation of the organization and its state."),
         "foundation:delegations:manage": ("Manage delegations", "Approves or rejects delegation requests, delegates on a holder's behalf and revokes any delegation.")}
ADDED = "rbac_n7_added_permissions"


def upgrade():
    op.create_table(
        "foundation_approval_delegations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("foundation_organizations.id"), nullable=False, index=True),
        sa.Column("delegator_user_id", sa.Uuid(), sa.ForeignKey("foundation_users.id"), nullable=False),
        sa.Column("delegate_user_id", sa.Uuid(), sa.ForeignKey("foundation_users.id"), nullable=False),
        sa.Column("permission_code", sa.String(120), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("foundation_users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approval", sa.String(20), nullable=False, server_default="awaiting_manager"),
        sa.Column("decided_by_user_id", sa.Uuid(), sa.ForeignKey("foundation_users.id"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.Uuid(), sa.ForeignKey("foundation_users.id"), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("effective_to >= effective_from", name="ck_delegation_period"),
        sa.CheckConstraint("delegator_user_id <> delegate_user_id", name="ck_delegation_not_self"),
        sa.CheckConstraint("approval IN ('awaiting_manager', 'awaiting_holder', 'approved', 'rejected')", name="ck_delegation_approval"),
    )
    op.create_index("ix_delegation_delegate", "foundation_approval_delegations", ["organization_id", "delegate_user_id", "permission_code"])
    op.create_table(
        "foundation_approval_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("foundation_organizations.id"), nullable=False),
        sa.Column("resource_type", sa.String(60), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("step", sa.String(60), nullable=False),
        sa.Column("permission_code", sa.String(120), nullable=False),
        sa.Column("authority_user_id", sa.Uuid(), sa.ForeignKey("foundation_users.id"), nullable=False),
        sa.Column("signed_by_user_id", sa.Uuid(), sa.ForeignKey("foundation_users.id"), nullable=False),
        sa.Column("delegation_id", sa.Uuid(), sa.ForeignKey("foundation_approval_delegations.id"), nullable=True),
        sa.Column("authority_name", sa.String(255), nullable=False),
        sa.Column("signer_name", sa.String(255), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_approval_record_resource", "foundation_approval_records", ["organization_id", "resource_type", "resource_id"])

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
    print(f"delegations: {created} permission(s) created and granted to the organization administrators")


def downgrade():
    bind = op.get_bind()
    meta = sa.MetaData()
    permissions, grants, added = (sa.Table(n, meta, autoload_with=bind) for n in ("foundation_permissions", "foundation_role_permissions", ADDED))
    ids = sa.select(added.c.id)
    bind.execute(grants.delete().where(grants.c.permission_id.in_(ids)))
    bind.execute(permissions.delete().where(permissions.c.id.in_(ids)))
    op.drop_table(ADDED)
    op.drop_table("foundation_approval_records")
    op.drop_table("foundation_approval_delegations")
