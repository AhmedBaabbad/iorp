"""Reference lists (MD-002): sectors, opportunity sources, countries and cities, in master data.

- masterdata_list_items (a city names its country by key).
- Permissions masterdata:lists:{read,update}, granted as the system roles define them. Grants added here are recorded so
  the downgrade removes exactly them.
No existing data changes: the texts customers, suppliers and shipments hold stay until mapped from the master data screen.
"""
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "f6a1b2k4"
down_revision = "f6a1b2k3"
branch_labels = None
depends_on = None

BACKUP = "masterdata_k4_added_grants"
NAMES = {"masterdata:lists:read": "Read Reference Lists (sectors, sources, countries, cities)", "masterdata:lists:update": "Manage Reference Lists"}
ALL = tuple(NAMES)
READ = ("masterdata:lists:read",)
ROLES = {
    "organization_admin": ALL, "factory_manager": ALL, "commercial_manager": ALL, "shipping_manager": ALL, "procurement_manager": ALL,
    "production_manager": READ, "quality_manager": READ, "sales_rep": READ, "warehouse_manager": READ, "maintenance_manager": READ,
    "safety_manager": READ, "finance_manager": READ, "viewer": READ,
}


def upgrade():
    bind = op.get_bind()
    uuid, dt = sa.Uuid(), sa.DateTime(timezone=True)
    op.create_table(
        "masterdata_list_items",
        sa.Column("id", uuid, primary_key=True), sa.Column("organization_id", uuid, sa.ForeignKey("foundation_organizations.id"), nullable=False),
        sa.Column("list", sa.String(20), nullable=False), sa.Column("key", sa.String(60), nullable=False),
        sa.Column("name_ar", sa.String(200), nullable=False), sa.Column("name_en", sa.String(200), nullable=False),
        sa.Column("parent_key", sa.String(60)), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", dt, nullable=False), sa.Column("updated_at", dt, nullable=False),
        sa.UniqueConstraint("organization_id", "list", "key", name="uq_masterdata_list_items_key"),
        sa.CheckConstraint("list IN ('sector', 'opportunity_source', 'country', 'city')", name="ck_masterdata_list_items_list"))
    op.create_index("ix_masterdata_list_items_organization_id", "masterdata_list_items", ["organization_id"])

    op.create_table(BACKUP, sa.Column("id", uuid, primary_key=True), sa.Column("role_id", uuid, nullable=False), sa.Column("permission_id", uuid, nullable=False))
    backup = sa.table(BACKUP, sa.column("id"), sa.column("role_id"), sa.column("permission_id"))
    for organization in bind.scalars(sa.text("SELECT id FROM foundation_organizations")).all():
        for code, name in NAMES.items():
            _module, resource, action = code.split(":")
            bind.execute(sa.text("INSERT INTO foundation_permissions (id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) "
                                 "VALUES (:id,:org,:code,:name,:description,'masterdata',:resource,:action,now(),now()) ON CONFLICT (organization_id,code) DO NOTHING"),
                         dict(id=uuid4(), org=organization, code=code, name=name, description=name, resource=resource, action=action))
        ids = dict(bind.execute(sa.text("SELECT code, id FROM foundation_permissions WHERE organization_id=:org AND module_name='masterdata' "
                                        "AND resource_name='lists'"), dict(org=organization)).all())
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
    if bind.scalar(sa.text("SELECT count(*) FROM masterdata_list_items")):
        raise RuntimeError("List items exist; reference lists are not dropped by a downgrade.")
    bind.execute(sa.text(f"DELETE FROM foundation_role_permissions WHERE id IN (SELECT id FROM {BACKUP})"))
    op.drop_table(BACKUP)
    codes = sa.bindparam("codes", expanding=True)
    bind.execute(sa.text("DELETE FROM foundation_role_permissions WHERE permission_id IN (SELECT id FROM foundation_permissions WHERE code IN :codes)").bindparams(codes),
                 dict(codes=list(ALL)))
    bind.execute(sa.text("DELETE FROM foundation_permissions WHERE code IN :codes").bindparams(codes), dict(codes=list(ALL)))
    op.drop_table("masterdata_list_items")
