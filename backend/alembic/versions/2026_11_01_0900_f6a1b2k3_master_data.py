"""Master data (MD-001): a new module — the organization's products with their specification templates, and its general
settings (VAT rate, default currency).

- masterdata_settings, masterdata_counters, masterdata_products, masterdata_product_properties.
- Permissions masterdata:products:{read,create,update} and masterdata:settings:{read,update}, granted as the system roles
  define them. Grants added here are recorded so the downgrade removes exactly them.
No existing data changes: product types other modules stored as text stay as they are until mapped to a product from the
master data screen (each module rewrites its own records).
"""
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "f6a1b2k3"
down_revision = "f6a1b2k2"
branch_labels = None
depends_on = None

BACKUP = "masterdata_k3_added_grants"
NAMES = {
    "masterdata:products:read": "Read Products", "masterdata:products:create": "Add Products",
    "masterdata:products:update": "Update Products and Their Specification Templates",
    "masterdata:settings:read": "Read General Settings (VAT, currency)", "masterdata:settings:update": "Update General Settings (VAT, currency)",
}
ALL = tuple(NAMES)
READ = ("masterdata:products:read", "masterdata:settings:read")
DEFINE = (*READ, "masterdata:products:create", "masterdata:products:update")
ROLES = {
    "organization_admin": ALL, "factory_manager": DEFINE, "commercial_manager": DEFINE, "production_manager": DEFINE, "quality_manager": DEFINE,
    "sales_rep": READ, "warehouse_manager": READ, "shipping_manager": READ, "maintenance_manager": READ, "procurement_manager": READ,
    "safety_manager": READ, "finance_manager": (*READ, "masterdata:settings:update"), "viewer": READ,
}


def upgrade():
    bind = op.get_bind()
    uuid, dt = sa.Uuid(), sa.DateTime(timezone=True)
    op.create_table(
        "masterdata_settings",
        sa.Column("organization_id", uuid, sa.ForeignKey("foundation_organizations.id"), primary_key=True),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False, server_default="15"),
        sa.Column("default_currency", sa.String(3), nullable=False, server_default="SAR"),
        sa.Column("updated_by_user_id", uuid, sa.ForeignKey("foundation_users.id", ondelete="SET NULL")),
        sa.Column("updated_at", dt, nullable=False),
        sa.CheckConstraint("vat_rate >= 0 AND vat_rate <= 100", name="ck_masterdata_settings_vat_rate"),
        sa.CheckConstraint("default_currency IN ('SAR', 'USD')", name="ck_masterdata_settings_currency"))
    op.create_table(
        "masterdata_counters",
        sa.Column("organization_id", uuid, sa.ForeignKey("foundation_organizations.id"), primary_key=True),
        sa.Column("kind", sa.String(8), primary_key=True), sa.Column("value", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "masterdata_products",
        sa.Column("id", uuid, primary_key=True), sa.Column("organization_id", uuid, sa.ForeignKey("foundation_organizations.id"), nullable=False),
        sa.Column("code", sa.String(20), nullable=False), sa.Column("key", sa.String(60), nullable=False),
        sa.Column("name_ar", sa.String(255), nullable=False), sa.Column("name_en", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False, server_default="finished"), sa.Column("default_unit", sa.String(32)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("notes", sa.Text()),
        sa.Column("created_by_user_id", uuid, sa.ForeignKey("foundation_users.id"), nullable=False),
        sa.Column("created_at", dt, nullable=False), sa.Column("updated_at", dt, nullable=False),
        sa.UniqueConstraint("organization_id", "key", name="uq_masterdata_products_key"),
        sa.UniqueConstraint("organization_id", "code", name="uq_masterdata_products_code"),
        sa.CheckConstraint("kind IN ('finished', 'material')", name="ck_masterdata_products_kind"))
    op.create_index("ix_masterdata_products_organization_id", "masterdata_products", ["organization_id"])
    op.create_table(
        "masterdata_product_properties",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("product_id", uuid, sa.ForeignKey("masterdata_products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False), sa.Column("key", sa.String(60), nullable=False),
        sa.Column("name_ar", sa.String(120), nullable=False), sa.Column("name_en", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False, server_default="text"), sa.Column("unit", sa.String(32)),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("options", sa.JSON()),
        sa.UniqueConstraint("product_id", "key", name="uq_masterdata_product_properties_key"),
        sa.CheckConstraint("kind IN ('number', 'text', 'choice')", name="ck_masterdata_product_properties_kind"))
    op.create_index("ix_masterdata_product_properties_product_id", "masterdata_product_properties", ["product_id"])

    op.create_table(BACKUP, sa.Column("id", uuid, primary_key=True), sa.Column("role_id", uuid, nullable=False), sa.Column("permission_id", uuid, nullable=False))
    backup = sa.table(BACKUP, sa.column("id"), sa.column("role_id"), sa.column("permission_id"))
    for organization in bind.scalars(sa.text("SELECT id FROM foundation_organizations")).all():
        for code, name in NAMES.items():
            _module, resource, action = code.split(":")
            bind.execute(sa.text("INSERT INTO foundation_permissions (id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) "
                                 "VALUES (:id,:org,:code,:name,:description,'masterdata',:resource,:action,now(),now()) ON CONFLICT (organization_id,code) DO NOTHING"),
                         dict(id=uuid4(), org=organization, code=code, name=name, description=name, resource=resource, action=action))
        ids = dict(bind.execute(sa.text("SELECT code, id FROM foundation_permissions WHERE organization_id=:org AND module_name='masterdata'"),
                                dict(org=organization)).all())
        roles = dict(bind.execute(sa.text("SELECT code, id FROM foundation_roles WHERE organization_id=:org AND is_system"), dict(org=organization)).all())
        for role, codes in ROLES.items():
            if role not in roles:
                continue
            for code in codes:
                added = bind.scalar(sa.text("INSERT INTO foundation_role_permissions (id,role_id,permission_id,scope) VALUES (:id,:role,:p,'organization') "
                                            "ON CONFLICT (role_id,permission_id) DO NOTHING RETURNING id"), dict(id=uuid4(), role=roles[role], p=ids[code]))
                if added:
                    bind.execute(backup.insert().values(id=added, role_id=roles[role], permission_id=ids[code]))


def downgrade():
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT count(*) FROM masterdata_products")):
        raise RuntimeError("Products exist; master data is not dropped by a downgrade.")
    bind.execute(sa.text(f"DELETE FROM foundation_role_permissions WHERE id IN (SELECT id FROM {BACKUP})"))
    op.drop_table(BACKUP)
    codes = sa.bindparam("codes", expanding=True)
    bind.execute(sa.text("DELETE FROM foundation_role_permissions WHERE permission_id IN (SELECT id FROM foundation_permissions WHERE code IN :codes)").bindparams(codes),
                 dict(codes=list(ALL)))
    bind.execute(sa.text("DELETE FROM foundation_permissions WHERE code IN :codes").bindparams(codes), dict(codes=list(ALL)))
    for table in ("masterdata_product_properties", "masterdata_products", "masterdata_counters", "masterdata_settings"):
        op.drop_table(table)
