"""RBAC-003: the system roles, one per module with executing roles under their managers.

For every organization: each system role's permissions become exactly its list below (missing ones added, extra ones
removed, the sales representative's reads at scope "own"); the production supervisor and quality inspector roles are
added; the warehouse, maintenance, safety, finance and human resources roles are retired. A retired role still assigned
to someone becomes the organization's own (custom) role with its permissions, so nobody loses their work. The
administrator's role and the organization's own roles are never touched. Every change is recorded for the downgrade.
"""
from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "f6a1b2k9"
down_revision = "f6a1b2k8"
branch_labels = None
depends_on = None

# role -> its permissions (generated from app/foundation/domain/system_roles.py when written; fixed here on purpose)
ROLES = {
    "commercial_manager": dict(name_ar="المدير التجاري", name_en="Commercial Manager",
        description_ar="يدير الموديل التجاري كاملاً: العملاء والعينات وعروض الأسعار وأوامر البيع والمتابعات", description_en="Runs the commercial module: customers, samples, quotations, sales orders and follow-ups",
        own=[],
        permissions=[
            'commercial:customers:assign_owner', 'commercial:customers:create', 'commercial:customers:delete',
            'commercial:customers:read', 'commercial:customers:update', 'commercial:evaluations:create',
            'commercial:evaluations:delete', 'commercial:evaluations:read', 'commercial:evaluations:update',
            'commercial:follow_ups:assign', 'commercial:follow_ups:cancel', 'commercial:follow_ups:complete',
            'commercial:follow_ups:create', 'commercial:follow_ups:delete', 'commercial:follow_ups:read',
            'commercial:follow_ups:reopen', 'commercial:follow_ups:update', 'commercial:interactions:create',
            'commercial:interactions:delete', 'commercial:interactions:read', 'commercial:interactions:update',
            'commercial:orders:cancel', 'commercial:orders:confirm', 'commercial:orders:create',
            'commercial:orders:delete', 'commercial:orders:read', 'commercial:orders:revise',
            'commercial:orders:update', 'commercial:quote_settings:read', 'commercial:quote_settings:update',
            'commercial:quotes:accept', 'commercial:quotes:create', 'commercial:quotes:delete',
            'commercial:quotes:expire', 'commercial:quotes:issue', 'commercial:quotes:read',
            'commercial:quotes:reject', 'commercial:quotes:revise', 'commercial:quotes:update',
            'commercial:samples:cancel', 'commercial:samples:create', 'commercial:samples:decide',
            'commercial:samples:delete', 'commercial:samples:deliver', 'commercial:samples:read',
            'commercial:samples:reopen', 'commercial:samples:start', 'commercial:samples:update',
            'masterdata:lists:map_legacy', 'masterdata:lists:read', 'masterdata:lists:update',
            'masterdata:products:create', 'masterdata:products:map_legacy', 'masterdata:products:read',
            'masterdata:products:update', 'masterdata:settings:read', 'production:demands:read',
            'reports:customers:activity_summary', 'reports:customers:customer_profile', 'reports:customers:customer_statement',
            'reports:customers:demand_fulfillment', 'reports:customers:directory', 'reports:customers:growth_retention',
            'reports:customers:internal_audience', 'reports:customers:quotations_report', 'shipping:returns:approve',
            'shipping:returns:cancel', 'shipping:returns:create', 'shipping:returns:read',
            'shipping:returns:reject', 'shipping:shipments:read',
        ]),
    "sales_rep": dict(name_ar="مندوب مبيعات", name_en="Sales Representative",
        description_ar="يعمل على عملائه فقط: عروض الأسعار والعينات وأوامر البيع المسودة والمتابعات", description_en="Works their own customers: quotations, samples, draft sales orders and follow-ups",
        own=['commercial:customers:read', 'commercial:follow_ups:read', 'commercial:interactions:read', 'commercial:orders:read', 'commercial:quotes:read', 'commercial:samples:read'],
        permissions=[
            'commercial:customers:read', 'commercial:customers:update', 'commercial:evaluations:create',
            'commercial:evaluations:read', 'commercial:follow_ups:complete', 'commercial:follow_ups:create',
            'commercial:follow_ups:read', 'commercial:follow_ups:update', 'commercial:interactions:create',
            'commercial:interactions:read', 'commercial:interactions:update', 'commercial:orders:create',
            'commercial:orders:read', 'commercial:orders:update', 'commercial:quotes:accept',
            'commercial:quotes:create', 'commercial:quotes:expire', 'commercial:quotes:issue',
            'commercial:quotes:read', 'commercial:quotes:reject', 'commercial:quotes:revise',
            'commercial:quotes:update', 'commercial:samples:cancel', 'commercial:samples:create',
            'commercial:samples:decide', 'commercial:samples:deliver', 'commercial:samples:read',
            'commercial:samples:reopen', 'commercial:samples:start', 'commercial:samples:update',
            'masterdata:lists:read', 'masterdata:products:read', 'masterdata:settings:read',
            'reports:customers:activity_summary', 'reports:customers:customer_profile', 'reports:customers:customer_statement',
            'reports:customers:directory', 'shipping:returns:create', 'shipping:returns:read',
            'shipping:shipments:read',
        ]),
    "production_manager": dict(name_ar="مدير الإنتاج", name_en="Production Manager",
        description_ar="يدير موديل الإنتاج كاملاً مع فرق العمل وتقارير الإنتاج", description_en="Runs the production module, its crews and reports",
        own=[],
        permissions=[
            'commercial:orders:read', 'masterdata:lists:read', 'masterdata:products:create',
            'masterdata:products:map_legacy', 'masterdata:products:read', 'masterdata:products:update',
            'masterdata:settings:read', 'production:demands:cancel', 'production:demands:create',
            'production:demands:delete', 'production:demands:read', 'production:demands:release',
            'production:demands:update', 'production:downtime_events:close', 'production:downtime_events:create',
            'production:downtime_events:delete', 'production:downtime_events:read', 'production:downtime_events:update',
            'production:planning:allocate', 'production:planning:read', 'production:planning:release_allocation',
            'production:planning:sequence', 'production:production_orders:cancel', 'production:production_orders:close',
            'production:production_orders:complete', 'production:production_orders:create', 'production:production_orders:hold',
            'production:production_orders:manage_items', 'production:production_orders:read', 'production:production_orders:release',
            'production:production_orders:start', 'production:production_orders:update', 'production:results:correct',
            'production:results:create', 'production:results:delete', 'production:results:read',
            'production:results:update', 'production:runs:cancel', 'production:runs:complete',
            'production:runs:create', 'production:runs:manage_members', 'production:runs:pause',
            'production:runs:read', 'production:runs:start', 'production:runs:update',
            'production:shift_rosters:close', 'production:shift_rosters:create', 'production:shift_rosters:manage_members',
            'production:shift_rosters:read', 'production:shift_rosters:update', 'production:shifts:create',
            'production:shifts:delete', 'production:shifts:read', 'production:shifts:update',
            'production:waste_records:create', 'production:waste_records:delete', 'production:waste_records:read',
            'production:waste_records:update', 'production:work_centers:create', 'production:work_centers:delete',
            'production:work_centers:read', 'production:work_centers:update', 'quality:ncr_actions:complete',
            'quality:ncr_actions:read', 'quality:ncr_reports:read', 'reports:production:order_full',
            'reports:production:orders_summary', 'reports:production:results_analysis', 'reports:production:shift_workforce',
            'workforce:members:create', 'workforce:members:delete', 'workforce:members:link_user',
            'workforce:members:read', 'workforce:members:update',
        ]),
    "production_supervisor": dict(name_ar="مشرف إنتاج", name_en="Production Supervisor",
        description_ar="يسجّل عمل الوردية: التشغيل والنتائج والتوقف والهالك", description_en="Records the shift: runs, results, downtime and scrap",
        own=[],
        permissions=[
            'masterdata:lists:read', 'masterdata:products:read', 'masterdata:settings:read',
            'production:demands:read', 'production:downtime_events:close', 'production:downtime_events:create',
            'production:downtime_events:read', 'production:downtime_events:update', 'production:production_orders:read',
            'production:results:create', 'production:results:read', 'production:results:update',
            'production:runs:complete', 'production:runs:create', 'production:runs:manage_members',
            'production:runs:pause', 'production:runs:read', 'production:runs:start',
            'production:runs:update', 'production:shift_rosters:manage_members', 'production:shift_rosters:read',
            'production:shifts:read', 'production:waste_records:create', 'production:waste_records:read',
            'production:waste_records:update', 'production:work_centers:read', 'quality:ncr_actions:complete',
            'quality:ncr_actions:read', 'quality:ncr_reports:create', 'quality:ncr_reports:read',
            'reports:production:order_full', 'workforce:members:read',
        ]),
    "quality_manager": dict(name_ar="مدير الجودة", name_en="Quality Manager",
        description_ar="يدير موديل الجودة كاملاً مع قراراته وتقاريره", description_en="Runs the quality module, its decisions and reports",
        own=[],
        permissions=[
            'masterdata:lists:read', 'masterdata:products:create', 'masterdata:products:map_legacy',
            'masterdata:products:read', 'masterdata:products:update', 'masterdata:settings:read',
            'procurement:materials:read', 'procurement:materials:update', 'procurement:purchase_orders:read',
            'procurement:receipts:read', 'procurement:suppliers:approve', 'procurement:suppliers:read',
            'production:production_orders:read', 'quality:certificates:create', 'quality:certificates:issue',
            'quality:certificates:read', 'quality:certificates:revoke', 'quality:certificates:update',
            'quality:ncr_actions:complete', 'quality:ncr_actions:read', 'quality:ncr_reports:cancel',
            'quality:ncr_reports:contain', 'quality:ncr_reports:create', 'quality:ncr_reports:investigate',
            'quality:ncr_reports:read', 'quality:ncr_reports:submit', 'quality:ncr_reports:update',
            'quality:ncr_reports:verify', 'quality:quality_checks:cancel', 'quality:quality_checks:close',
            'quality:quality_checks:create', 'quality:quality_checks:measure', 'quality:quality_checks:read',
            'quality:quality_checks:start', 'quality:quality_checks:update', 'quality:quality_defects:create',
            'quality:quality_defects:read', 'quality:quality_defects:update', 'quality:rejections:create',
            'quality:rejections:decide', 'quality:rejections:execute', 'quality:rejections:read',
            'quality:rejections:update', 'quality:settings:update', 'quality:specifications:activate',
            'quality:specifications:create', 'quality:specifications:read', 'quality:specifications:update',
            'reports:quality:check_full', 'reports:quality:checks_summary', 'reports:quality:corrective_actions',
            'reports:quality:defects_analysis', 'reports:quality:rejections_analysis', 'shipping:returns:read',
            'shipping:shipments:read',
        ]),
    "quality_inspector": dict(name_ar="مفتش جودة", name_en="Quality Inspector",
        description_ar="ينفّذ الفحوصات: القياسات والعيوب وتسجيل المرفوض", description_en="Carries out inspections: checks, measurements, defects",
        own=[],
        permissions=[
            'masterdata:lists:read', 'masterdata:products:read', 'masterdata:settings:read',
            'procurement:materials:read', 'procurement:receipts:read', 'production:production_orders:read',
            'quality:certificates:read', 'quality:ncr_actions:complete', 'quality:ncr_actions:read',
            'quality:ncr_reports:create', 'quality:ncr_reports:read', 'quality:quality_checks:close',
            'quality:quality_checks:create', 'quality:quality_checks:measure', 'quality:quality_checks:read',
            'quality:quality_checks:start', 'quality:quality_checks:update', 'quality:quality_defects:create',
            'quality:quality_defects:read', 'quality:quality_defects:update', 'quality:rejections:create',
            'quality:rejections:read', 'quality:specifications:read', 'reports:quality:check_full',
            'shipping:returns:read',
        ]),
    "procurement_manager": dict(name_ar="مدير المشتريات", name_en="Procurement Manager",
        description_ar="يدير المشتريات: الموردين والمواد وأوامر الشراء واستلام المواد", description_en="Runs procurement: suppliers, materials, purchase orders and goods receipts",
        own=[],
        permissions=[
            'commercial:orders:read', 'masterdata:lists:map_legacy', 'masterdata:lists:read',
            'masterdata:lists:update', 'masterdata:products:read', 'masterdata:settings:read',
            'procurement:materials:create', 'procurement:materials:read', 'procurement:materials:update',
            'procurement:purchase_orders:approve', 'procurement:purchase_orders:cancel', 'procurement:purchase_orders:close',
            'procurement:purchase_orders:create', 'procurement:purchase_orders:read', 'procurement:purchase_orders:send',
            'procurement:purchase_orders:update', 'procurement:receipts:cancel', 'procurement:receipts:create',
            'procurement:receipts:read', 'procurement:receipts:receive', 'procurement:receipts:update',
            'procurement:settings:update', 'procurement:suppliers:approve', 'procurement:suppliers:create',
            'procurement:suppliers:read', 'procurement:suppliers:update', 'production:production_orders:read',
            'quality:ncr_actions:complete', 'quality:ncr_actions:read', 'quality:ncr_reports:read',
            'reports:production:orders_summary',
        ]),
    "shipping_manager": dict(name_ar="مدير الشحن", name_en="Shipping Manager",
        description_ar="يدير الشحن: التجهيز والإخراج والتسليم والمرتجعات", description_en="Runs shipping: preparing, dispatching, delivering and returns",
        own=[],
        permissions=[
            'commercial:customers:read', 'commercial:orders:read', 'masterdata:lists:map_legacy',
            'masterdata:lists:read', 'masterdata:lists:update', 'masterdata:products:read',
            'masterdata:settings:read', 'production:production_orders:read', 'quality:ncr_actions:complete',
            'quality:ncr_actions:read', 'quality:ncr_reports:create', 'quality:ncr_reports:read',
            'reports:production:order_full', 'reports:production:orders_summary', 'shipping:returns:approve',
            'shipping:returns:cancel', 'shipping:returns:create', 'shipping:returns:read',
            'shipping:returns:receive', 'shipping:returns:reject', 'shipping:settings:update',
            'shipping:shipments:cancel', 'shipping:shipments:close', 'shipping:shipments:create',
            'shipping:shipments:deliver', 'shipping:shipments:dispatch', 'shipping:shipments:fail',
            'shipping:shipments:read', 'shipping:shipments:ready', 'shipping:shipments:reopen',
            'shipping:shipments:reschedule', 'shipping:shipments:update',
        ]),
    "factory_manager": dict(name_ar="مدير المصنع", name_en="Factory Manager",
        description_ar="يشرف على المصنع ويتخذ القرارات الكبرى", description_en="Oversees the factory and takes its major decisions",
        own=[],
        permissions=[
            'commercial:customers:read', 'commercial:orders:read', 'commercial:quotes:read',
            'masterdata:lists:read', 'masterdata:products:read', 'masterdata:settings:read',
            'procurement:materials:read', 'procurement:purchase_orders:approve', 'procurement:purchase_orders:read',
            'procurement:receipts:read', 'procurement:suppliers:approve', 'procurement:suppliers:read',
            'production:demands:cancel', 'production:demands:read', 'production:demands:release',
            'production:downtime_events:read', 'production:planning:read', 'production:production_orders:cancel',
            'production:production_orders:close', 'production:production_orders:hold', 'production:production_orders:read',
            'production:production_orders:release', 'production:results:correct', 'production:results:read',
            'production:runs:read', 'production:shift_rosters:read', 'production:shifts:read',
            'production:waste_records:read', 'production:work_centers:read', 'quality:certificates:issue',
            'quality:certificates:read', 'quality:certificates:revoke', 'quality:ncr_actions:read',
            'quality:ncr_reports:cancel', 'quality:ncr_reports:read', 'quality:ncr_reports:verify',
            'quality:quality_checks:read', 'quality:quality_defects:read', 'quality:rejections:decide',
            'quality:rejections:read', 'quality:specifications:activate', 'quality:specifications:read',
            'reports:production:order_full', 'reports:production:orders_summary', 'reports:production:results_analysis',
            'reports:production:shift_workforce', 'reports:quality:check_full', 'reports:quality:checks_summary',
            'reports:quality:corrective_actions', 'reports:quality:defects_analysis', 'reports:quality:rejections_analysis',
            'shipping:returns:approve', 'shipping:returns:read', 'shipping:returns:reject',
            'shipping:shipments:read', 'workforce:members:read',
        ]),
    "viewer": dict(name_ar="مستخدم للعرض", name_en="Viewer",
        description_ar="يعرض بيانات العمل وتقاريرها فقط", description_en="Reads the business modules and their reports",
        own=[],
        permissions=[
            'commercial:customers:read', 'commercial:evaluations:read', 'commercial:follow_ups:read',
            'commercial:interactions:read', 'commercial:orders:read', 'commercial:quote_settings:read',
            'commercial:quotes:read', 'commercial:samples:read', 'masterdata:lists:read',
            'masterdata:products:read', 'masterdata:settings:read', 'organization:branding:read',
            'procurement:materials:read', 'procurement:purchase_orders:read', 'procurement:receipts:read',
            'procurement:suppliers:read', 'production:demands:read', 'production:downtime_events:read',
            'production:planning:read', 'production:production_orders:read', 'production:results:read',
            'production:runs:read', 'production:shift_rosters:read', 'production:shifts:read',
            'production:waste_records:read', 'production:work_centers:read', 'quality:certificates:read',
            'quality:ncr_actions:read', 'quality:ncr_reports:read', 'quality:quality_checks:read',
            'quality:quality_defects:read', 'quality:rejections:read', 'quality:specifications:read',
            'reports:production:order_full', 'reports:production:orders_summary', 'reports:production:results_analysis',
            'reports:production:shift_workforce', 'reports:quality:check_full', 'reports:quality:checks_summary',
            'reports:quality:corrective_actions', 'reports:quality:defects_analysis', 'reports:quality:rejections_analysis',
            'shipping:returns:read', 'shipping:shipments:read', 'workforce:members:read',
        ]),
}


