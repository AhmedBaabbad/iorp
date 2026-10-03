"""Quality inspections and rejections aligned with production (QUAL-001).

- Checks: decimal quantities in the line's unit, sample link, start/close/cancel stamps, cancel reason;
  status value "cancelled".
- Rejections: QR- code, production order link, decimal quantity, the disposition becomes a decision
  (nullable until decided; values "decided" status and "use_as_is" disposition), decision/concession/
  execution stamps.
- quality_code_counters (locked numbering) and quality_status_history (every lifecycle step).
- Permissions: quality:<resource>:write is split into its actions (checks: create, update, start, close,
  cancel; rejections: create, update, decide, execute; defects and NCR: create, update). Every holder keeps
  the same access and scope. Removed rows and grants are backed up so the downgrade restores them exactly.
Existing values are kept: current checks and rejections stay as they are (integers become decimals).
"""
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "f6a1b2i6"
down_revision = "f6a1b2i5"
branch_labels = None
depends_on = None

SPLIT = {
    "quality:quality_checks:write": ("create", "update", "start", "close", "cancel"),
    "quality:rejections:write": ("create", "update", "decide", "execute"),
    "quality:quality_defects:write": ("create", "update"),
    "quality:ncr_reports:write": ("create", "update"),
}
BACKUP = "quality_rbac_i6_backup"


def upgrade():
    bind = op.get_bind()
    # PostgreSQL 12+ adds enum values inside a transaction (they are not used in this migration).
    op.execute("ALTER TYPE quality_check_status ADD VALUE IF NOT EXISTS 'cancelled'")
    op.execute("ALTER TYPE quality_disposition ADD VALUE IF NOT EXISTS 'use_as_is'")
    op.execute("ALTER TYPE quality_disposition_status ADD VALUE IF NOT EXISTS 'decided'")

    for column in ("qty_inspected", "qty_accepted", "qty_rejected"):
        op.alter_column("quality_checks", column, type_=sa.Numeric(14, 3), postgresql_using=f"{column}::numeric")
    op.add_column("quality_checks", sa.Column("unit", sa.String(32)))
    op.add_column("quality_checks", sa.Column("sample_id", sa.Uuid()))
    op.create_index("ix_quality_checks_sample_id", "quality_checks", ["sample_id"])
    op.add_column("quality_checks", sa.Column("started_at", sa.DateTime(timezone=True)))
    op.add_column("quality_checks", sa.Column("closed_at", sa.DateTime(timezone=True)))
    op.add_column("quality_checks", sa.Column("closed_by_user_id", sa.Uuid(), sa.ForeignKey("foundation_users.id")))
    op.add_column("quality_checks", sa.Column("cancel_reason", sa.Text()))

    op.add_column("quality_rejections", sa.Column("rejection_code", sa.String(32)))
    op.add_column("quality_rejections", sa.Column("production_order_id", sa.Uuid()))
    op.create_index("ix_quality_rejections_production_order_id", "quality_rejections", ["production_order_id"])
    op.alter_column("quality_rejections", "quantity_rejected", type_=sa.Numeric(14, 3), postgresql_using="quantity_rejected::numeric")
    op.alter_column("quality_rejections", "disposition", nullable=True)
    for name, type_ in (("decided_at", sa.DateTime(timezone=True)), ("decided_by_user_id", sa.Uuid()), ("decision_notes", sa.Text()),
                        ("concession_approved_by", sa.String(255)), ("executed_at", sa.DateTime(timezone=True)),
                        ("executed_by_user_id", sa.Uuid()), ("execution_notes", sa.Text())):
        args = [sa.ForeignKey("foundation_users.id")] if name.endswith("_user_id") else []
        op.add_column("quality_rejections", sa.Column(name, type_, *args))
    # Existing rejections: number them per organization and year, take the order from their check.
    bind.execute(sa.text("""
        UPDATE quality_rejections r SET rejection_code = n.code FROM (
          SELECT id, 'QR-' || extract(year FROM created_at)::int || '-' ||
                 lpad(row_number() OVER (PARTITION BY organization_id, extract(year FROM created_at) ORDER BY created_at, id)::text, 4, '0') AS code
          FROM quality_rejections) n WHERE n.id = r.id"""))
    bind.execute(sa.text("UPDATE quality_rejections r SET production_order_id = c.production_order_id FROM quality_checks c "
                         "WHERE c.id = r.quality_check_id AND r.production_order_id IS NULL"))
    op.alter_column("quality_rejections", "rejection_code", nullable=False)
    op.create_unique_constraint("uq_quality_rejections_org_code", "quality_rejections", ["organization_id", "rejection_code"])

    op.create_table("quality_code_counters",
                    sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("foundation_organizations.id"), primary_key=True),
                    sa.Column("kind", sa.String(8), primary_key=True), sa.Column("year", sa.Integer(), primary_key=True),
                    sa.Column("value", sa.Integer(), nullable=False, server_default="0"))
    # Continue after the codes already issued.
    bind.execute(sa.text("""
        INSERT INTO quality_code_counters (organization_id, kind, year, value)
        SELECT organization_id, 'QI', split_part(inspection_code, '-', 2)::int, max(split_part(inspection_code, '-', 3)::int)
        FROM quality_checks WHERE inspection_code ~ '^QI-[0-9]{4}-[0-9]+$' GROUP BY 1, 3
        UNION ALL
        SELECT organization_id, 'QR', split_part(rejection_code, '-', 2)::int, max(split_part(rejection_code, '-', 3)::int)
        FROM quality_rejections GROUP BY 1, 3"""))
    op.create_table("quality_status_history",
                    sa.Column("id", sa.Uuid(), primary_key=True),
                    sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("foundation_organizations.id"), nullable=False),
                    sa.Column("entity_type", sa.String(20), nullable=False), sa.Column("entity_id", sa.Uuid(), nullable=False),
                    sa.Column("action", sa.String(30), nullable=False), sa.Column("from_status", sa.String(30)),
                    sa.Column("to_status", sa.String(30), nullable=False), sa.Column("reason", sa.Text()), sa.Column("detail", sa.JSON()),
                    sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("foundation_users.id", ondelete="SET NULL")),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_quality_history_entity", "quality_status_history", ["organization_id", "entity_type", "entity_id"])

    _split_permissions(bind)


