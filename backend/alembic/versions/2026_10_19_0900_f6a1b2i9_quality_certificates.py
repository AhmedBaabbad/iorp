"""Certificates of Analysis (QUAL-COA-001).

- quality_settings (certificate prefix and last number) and quality_certificates (values frozen from a closed inspection,
  numbered on issue, revoked or superseded by a replacement).
- Permissions quality:certificates:{read,create,update,issue,revoke}: granted to the organization admin, factory manager and
  quality manager; read also to the viewer. Grants added here are recorded so the downgrade removes exactly them.
No existing data changes.
"""
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "f6a1b2i9"
down_revision = "f6a1b2i8"
branch_labels = None
depends_on = None

BACKUP = "quality_coa_i9_added_grants"
NEW = {
    "quality:certificates:read": ("read", "Read Certificates of Analysis"),
    "quality:certificates:create": ("create", "Create Certificates of Analysis"),
    "quality:certificates:update": ("update", "Update Certificates of Analysis"),
    "quality:certificates:issue": ("issue", "Approve and Issue Certificates of Analysis"),
    "quality:certificates:revoke": ("revoke", "Revoke Certificates of Analysis"),
}
MANAGERS = ("organization_admin", "factory_manager", "quality_manager")


def upgrade():
    bind = op.get_bind()
    uuid, dt = sa.Uuid(), sa.DateTime(timezone=True)
    op.create_table("quality_settings",
                    sa.Column("organization_id", uuid, sa.ForeignKey("foundation_organizations.id"), primary_key=True),
                    sa.Column("coa_prefix", sa.String(20), nullable=False, server_default="COA-"),
                    sa.Column("coa_last_number", sa.Integer(), nullable=False, server_default="0"),
                    sa.Column("updated_at", dt, nullable=False, server_default=sa.func.now()))
    user = lambda name, nullable=True: sa.Column(name, uuid, sa.ForeignKey("foundation_users.id"), nullable=nullable)  # noqa: E731
    op.create_table("quality_certificates",
                    sa.Column("id", uuid, primary_key=True),
                    sa.Column("organization_id", uuid, sa.ForeignKey("foundation_organizations.id"), nullable=False, index=True),
                    sa.Column("certificate_no", sa.String(40)), sa.Column("status", sa.String(12), nullable=False, server_default="draft"),
                    sa.Column("quality_check_id", uuid, sa.ForeignKey("quality_checks.id"), nullable=False, index=True),
                    sa.Column("production_order_id", uuid, index=True), sa.Column("production_order_item_id", uuid),
                    sa.Column("customer_id", uuid, index=True), sa.Column("customer_name", sa.String(255), nullable=False, server_default=""),
                    sa.Column("customer_po", sa.String(80)), sa.Column("delivery_ref", sa.String(80)),
                    sa.Column("batch_no", sa.String(80), nullable=False), sa.Column("product_description", sa.String(255), nullable=False),
                    sa.Column("grade", sa.String(80)), sa.Column("production_date", sa.Date()), sa.Column("inspection_date", sa.Date()),
                    sa.Column("quantity", sa.Numeric(14, 3), nullable=False), sa.Column("unit_label", sa.String(32), nullable=False, server_default=""),
                    sa.Column("package_count", sa.Integer()), sa.Column("sample_size", sa.String(120)), sa.Column("sampling_reference", sa.String(120)),
                    sa.Column("retained_sample", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("retention_ref", sa.String(80)),
                    sa.Column("deviation_note", sa.Text()), sa.Column("remarks", sa.Text()),
                    sa.Column("inspection_code", sa.String(32), nullable=False), sa.Column("inspection_result", sa.String(32), nullable=False),
                    sa.Column("specification_code", sa.String(40)), sa.Column("specification_revision", sa.Integer()),
                    sa.Column("measurements", sa.JSON(), nullable=False), sa.Column("inspector_name", sa.String(200)),
                    sa.Column("supersedes_id", uuid, sa.ForeignKey("quality_certificates.id")),
                    user("prepared_by_user_id", False), sa.Column("issued_at", dt), user("issued_by_user_id"),
                    sa.Column("revoked_at", dt), user("revoked_by_user_id"), sa.Column("revoke_reason", sa.Text()),
                    sa.Column("created_at", dt, nullable=False, server_default=sa.func.now()),
                    sa.Column("updated_at", dt, nullable=False, server_default=sa.func.now()),
                    sa.UniqueConstraint("organization_id", "certificate_no", name="uq_quality_certificates_org_no"),
                    sa.CheckConstraint("status IN ('draft', 'issued', 'revoked')", name="ck_quality_certificates_status"))

    op.create_table(BACKUP, sa.Column("id", uuid, primary_key=True), sa.Column("role_id", uuid, nullable=False),
                    sa.Column("permission_id", uuid, nullable=False))
    backup = sa.table(BACKUP, sa.column("id"), sa.column("role_id"), sa.column("permission_id"))
    for org in bind.scalars(sa.text("SELECT id FROM foundation_organizations")).all():
        ids = {}
        for code, (action, name) in NEW.items():
            bind.execute(sa.text("INSERT INTO foundation_permissions (id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) "
                                 "VALUES (:id,:org,:code,:name,:description,'quality','certificates',:action,now(),now()) ON CONFLICT (organization_id,code) DO NOTHING"),
                         dict(id=uuid4(), org=org, code=code, name=name, description=name, action=action))
            ids[code] = bind.scalar(sa.text("SELECT id FROM foundation_permissions WHERE organization_id=:org AND code=:code"), dict(org=org, code=code))
        roles = dict(bind.execute(sa.text("SELECT code, id FROM foundation_roles WHERE organization_id=:org AND is_system"), dict(org=org)).all())
        grants = [(roles[r], ids[c]) for r in MANAGERS if r in roles for c in NEW]
        if "viewer" in roles:
            grants.append((roles["viewer"], ids["quality:certificates:read"]))
        for role_id, permission_id in grants:
            added = bind.scalar(sa.text("INSERT INTO foundation_role_permissions (id,role_id,permission_id,scope) VALUES (:id,:role,:p,'organization') "
                                        "ON CONFLICT (role_id,permission_id) DO NOTHING RETURNING id"), dict(id=uuid4(), role=role_id, p=permission_id))
            if added:
                bind.execute(backup.insert().values(id=added, role_id=role_id, permission_id=permission_id))


def downgrade():
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT count(*) FROM quality_certificates WHERE status <> 'draft'")):
        raise RuntimeError("Issued or revoked certificates exist; they are official records and are not dropped by a downgrade.")
    bind.execute(sa.text(f"DELETE FROM foundation_role_permissions WHERE id IN (SELECT id FROM {BACKUP})"))
    op.drop_table(BACKUP)
    codes = sa.bindparam("codes", expanding=True)
    bind.execute(sa.text("DELETE FROM foundation_role_permissions WHERE permission_id IN (SELECT id FROM foundation_permissions WHERE code IN :codes)").bindparams(codes),
                 dict(codes=list(NEW)))
    bind.execute(sa.text("DELETE FROM foundation_permissions WHERE code IN :codes").bindparams(codes), dict(codes=list(NEW)))
    op.drop_table("quality_certificates")
    op.drop_table("quality_settings")
