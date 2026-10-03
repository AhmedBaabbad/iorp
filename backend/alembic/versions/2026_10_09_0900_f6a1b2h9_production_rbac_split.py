"""Production permissions split per action (PROD-RBAC-001).

Every bundled code becomes the explicit actions it used to allow, so no role gains or
loses access: a role holding the old code gets each replacement with the same scope.

    production:work_centers:write        -> work_centers create / update / delete
    production:production_orders:write   -> production_orders update / manage_items
    production:orders:<action>           -> production_orders:<action>
    production:results:write             -> results create / update / delete
    production:downtime_events:write     -> downtime_events create / update / delete / close
    production:waste_records:write       -> waste_records create / update / delete
    production:shift_definitions:*       -> removed (no route used it; shifts have production:shifts:*)

Removed permission rows, removed grants, added rows and added grants are kept in
production_rbac_h9_backup so the downgrade restores the exact previous grants. Each step is
idempotent; the whole upgrade runs in the migration transaction.
"""
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "f6a1b2h9"
down_revision = "f6a1b2h8"
branch_labels = None
depends_on = None

BACKUP = "production_rbac_h9_backup"
ACTIONS = ("create", "cancel", "release", "start", "hold", "complete", "close")
MAPPING: dict[str, tuple[str, ...]] = {
    "production:work_centers:write": tuple(f"production:work_centers:{a}" for a in ("create", "update", "delete")),
    "production:production_orders:write": ("production:production_orders:update", "production:production_orders:manage_items"),
    **{f"production:orders:{a}": (f"production:production_orders:{a}",) for a in ACTIONS},
    "production:results:write": tuple(f"production:results:{a}" for a in ("create", "update", "delete")),
    "production:downtime_events:write": tuple(f"production:downtime_events:{a}" for a in ("create", "update", "delete", "close")),
    "production:waste_records:write": tuple(f"production:waste_records:{a}" for a in ("create", "update", "delete")),
    "production:shift_definitions:read": (),
    "production:shift_definitions:write": (),
}
RESOURCE_TITLE = {"work_centers": "Work Centers", "production_orders": "Production Orders", "results": "Production Results",
                  "downtime_events": "Downtime Events", "waste_records": "Waste Records"}
ACTION_TITLE = {"manage_items": "Manage Items of"}


def _definition(code: str) -> dict[str, str]:
    _, resource, action = code.split(":")
    name = f"{ACTION_TITLE.get(action, action.replace('_', ' ').title())} {RESOURCE_TITLE[resource]}"
    return dict(code=code, name=name, description=f"Allows the account to {name[0].lower()}{name[1:]}.",
                module_name="production", resource_name=resource, action_name=action)


def _codes(bind, sql: str, **params):
    return bind.execute(sa.text(sql).bindparams(*(sa.bindparam(k, expanding=True) for k, v in params.items() if isinstance(v, list))), params)