RETIRED = ("warehouse_manager", "maintenance_manager", "safety_manager", "finance_manager", "hr_manager")
ADDED, REMOVED, SCOPES, ROLES_TABLE, RETIRED_TABLE = ("rbac_k9_added_grants", "rbac_k9_removed_grants", "rbac_k9_changed_scopes",
                                                      "rbac_k9_roles", "rbac_k9_retired_roles")


def _tables(bind, *names):
    meta = sa.MetaData()
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
    op.create_table(REMOVED, sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("role_id", sa.Uuid()),
                    sa.Column("permission_id", sa.Uuid()), sa.Column("scope", sa.String(20)))
    op.create_table(SCOPES, sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("scope", sa.String(20)))
    # roles created (new) or changed (name, description, system flag), with what they were
    op.create_table(ROLES_TABLE, sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("created", sa.Boolean()),
                    sa.Column("name", sa.String(120)), sa.Column("description", sa.Text()))
    op.create_table(RETIRED_TABLE, sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("organization_id", sa.Uuid()),
                    sa.Column("name", sa.String(120)), sa.Column("code", sa.String(64)), sa.Column("description", sa.Text()),
                    sa.Column("deleted", sa.Boolean()))
    orgs, permissions, roles, grants, user_roles, added, removed, scopes, role_log, retired_log = _tables(
        bind, "foundation_organizations", "foundation_permissions", "foundation_roles", "foundation_role_permissions",
        "foundation_user_roles", ADDED, REMOVED, SCOPES, ROLES_TABLE, RETIRED_TABLE)
    now = datetime.now(timezone.utc)

    def permission_id(org, code):
        pid = bind.scalar(sa.select(permissions.c.id).where(permissions.c.organization_id == org, permissions.c.code == code))
        if pid is None:
            pid = uuid4()
            module, resource, action = code.split(":")
            bind.execute(permissions.insert().values(id=pid, organization_id=org, code=code, name=code, description=code, module_name=module,
                                                     resource_name=resource, action_name=action, created_at=now, updated_at=now))
        return pid

    for org, locale in bind.execute(sa.select(orgs.c.id, orgs.c.default_locale)).all():
        lang = "en" if locale == "en" else "ar"
        for code, spec in ROLES.items():
            row = bind.execute(sa.select(roles).where(roles.c.organization_id == org, roles.c.code == code)).mappings().first()
            name, description = spec[f"name_{lang}"], spec[f"description_{lang}"]
            if row is None:
                rid = uuid4()
                bind.execute(roles.insert().values(id=rid, organization_id=org, code=code, name=name, description=description, is_system=True,
                                                   is_protected=False, is_editable=False, created_at=now, updated_at=now))
                bind.execute(role_log.insert().values(id=rid, created=True))
            else:
                rid = row["id"]
                if not row["is_system"]:
                    continue  # an organization's own role that happens to use this code: never touched
                bind.execute(role_log.insert().values(id=rid, created=False, name=row["name"], description=row["description"]))
                bind.execute(roles.update().where(roles.c.id == rid).values(name=name, description=description, updated_at=now))
            wanted = {permission_id(org, c): ("own" if c in spec["own"] else "organization") for c in spec["permissions"]}
            current = {g["permission_id"]: g for g in bind.execute(sa.select(grants).where(grants.c.role_id == rid)).mappings()}
            for pid, scope in wanted.items():
                if pid not in current:
                    gid = uuid4()
                    bind.execute(grants.insert().values(id=gid, role_id=rid, permission_id=pid, scope=scope))
                    bind.execute(added.insert().values(id=gid))
                elif current[pid]["scope"] != scope:
                    bind.execute(scopes.insert().values(id=current[pid]["id"], scope=current[pid]["scope"]))
                    bind.execute(grants.update().where(grants.c.id == current[pid]["id"]).values(scope=scope))
            for pid, g in current.items():
                if pid not in wanted:
                    bind.execute(removed.insert().values(id=g["id"], role_id=g["role_id"], permission_id=g["permission_id"], scope=g["scope"]))
                    bind.execute(grants.delete().where(grants.c.id == g["id"]))
        for row in bind.execute(sa.select(roles).where(roles.c.organization_id == org, roles.c.code.in_(RETIRED),
                                                       roles.c.is_system.is_(True))).mappings().all():
            in_use = bind.scalar(sa.select(user_roles.c.id).where(user_roles.c.role_id == row["id"]).limit(1)) is not None
            bind.execute(retired_log.insert().values(id=row["id"], organization_id=org, name=row["name"], code=row["code"],
                                                     description=row["description"], deleted=not in_use))
            if in_use:
                # still someone's role: it becomes the organization's own role, with the same permissions
                bind.execute(roles.update().where(roles.c.id == row["id"]).values(is_system=False, is_editable=True, is_protected=False, updated_at=now))
            else:
                for g in bind.execute(sa.select(grants).where(grants.c.role_id == row["id"])).mappings().all():
                    bind.execute(removed.insert().values(id=g["id"], role_id=g["role_id"], permission_id=g["permission_id"], scope=g["scope"]))
                bind.execute(grants.delete().where(grants.c.role_id == row["id"]))
                bind.execute(roles.delete().where(roles.c.id == row["id"]))