def _split_permissions(bind):
    op.create_table(BACKUP, sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("kind", sa.String(20), nullable=False),
                    sa.Column("organization_id", sa.Uuid(), nullable=False), sa.Column("role_id", sa.Uuid()),
                    sa.Column("code", sa.String(120), nullable=False), sa.Column("scope", sa.String(20)),
                    sa.Column("name", sa.String(120)), sa.Column("description", sa.Text()))
    backup = sa.table(BACKUP, *(sa.column(c) for c in ("id", "kind", "organization_id", "role_id", "code", "scope", "name", "description")))
    for org in bind.scalars(sa.text("SELECT id FROM foundation_organizations")).all():
        for old, actions in SPLIT.items():
            row = bind.execute(sa.text("SELECT id, name, description FROM foundation_permissions WHERE organization_id=:org AND code=:code"),
                               dict(org=org, code=old)).first()
            resource = old.split(":")[1]
            ids = {}
            for action in actions:
                code = f"quality:{resource}:{action}"
                created = bind.execute(sa.text(
                    "INSERT INTO foundation_permissions (id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) "
                    "VALUES (:id,:org,:code,:name,:description,'quality',:resource,:action,now(),now()) ON CONFLICT (organization_id,code) DO NOTHING RETURNING id"),
                    dict(id=uuid4(), org=org, code=code, name=f"{action.title()} {resource.replace('_', ' ')}",
                         description=f"{action.title()} {resource.replace('_', ' ')}", resource=resource, action=action)).scalar()
                if created:
                    bind.execute(backup.insert().values(id=uuid4(), kind="permission_added", organization_id=org, code=code))
                ids[code] = bind.scalar(sa.text("SELECT id FROM foundation_permissions WHERE organization_id=:org AND code=:code"), dict(org=org, code=code))
            if row is None:
                continue
            for role_id, scope in bind.execute(sa.text("SELECT role_id, scope FROM foundation_role_permissions WHERE permission_id=:p"), dict(p=row.id)).all():
                for code, pid in ids.items():
                    added = bind.execute(sa.text("INSERT INTO foundation_role_permissions (id,role_id,permission_id,scope) VALUES (:id,:role,:p,:scope) "
                                                 "ON CONFLICT (role_id,permission_id) DO NOTHING RETURNING id"), dict(id=uuid4(), role=role_id, p=pid, scope=scope)).scalar()
                    if added:
                        bind.execute(backup.insert().values(id=uuid4(), kind="grant_added", organization_id=org, role_id=role_id, code=code))
                bind.execute(backup.insert().values(id=uuid4(), kind="grant_removed", organization_id=org, role_id=role_id, code=old, scope=scope))
            bind.execute(backup.insert().values(id=uuid4(), kind="permission_removed", organization_id=org, code=old, name=row.name, description=row.description))
            bind.execute(sa.text("DELETE FROM foundation_role_permissions WHERE permission_id=:p"), dict(p=row.id))
            bind.execute(sa.text("DELETE FROM foundation_permissions WHERE id=:p"), dict(p=row.id))
        # The quality manager opens the production order an inspection belongs to.
        for role_id, pid in bind.execute(sa.text(
                "SELECT r.id, p.id FROM foundation_roles r JOIN foundation_permissions p ON p.organization_id = r.organization_id "
                "WHERE r.organization_id=:org AND r.is_system AND r.code='quality_manager' AND p.code='production:production_orders:read'"), dict(org=org)).all():
            added = bind.execute(sa.text("INSERT INTO foundation_role_permissions (id,role_id,permission_id,scope) VALUES (:id,:role,:p,'organization') "
                                         "ON CONFLICT (role_id,permission_id) DO NOTHING RETURNING id"), dict(id=uuid4(), role=role_id, p=pid)).scalar()
            if added:
                bind.execute(backup.insert().values(id=uuid4(), kind="grant_added", organization_id=org, role_id=role_id, code="production:production_orders:read"))


