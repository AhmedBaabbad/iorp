"""Test parameters, product specifications and inspection measurements (QUAL-SPEC-001).

- quality_test_parameters, quality_specifications (+ lines), quality_check_measurements.
- quality_checks: the specification revision its measurement plan came from.
- Permissions: quality:quality_checks:measure — granted to every role that may update quality checks, with the
  same scope (whoever edits an inspection records its measurements); quality:specifications:{read,create,update,
  activate} — granted to the organization admin, factory manager and quality manager; read also to the viewer.
  Grants added here are recorded so the downgrade removes exactly them.
No existing data changes.
"""
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "f6a1b2i8"
down_revision = "f6a1b2i7"
branch_labels = None
depends_on = None

BACKUP = "quality_spec_i8_added_grants"
NEW = {
    "quality:quality_checks:measure": ("quality_checks", "measure", "Record Inspection Measurements"),
    "quality:specifications:read": ("specifications", "read", "Read Product Specifications"),
    "quality:specifications:create": ("specifications", "create", "Create Product Specifications"),
    "quality:specifications:update": ("specifications", "update", "Update Product Specifications"),
    "quality:specifications:activate": ("specifications", "activate", "Put Product Specifications into Force"),
}
MANAGERS = ("organization_admin", "factory_manager", "quality_manager")


