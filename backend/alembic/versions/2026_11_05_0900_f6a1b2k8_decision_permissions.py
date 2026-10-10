"""RBAC-002: a dedicated permission for every remaining decision, the sales representative's own customers' documents, and
the vague "write" permissions of the commercial module removed.

Upgrade, for every organization:
  * the new permissions (permanent user delete, failed delivery, closing a shipment, rejecting a return, sending and
    closing a purchase order, the non-conformance steps, mapping legacy values) are created and granted to the system
    roles that held the general permission they come from; custom roles receive nothing implicitly;
  * the sales representative system role receives its customers' quotations, samples and draft sales orders, the reads
    at scope "own" (only the customers they own);
  * commercial:*:write is removed with its grants (create, update and delete say exactly what is allowed).
Every grant added and every row removed is recorded, so the downgrade restores exactly the previous state.
"""
from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "f6a1b2k8"
down_revision = "f6a1b2k7"
branch_labels = None
depends_on = None

ADDED = "rbac_k8_added_grants"
REMOVED_PERMISSIONS = "rbac_k8_removed_permissions"
REMOVED_GRANTS = "rbac_k8_removed_grants"

# code -> (system roles granted it, scope)
GRANTS: dict[str, tuple[tuple[str, ...], str]] = {
    "foundation:users:delete": (("organization_admin",), "organization"),
    "shipping:shipments:fail": (("organization_admin", "shipping_manager"), "organization"),
    "shipping:shipments:close": (("organization_admin", "shipping_manager"), "organization"),
    "shipping:returns:reject": (("organization_admin", "shipping_manager", "commercial_manager", "factory_manager"), "organization"),
    "procurement:purchase_orders:send": (("organization_admin", "procurement_manager"), "organization"),
    "procurement:purchase_orders:close": (("organization_admin", "procurement_manager"), "organization"),
    "quality:ncr_reports:contain": (("organization_admin", "factory_manager", "quality_manager", "safety_manager"), "organization"),
    "quality:ncr_reports:investigate": (("organization_admin", "factory_manager", "quality_manager", "safety_manager"), "organization"),
    "quality:ncr_reports:submit": (("organization_admin", "factory_manager", "quality_manager", "safety_manager"), "organization"),
    "masterdata:products:map_legacy": (("organization_admin", "factory_manager", "commercial_manager", "production_manager", "quality_manager"), "organization"),
    "masterdata:lists:map_legacy": (("organization_admin", "factory_manager", "commercial_manager", "shipping_manager", "procurement_manager"), "organization"),
    "commercial:interactions:update": (("organization_admin", "commercial_manager", "sales_rep"), "organization"),
    "commercial:interactions:delete": (("organization_admin", "commercial_manager"), "organization"),
    "commercial:evaluations:update": (("organization_admin", "commercial_manager"), "organization"),
    "commercial:evaluations:delete": (("organization_admin", "commercial_manager"), "organization"),
}
SALES_REP_OWN = ("commercial:quotes:read", "commercial:samples:read", "commercial:orders:read")
SALES_REP = ("commercial:quotes:create", "commercial:quotes:update", "commercial:quotes:issue", "commercial:quotes:accept",
             "commercial:quotes:reject", "commercial:quotes:expire", "commercial:quotes:revise",
             "commercial:samples:create", "commercial:samples:update", "commercial:samples:start", "commercial:samples:deliver",
             "commercial:samples:cancel", "commercial:samples:reopen", "commercial:samples:decide",
             "commercial:evaluations:read", "commercial:evaluations:create", "commercial:orders:create", "commercial:orders:update")
REMOVED = tuple(f"commercial:{r}:write" for r in ("customers", "interactions", "follow_ups", "samples", "quotes", "orders"))


def _tables(bind, *extra):
    meta = sa.MetaData()
    names = ("foundation_organizations", "foundation_permissions", "foundation_roles", "foundation_role_permissions", *extra)
    tables = [sa.Table(name, meta, autoload_with=bind) for name in names]
    # SQLite reflects PostgreSQL UUID declarations as NUMERIC; keep test and production binds typed.
    for table in tables:
        for column in table.c:
            if column.name == "id" or column.name.endswith("_id"):
                column.type = sa.Uuid()
    return tables