def downgrade():
    bind = op.get_bind()
    newer = bind.scalar(sa.text("SELECT count(*) FROM quality_checks WHERE status::text='cancelled' OR qty_inspected <> trunc(qty_inspected) "
                                "OR qty_accepted <> trunc(qty_accepted) OR qty_rejected <> trunc(qty_rejected)"))
    newer += bind.scalar(sa.text("SELECT count(*) FROM quality_rejections WHERE disposition IS NULL OR disposition::text='use_as_is' "
                                 "OR disposition_status::text='decided' OR quantity_rejected <> trunc(quantity_rejected)"))
    if newer:
        raise RuntimeError("Quality records use the new lifecycle (decimals, cancelled, decided, use as is); export them before downgrading")
    rows = bind.execute(sa.text(f"SELECT * FROM {BACKUP}")).mappings().all()
    for r in [r for r in rows if r["kind"] == "permission_removed"]:
        resource = r["code"].split(":")[1]
        bind.execute(sa.text("INSERT INTO foundation_permissions (id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) "
                             "VALUES (:id,:org,:code,:name,:description,'quality',:resource,'write',now(),now()) ON CONFLICT (organization_id,code) DO NOTHING"),
                     dict(id=uuid4(), org=r["organization_id"], code=r["code"], name=r["name"], description=r["description"], resource=resource))
    for r in [r for r in rows if r["kind"] == "grant_removed"]:
        bind.execute(sa.text("INSERT INTO foundation_role_permissions (id,role_id,permission_id,scope) SELECT :id,:role,p.id,:scope FROM foundation_permissions p "
                             "WHERE p.organization_id=:org AND p.code=:code ON CONFLICT (role_id,permission_id) DO NOTHING"),
                     dict(id=uuid4(), role=r["role_id"], scope=r["scope"], org=r["organization_id"], code=r["code"]))
    for r in [r for r in rows if r["kind"] == "grant_added"]:
        bind.execute(sa.text("DELETE FROM foundation_role_permissions WHERE role_id=:role AND permission_id IN "
                             "(SELECT id FROM foundation_permissions WHERE organization_id=:org AND code=:code)"),
                     dict(role=r["role_id"], org=r["organization_id"], code=r["code"]))
    for r in [r for r in rows if r["kind"] == "permission_added"]:
        params = dict(org=r["organization_id"], code=r["code"])
        bind.execute(sa.text("DELETE FROM foundation_role_permissions WHERE permission_id IN (SELECT id FROM foundation_permissions WHERE organization_id=:org AND code=:code)"), params)
        bind.execute(sa.text("DELETE FROM foundation_permissions WHERE organization_id=:org AND code=:code"), params)
    op.drop_table(BACKUP)

    op.drop_index("ix_quality_history_entity", table_name="quality_status_history")
    op.drop_table("quality_status_history")
    op.drop_table("quality_code_counters")
    op.drop_constraint("uq_quality_rejections_org_code", "quality_rejections", type_="unique")
    for name in ("execution_notes", "executed_by_user_id", "executed_at", "concession_approved_by", "decision_notes", "decided_by_user_id", "decided_at"):
        op.drop_column("quality_rejections", name)
    op.alter_column("quality_rejections", "disposition", nullable=False)
    op.alter_column("quality_rejections", "quantity_rejected", type_=sa.Integer(), postgresql_using="quantity_rejected::integer")
    op.drop_index("ix_quality_rejections_production_order_id", table_name="quality_rejections")
    op.drop_column("quality_rejections", "production_order_id")
    op.drop_column("quality_rejections", "rejection_code")
    for name in ("cancel_reason", "closed_by_user_id", "closed_at", "started_at"):
        op.drop_column("quality_checks", name)
    op.drop_index("ix_quality_checks_sample_id", table_name="quality_checks")
    op.drop_column("quality_checks", "sample_id")
    op.drop_column("quality_checks", "unit")
    for column in ("qty_inspected", "qty_accepted", "qty_rejected"):
        op.alter_column("quality_checks", column, type_=sa.Integer(), postgresql_using=f"{column}::integer")
    # The added enum values stay: PostgreSQL cannot drop them, and nothing uses them after this downgrade.