def upgrade():
    bind = op.get_bind()
    uuid, dt, num = sa.Uuid(), sa.DateTime(timezone=True), sa.Numeric(14, 4)
    op.create_table("quality_test_parameters",
                    sa.Column("id", uuid, primary_key=True),
                    sa.Column("organization_id", uuid, sa.ForeignKey("foundation_organizations.id"), nullable=False, index=True),
                    sa.Column("code", sa.String(40), nullable=False), sa.Column("name_ar", sa.String(120), nullable=False),
                    sa.Column("name_en", sa.String(120), nullable=False), sa.Column("kind", sa.String(16), nullable=False),
                    sa.Column("unit", sa.String(16)), sa.Column("method", sa.String(255)),
                    sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
                    sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
                    sa.Column("created_at", dt, nullable=False, server_default=sa.func.now()),
                    sa.Column("updated_at", dt, nullable=False, server_default=sa.func.now()),
                    sa.UniqueConstraint("organization_id", "code", name="uq_quality_test_parameters_org_code"),
                    sa.CheckConstraint("kind IN ('numeric', 'attribute')", name="ck_quality_test_parameters_kind"))
    op.create_table("quality_specifications",
                    sa.Column("id", uuid, primary_key=True),
                    sa.Column("organization_id", uuid, sa.ForeignKey("foundation_organizations.id"), nullable=False, index=True),
                    sa.Column("code", sa.String(40), nullable=False), sa.Column("revision", sa.Integer(), nullable=False),
                    sa.Column("title", sa.String(200), nullable=False), sa.Column("product_type", sa.String(120), nullable=False, index=True),
                    sa.Column("grade", sa.String(80)), sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
                    sa.Column("notes", sa.Text()), sa.Column("activated_at", dt),
                    sa.Column("activated_by_user_id", uuid, sa.ForeignKey("foundation_users.id")),
                    sa.Column("created_by_user_id", uuid, sa.ForeignKey("foundation_users.id"), nullable=False),
                    sa.Column("created_at", dt, nullable=False, server_default=sa.func.now()),
                    sa.Column("updated_at", dt, nullable=False, server_default=sa.func.now()),
                    sa.UniqueConstraint("organization_id", "code", "revision", name="uq_quality_specifications_org_code_rev"),
                    sa.CheckConstraint("status IN ('draft', 'active', 'superseded')", name="ck_quality_specifications_status"))
    # One revision in force per code.
    op.create_index("uq_quality_specifications_active", "quality_specifications", ["organization_id", "code"], unique=True,
                    postgresql_where=sa.text("status = 'active'"))
    op.create_table("quality_specification_lines",
                    sa.Column("id", uuid, primary_key=True),
                    sa.Column("specification_id", uuid, sa.ForeignKey("quality_specifications.id", ondelete="CASCADE"), nullable=False, index=True),
                    sa.Column("parameter_id", uuid, sa.ForeignKey("quality_test_parameters.id"), nullable=False),
                    sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
                    sa.Column("target_source", sa.String(16), nullable=False, server_default="none"), sa.Column("order_spec_key", sa.String(60)),
                    sa.Column("target_value", num), sa.Column("tolerance_minus", num), sa.Column("tolerance_plus", num),
                    sa.Column("min_value", num), sa.Column("max_value", num),
                    sa.Column("requirement", sa.String(255)), sa.Column("acceptance", sa.String(255)), sa.Column("method", sa.String(255)),
                    sa.Column("readings_required", sa.Integer(), nullable=False, server_default="1"),
                    sa.UniqueConstraint("specification_id", "parameter_id", name="uq_quality_spec_lines_parameter"))
    op.create_table("quality_check_measurements",
                    sa.Column("id", uuid, primary_key=True),
                    sa.Column("organization_id", uuid, sa.ForeignKey("foundation_organizations.id"), nullable=False),
                    sa.Column("quality_check_id", uuid, sa.ForeignKey("quality_checks.id", ondelete="CASCADE"), nullable=False, index=True),
                    sa.Column("parameter_id", uuid, sa.ForeignKey("quality_test_parameters.id", ondelete="SET NULL")),
                    sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
                    sa.Column("parameter_code", sa.String(40), nullable=False), sa.Column("name_ar", sa.String(120), nullable=False),
                    sa.Column("name_en", sa.String(120), nullable=False), sa.Column("kind", sa.String(16), nullable=False),
                    sa.Column("unit", sa.String(16)), sa.Column("method", sa.String(255)), sa.Column("requirement", sa.String(255)),
                    sa.Column("acceptance", sa.String(255)), sa.Column("target", num), sa.Column("lower_limit", num), sa.Column("upper_limit", num),
                    sa.Column("readings_required", sa.Integer(), nullable=False, server_default="1"), sa.Column("readings", sa.JSON()),
                    sa.Column("attribute_result", sa.String(16)), sa.Column("observation", sa.String(255)),
                    sa.Column("reading_count", sa.Integer(), nullable=False, server_default="0"),
                    sa.Column("minimum", num), sa.Column("maximum", num), sa.Column("mean", num),
                    sa.Column("status", sa.String(12), nullable=False, server_default="pending"),
                    sa.Column("measured_at", dt), sa.Column("measured_by_user_id", uuid, sa.ForeignKey("foundation_users.id")))
    op.add_column("quality_checks", sa.Column("specification_id", uuid, sa.ForeignKey("quality_specifications.id")))
    op.add_column("quality_checks", sa.Column("specification_code", sa.String(40)))
    op.add_column("quality_checks", sa.Column("specification_revision", sa.Integer()))

    op.create_table(BACKUP, sa.Column("id", uuid, primary_key=True), sa.Column("role_id", uuid, nullable=False),
                    sa.Column("permission_id", uuid, nullable=False))
    backup = sa.table(BACKUP, sa.column("id"), sa.column("role_id"), sa.column("permission_id"))

    def grant(role_id, permission_id, scope="organization"):
        added = bind.scalar(sa.text("INSERT INTO foundation_role_permissions (id,role_id,permission_id,scope) VALUES (:id,:role,:p,:scope) "
                                    "ON CONFLICT (role_id,permission_id) DO NOTHING RETURNING id"),
                            dict(id=uuid4(), role=role_id, p=permission_id, scope=scope))
        if added:
            bind.execute(backup.insert().values(id=added, role_id=role_id, permission_id=permission_id))

    for org in bind.scalars(sa.text("SELECT id FROM foundation_organizations")).all():
        ids = {}
        for code, (resource, action, name) in NEW.items():
            bind.execute(sa.text("INSERT INTO foundation_permissions (id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) "
                                 "VALUES (:id,:org,:code,:name,:description,'quality',:resource,:action,now(),now()) ON CONFLICT (organization_id,code) DO NOTHING"),
                         dict(id=uuid4(), org=org, code=code, name=name, description=name, resource=resource, action=action))
            ids[code] = bind.scalar(sa.text("SELECT id FROM foundation_permissions WHERE organization_id=:org AND code=:code"), dict(org=org, code=code))
        # Whoever may update an inspection records its measurements, with the same scope.
        for role_id, scope in bind.execute(sa.text(
                "SELECT rp.role_id, rp.scope FROM foundation_role_permissions rp JOIN foundation_permissions p ON p.id = rp.permission_id "
                "WHERE p.organization_id=:org AND p.code='quality:quality_checks:update'"), dict(org=org)).all():
            grant(role_id, ids["quality:quality_checks:measure"], scope)
        roles = dict(bind.execute(sa.text("SELECT code, id FROM foundation_roles WHERE organization_id=:org AND is_system"), dict(org=org)).all())
        for role in MANAGERS:
            if role in roles:
                for code in NEW:
                    grant(roles[role], ids[code])
        if "viewer" in roles:
            grant(roles["viewer"], ids["quality:specifications:read"])


def downgrade():
    bind = op.get_bind()
    bind.execute(sa.text(f"DELETE FROM foundation_role_permissions WHERE id IN (SELECT id FROM {BACKUP})"))
    op.drop_table(BACKUP)
    bind.execute(sa.text("DELETE FROM foundation_role_permissions WHERE permission_id IN (SELECT id FROM foundation_permissions WHERE code IN :codes)")
                 .bindparams(sa.bindparam("codes", expanding=True)), dict(codes=list(NEW)))
    bind.execute(sa.text("DELETE FROM foundation_permissions WHERE code IN :codes").bindparams(sa.bindparam("codes", expanding=True)), dict(codes=list(NEW)))
    for column in ("specification_revision", "specification_code", "specification_id"):
        op.drop_column("quality_checks", column)
    op.drop_table("quality_check_measurements")
    op.drop_table("quality_specification_lines")
    op.drop_index("uq_quality_specifications_active", table_name="quality_specifications")
    op.drop_table("quality_specifications")
    op.drop_table("quality_test_parameters")