def upgrade():
    bind = op.get_bind()
    op.create_table(ADDED, sa.Column("id", sa.Uuid(), primary_key=True))
    op.create_table(REMOVED_PERMISSIONS, sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("organization_id", sa.Uuid()),
                    sa.Column("code", sa.String(120)), sa.Column("name", sa.String(120)), sa.Column("description", sa.Text()),
                    sa.Column("module_name", sa.String(80)), sa.Column("resource_name", sa.String(80)), sa.Column("action_name", sa.String(80)))
    op.create_table(REMOVED_GRANTS, sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("role_id", sa.Uuid()),
                    sa.Column("permission_id", sa.Uuid()), sa.Column("scope", sa.String(20)))
    orgs, permissions, roles, grants, added, removed_p, removed_g = _tables(bind, ADDED, REMOVED_PERMISSIONS, REMOVED_GRANTS)
    now = datetime.now(timezone.utc)

    def permission_id(org, code):
        pid = bind.scalar(sa.select(permissions.c.id).where(permissions.c.organization_id == org, permissions.c.code == code))
        if pid is None:
            pid = uuid4()
            module, resource, action = code.split(":")
            bind.execute(permissions.insert().values(id=pid, organization_id=org, code=code, name=code, description=code,
                                                     module_name=module, resource_name=resource, action_name=action,
                                                     created_at=now, updated_at=now))
        return pid

    def grant(org, code, role_codes, scope):
        pid = permission_id(org, code)
        for rid in bind.scalars(sa.select(roles.c.id).where(roles.c.organization_id == org, roles.c.is_system.is_(True),
                                                            roles.c.code.in_(role_codes))):
            existing = bind.execute(sa.select(grants.c.id, grants.c.scope).where(grants.c.role_id == rid, grants.c.permission_id == pid)).first()
            if existing is None:
                gid = uuid4()
                bind.execute(grants.insert().values(id=gid, role_id=rid, permission_id=pid, scope=scope))
                bind.execute(added.insert().values(id=gid))

    for org in bind.scalars(sa.select(orgs.c.id)):
        for code, (role_codes, scope) in GRANTS.items():
            grant(org, code, role_codes, scope)
        for code in SALES_REP_OWN:
            grant(org, code, ("sales_rep",), "own")
        for code in SALES_REP:
            grant(org, code, ("sales_rep",), "organization")
        for row in bind.execute(sa.select(permissions).where(permissions.c.organization_id == org, permissions.c.code.in_(REMOVED))).mappings():
            for g in bind.execute(sa.select(grants).where(grants.c.permission_id == row["id"])).mappings():
                bind.execute(removed_g.insert().values(id=g["id"], role_id=g["role_id"], permission_id=g["permission_id"], scope=g["scope"]))
            bind.execute(grants.delete().where(grants.c.permission_id == row["id"]))
            bind.execute(removed_p.insert().values(**{k: row[k] for k in ("id", "organization_id", "code", "name", "description",
                                                                          "module_name", "resource_name", "action_name")}))
            bind.execute(permissions.delete().where(permissions.c.id == row["id"]))


def downgrade():
    bind = op.get_bind()
    orgs, permissions, roles, grants, added, removed_p, removed_g = _tables(bind, ADDED, REMOVED_PERMISSIONS, REMOVED_GRANTS)
    bind.execute(grants.delete().where(grants.c.id.in_(sa.select(added.c.id))))
    now = datetime.now(timezone.utc)
    for row in bind.execute(sa.select(removed_p)).mappings():
        bind.execute(permissions.insert().values(**dict(row), created_at=now, updated_at=now))
    for row in bind.execute(sa.select(removed_g)).mappings():
        bind.execute(grants.insert().values(**dict(row)))
    for table in (REMOVED_GRANTS, REMOVED_PERMISSIONS, ADDED):
        op.drop_table(table)
    # The new permission rows stay (unused without their grants), as in the earlier permission migrations.