def upgrade():
    bind = op.get_bind()
    op.create_table(
        BACKUP,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False),  # permission_removed | grant_removed | permission_added | grant_added
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid()),
        sa.Column("code", sa.String(120), nullable=False),
        sa.Column("scope", sa.String(20)),
        sa.Column("name", sa.String(120)),
        sa.Column("description", sa.Text()),
        sa.Column("module_name", sa.String(80)),
        sa.Column("resource_name", sa.String(80)),
        sa.Column("action_name", sa.String(80)),
    )
    backup = sa.table(BACKUP, *(sa.column(c) for c in ("id", "kind", "organization_id", "role_id", "code", "scope", "name", "description",
                                                       "module_name", "resource_name", "action_name")))
    old_codes = list(MAPPING)
    summary: dict[tuple[str, str], int] = {}

    for org in bind.scalars(sa.text("SELECT id FROM foundation_organizations ORDER BY created_at")).all():
        old = {r.code: r for r in _codes(bind, "SELECT * FROM foundation_permissions WHERE organization_id=:org AND code IN :codes",
                                         org=org, codes=old_codes).mappings()}
        if not old:
            continue
        # 1. The replacement permission rows (created only where missing).
        for code in sorted({c for targets in MAPPING.values() for c in targets}):
            created = bind.execute(sa.text(
                "INSERT INTO foundation_permissions (id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) "
                "VALUES (:id,:org,:code,:name,:description,:module_name,:resource_name,:action_name,now(),now()) "
                "ON CONFLICT (organization_id,code) DO NOTHING RETURNING id"), dict(id=uuid4(), org=org, **_definition(code))).scalar()
            if created:
                bind.execute(backup.insert().values(id=uuid4(), kind="permission_added", organization_id=org, code=code))
        new_ids = dict(bind.execute(sa.text("SELECT code, id FROM foundation_permissions WHERE organization_id=:org"), dict(org=org)).all())

        # 2. Every holder of an old code gets its replacements with the same scope.
        grants = bind.execute(sa.text(
            "SELECT rp.id, rp.role_id, rp.scope, p.code, r.code AS role_code FROM foundation_role_permissions rp "
            "JOIN foundation_permissions p ON p.id=rp.permission_id JOIN foundation_roles r ON r.id=rp.role_id "
            "WHERE p.organization_id=:org AND p.code IN :codes").bindparams(sa.bindparam("codes", expanding=True)),
            dict(org=org, codes=old_codes)).mappings().all()
        for g in grants:
            for target in MAPPING[g["code"]]:
                added = bind.execute(sa.text(
                    "INSERT INTO foundation_role_permissions (id,role_id,permission_id,scope) VALUES (:id,:role,:permission,:scope) "
                    "ON CONFLICT (role_id,permission_id) DO NOTHING RETURNING id"),
                    dict(id=uuid4(), role=g["role_id"], permission=new_ids[target], scope=g["scope"])).scalar()
                if added:
                    bind.execute(backup.insert().values(id=uuid4(), kind="grant_added", organization_id=org, role_id=g["role_id"], code=target))
            bind.execute(backup.insert().values(id=uuid4(), kind="grant_removed", organization_id=org, role_id=g["role_id"], code=g["code"], scope=g["scope"]))
            key = (g["role_code"], g["code"])
            summary[key] = summary.get(key, 0) + 1

        # 3. The old codes disappear (grants first, then the rows).
        for row in old.values():
            bind.execute(backup.insert().values(id=uuid4(), kind="permission_removed", organization_id=org, code=row["code"], name=row["name"],
                                                description=row["description"], module_name=row["module_name"],
                                                resource_name=row["resource_name"], action_name=row["action_name"]))
        ids = [row["id"] for row in old.values()]
        _codes(bind, "DELETE FROM foundation_role_permissions WHERE permission_id IN :ids", ids=ids)
        _codes(bind, "DELETE FROM foundation_permissions WHERE id IN :ids", ids=ids)

    for (role, code), count in sorted(summary.items()):
        targets = ", ".join(MAPPING[code]) or "removed (unused by any route)"
        print(f"PROD-RBAC-001 {role}: {code} -> {targets} [{count} organization(s)]")


def downgrade():
    bind = op.get_bind()
    rows = bind.execute(sa.text(f"SELECT * FROM {BACKUP}")).mappings().all()
    by_kind = {k: [r for r in rows if r["kind"] == k] for k in ("permission_removed", "grant_removed", "permission_added", "grant_added")}
    for r in by_kind["permission_removed"]:
        bind.execute(sa.text(
            "INSERT INTO foundation_permissions (id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) "
            "VALUES (:id,:org,:code,:name,:description,:module_name,:resource_name,:action_name,now(),now()) ON CONFLICT (organization_id,code) DO NOTHING"),
            dict(id=uuid4(), org=r["organization_id"], code=r["code"], name=r["name"], description=r["description"],
                 module_name=r["module_name"], resource_name=r["resource_name"], action_name=r["action_name"]))
    for r in by_kind["grant_removed"]:
        bind.execute(sa.text(
            "INSERT INTO foundation_role_permissions (id,role_id,permission_id,scope) "
            "SELECT :id,:role,p.id,:scope FROM foundation_permissions p WHERE p.organization_id=:org AND p.code=:code "
            "ON CONFLICT (role_id,permission_id) DO NOTHING"),
            dict(id=uuid4(), role=r["role_id"], scope=r["scope"], org=r["organization_id"], code=r["code"]))
    for r in by_kind["grant_added"]:
        bind.execute(sa.text(
            "DELETE FROM foundation_role_permissions WHERE role_id=:role AND permission_id IN "
            "(SELECT id FROM foundation_permissions WHERE organization_id=:org AND code=:code)"),
            dict(role=r["role_id"], org=r["organization_id"], code=r["code"]))
    for r in by_kind["permission_added"]:
        params = dict(org=r["organization_id"], code=r["code"])
        bind.execute(sa.text("DELETE FROM foundation_role_permissions WHERE permission_id IN "
                             "(SELECT id FROM foundation_permissions WHERE organization_id=:org AND code=:code)"), params)
        bind.execute(sa.text("DELETE FROM foundation_permissions WHERE organization_id=:org AND code=:code"), params)
    op.drop_table(BACKUP)