def downgrade():
    bind = op.get_bind()
    roles, grants, added, removed, scopes, role_log, retired_log = _tables(
        bind, "foundation_roles", "foundation_role_permissions", ADDED, REMOVED, SCOPES, ROLES_TABLE, RETIRED_TABLE)
    now = datetime.now(timezone.utc)
    for row in bind.execute(sa.select(retired_log)).mappings().all():
        if row["deleted"]:
            bind.execute(roles.insert().values(id=row["id"], organization_id=row["organization_id"], code=row["code"], name=row["name"],
                                               description=row["description"], is_system=True, is_protected=False, is_editable=False,
                                               created_at=now, updated_at=now))
        else:
            bind.execute(roles.update().where(roles.c.id == row["id"]).values(is_system=True, is_editable=False))
    bind.execute(grants.delete().where(grants.c.id.in_(sa.select(added.c.id))))
    for row in bind.execute(sa.select(removed)).mappings().all():
        bind.execute(grants.insert().values(**dict(row)))
    for row in bind.execute(sa.select(scopes)).mappings().all():
        bind.execute(grants.update().where(grants.c.id == row["id"]).values(scope=row["scope"]))
    for row in bind.execute(sa.select(role_log)).mappings().all():
        if row["created"]:
            bind.execute(grants.delete().where(grants.c.role_id == row["id"]))
            bind.execute(roles.delete().where(roles.c.id == row["id"]))
        else:
            bind.execute(roles.update().where(roles.c.id == row["id"]).values(name=row["name"], description=row["description"]))
    for table in (RETIRED_TABLE, ROLES_TABLE, SCOPES, REMOVED, ADDED):
        op.drop_table(table)
