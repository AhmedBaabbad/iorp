"""Independent shifts, preserved legacy links, roster history and run teams.

Revision ID: f6a1b2g6
Revises: f6a1b2g5
"""
from uuid import uuid4
from alembic import op
import sqlalchemy as sa

revision = "f6a1b2g6"
down_revision = "f6a1b2g5"
branch_labels = None
depends_on = None


def common():
    return [sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("foundation_organizations.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())]


def ref(name, target, nullable=False):
    return sa.Column(name, sa.Uuid(), sa.ForeignKey(target + ".id", ondelete="RESTRICT"), nullable=nullable)


def upgrade():
    bind = op.get_bind()
    # A historical association, not a live FK: retain even if a center is retired.
    op.create_table("production_legacy_shift_centers",
        sa.Column("shift_definition_id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("work_center_id", sa.Uuid(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    bind.execute(sa.text("INSERT INTO production_legacy_shift_centers (shift_definition_id, organization_id, work_center_id) SELECT id, organization_id, work_center_id FROM production_shift_definitions"))
    for fk in sa.inspect(bind).get_foreign_keys("production_shift_definitions"):
        if "work_center_id" in fk["constrained_columns"]:
            op.drop_constraint(fk["name"], "production_shift_definitions", type_="foreignkey")
    op.drop_index("ix_production_shift_definitions_work_center_id", table_name="production_shift_definitions")
    op.drop_column("production_shift_definitions", "work_center_id")
    op.create_table("production_shift_rosters", *common(),
        ref("shift_definition_id", "production_shift_definitions"),
        sa.Column("name", sa.String(255)), sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()), sa.Column("status", sa.String(20), nullable=False), sa.Column("notes", sa.Text()),
        sa.CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="ck_roster_period"),
        sa.CheckConstraint("status IN ('active','closed')", name="ck_roster_status"))
    op.create_table("production_shift_roster_members", *common(),
        ref("shift_roster_id", "production_shift_rosters"), ref("workforce_member_id", "workforce_members"),
        sa.Column("is_shift_lead", sa.Boolean(), nullable=False), sa.Column("role_note", sa.String(255)),
        sa.UniqueConstraint("organization_id", "shift_roster_id", "workforce_member_id", name="uq_roster_worker"))
    op.create_table("production_runs", *common(),
        ref("production_order_id", "production_orders"), ref("work_center_id", "production_work_centers"),
        ref("shift_definition_id", "production_shift_definitions", True), ref("shift_roster_id", "production_shift_rosters", True),
        sa.Column("run_date", sa.Date(), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("planned_quantity", sa.Numeric(15, 3)), sa.Column("notes", sa.Text()),
        ref("created_by_user_id", "foundation_users"),
        sa.CheckConstraint("ended_at IS NULL OR (started_at IS NOT NULL AND ended_at >= started_at)", name="ck_run_window"),
        sa.CheckConstraint("planned_quantity IS NULL OR planned_quantity > 0", name="ck_run_quantity"),
        sa.CheckConstraint("status IN ('planned','in_progress','paused','completed','cancelled')", name="ck_run_status"))
    op.create_table("production_run_members", *common(),
        ref("production_run_id", "production_runs"), ref("workforce_member_id", "workforce_members"),
        sa.Column("role_code", sa.String(64), nullable=False), sa.Column("is_lead", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("ended_at", sa.DateTime(timezone=True)), sa.Column("notes", sa.Text()),
        sa.UniqueConstraint("organization_id", "production_run_id", "workforce_member_id", name="uq_run_worker"),
        sa.CheckConstraint("ended_at IS NULL OR (started_at IS NOT NULL AND ended_at >= started_at)", name="ck_run_member_window"))
    for table, fields in {
        "production_shift_rosters": ("organization_id", "shift_definition_id", "effective_from"),
        "production_shift_roster_members": ("organization_id", "shift_roster_id", "workforce_member_id"),
        "production_runs": ("organization_id", "production_order_id", "work_center_id", "shift_definition_id", "shift_roster_id", "run_date"),
        "production_run_members": ("organization_id", "production_run_id", "workforce_member_id"),
    }.items():
        for field in fields:
            op.create_index(f"ix_{table}_{field}", table, [field])
    # Preserve existing shift access by mapping grants, never by role name.
    for org in bind.scalars(sa.text("SELECT id FROM foundation_organizations")):
        for resource, actions in {"shifts": ("read", "create", "update"), "shift_rosters": ("read", "create", "update", "manage_members"), "runs": ("read", "create", "update", "start", "complete", "manage_members")}.items():
            for action in actions:
                permission_id = uuid4()
                bind.execute(sa.text("INSERT INTO foundation_permissions (id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) VALUES (:id,:org,:code,CAST(:name AS text),CAST(:name AS text),'production',:resource,:action,now(),now()) ON CONFLICT (organization_id,code) DO NOTHING"), dict(id=permission_id, org=org, code=f"production:{resource}:{action}", name=f"{action} {resource}", resource=resource, action=action))
                if resource == "shifts":
                    old_code = "production:shift_definitions:" + ("read" if action == "read" else "write")
                    new_id = bind.scalar(sa.text("SELECT id FROM foundation_permissions WHERE organization_id=:org AND code=:code"), dict(org=org, code=f"production:shifts:{action}"))
                    roles = bind.execute(sa.text("SELECT rp.role_id, rp.scope FROM foundation_role_permissions rp JOIN foundation_permissions p ON p.id=rp.permission_id WHERE p.organization_id=:org AND p.code=:code"), dict(org=org, code=old_code)).all()
                    for role, scope in roles:
                        bind.execute(sa.text("INSERT INTO foundation_role_permissions (id,role_id,permission_id,scope) VALUES (:id,:role,:permission,:scope) ON CONFLICT (role_id,permission_id) DO NOTHING"), dict(id=uuid4(), role=role, permission=new_id, scope=scope))


def downgrade():
    bind = op.get_bind()
    for table in ("production_run_members", "production_runs", "production_shift_roster_members", "production_shift_rosters"):
        if bind.scalar(sa.text(f"SELECT count(*) FROM {table}")):
            raise RuntimeError("Archive execution history before downgrading")
    if bind.scalar(sa.text("SELECT count(*) FROM production_shift_definitions s LEFT JOIN production_legacy_shift_centers a ON a.shift_definition_id=s.id LEFT JOIN production_work_centers w ON w.id=a.work_center_id WHERE w.id IS NULL")):
        raise RuntimeError("Independent shifts have no valid legacy center; downgrade requires an explicit mapping")
    for table in ("production_run_members", "production_runs", "production_shift_roster_members", "production_shift_rosters"):
        op.drop_table(table)
    op.add_column("production_shift_definitions", sa.Column("work_center_id", sa.Uuid()))
    bind.execute(sa.text("UPDATE production_shift_definitions s SET work_center_id=a.work_center_id FROM production_legacy_shift_centers a WHERE s.id=a.shift_definition_id"))
    op.alter_column("production_shift_definitions", "work_center_id", nullable=False)
    op.create_foreign_key("production_shift_definitions_work_center_id_fkey", "production_shift_definitions", "production_work_centers", ["work_center_id"], ["id"])
    op.create_index("ix_production_shift_definitions_work_center_id", "production_shift_definitions", ["work_center_id"])
    op.drop_table("production_legacy_shift_centers")
    # Permission grants are retained on downgrade to avoid destroying administrator choices.
