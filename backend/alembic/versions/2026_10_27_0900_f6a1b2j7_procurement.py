"""Procurement (PROC-001): a new module — suppliers, materials and goods receipts.

- procurement_settings (receipt prefix), procurement_counters (SUP / MAT codes, GRN numbers per year),
  procurement_suppliers, procurement_materials, procurement_receipts, procurement_receipt_lines, procurement_events.
- Permissions procurement:suppliers:{read,create,update,approve}, materials:{read,create,update},
  receipts:{read,create,update,receive,cancel}, settings:update, granted as the system roles define them. Grants added
  here are recorded so the downgrade removes exactly them.
No existing data changes.
"""
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "f6a1b2j7"
down_revision = "f6a1b2j6"
branch_labels = None
depends_on = None

BACKUP = "procurement_j7_added_grants"
NAMES = {
    "procurement:suppliers:read": "Read Suppliers", "procurement:suppliers:create": "Create Suppliers",
    "procurement:suppliers:update": "Update Suppliers", "procurement:suppliers:approve": "Approve or Block Suppliers",
    "procurement:materials:read": "Read Materials", "procurement:materials:create": "Create Materials", "procurement:materials:update": "Update Materials",
    "procurement:receipts:read": "Read Goods Receipts", "procurement:receipts:create": "Create Goods Receipts",
    "procurement:receipts:update": "Update Goods Receipts", "procurement:receipts:receive": "Confirm Goods Receipts",
    "procurement:receipts:cancel": "Cancel Goods Receipts", "procurement:settings:update": "Update Procurement Settings",
}
ALL = tuple(NAMES)
READ = ("procurement:suppliers:read", "procurement:materials:read", "procurement:receipts:read")
ROLES = {
    "organization_admin": ALL, "procurement_manager": ALL,
    "warehouse_manager": (*READ, "procurement:receipts:create", "procurement:receipts:update", "procurement:receipts:receive", "procurement:receipts:cancel"),
    "quality_manager": (*READ, "procurement:suppliers:approve", "procurement:materials:update"),
    "factory_manager": READ, "finance_manager": ("procurement:suppliers:read", "procurement:receipts:read"), "viewer": READ,
}


def upgrade():
    bind = op.get_bind()
    uuid, dt = sa.Uuid(), sa.DateTime(timezone=True)
    org = lambda primary=False: sa.Column("organization_id", uuid, sa.ForeignKey("foundation_organizations.id"), nullable=False, primary_key=primary)  # noqa: E731
    user = lambda name, nullable=True: sa.Column(name, uuid, sa.ForeignKey("foundation_users.id"), nullable=nullable)  # noqa: E731
    stamps = lambda: (sa.Column("created_at", dt, nullable=False), sa.Column("updated_at", dt, nullable=False))  # noqa: E731

    op.create_table("procurement_settings", org(True), sa.Column("receipt_prefix", sa.String(20), nullable=False, server_default="GRN-"),
                    sa.Column("updated_at", dt, nullable=False))
    op.create_table("procurement_counters", org(True), sa.Column("kind", sa.String(8), primary_key=True), sa.Column("year", sa.Integer(), primary_key=True),
                    sa.Column("value", sa.Integer(), nullable=False, server_default="0"))
    op.create_table("procurement_suppliers", sa.Column("id", uuid, primary_key=True), org(), sa.Column("supplier_code", sa.String(20), nullable=False),
                    sa.Column("name", sa.String(255), nullable=False), sa.Column("category", sa.String(16), nullable=False, server_default="raw_material"),
                    sa.Column("status", sa.String(12), nullable=False, server_default="pending"), sa.Column("status_reason", sa.Text()),
                    sa.Column("status_changed_at", dt), user("status_changed_by_user_id"), sa.Column("supplies", sa.String(500)),
                    sa.Column("contact_name", sa.String(200)), sa.Column("phone", sa.String(20)), sa.Column("email", sa.String(255)),
                    sa.Column("address", sa.Text()), sa.Column("city", sa.String(120)), sa.Column("country", sa.String(80)),
                    sa.Column("vat_number", sa.String(40)), sa.Column("cr_number", sa.String(40)), sa.Column("notes", sa.Text()),
                    user("created_by_user_id", False), *stamps(),
                    sa.UniqueConstraint("organization_id", "supplier_code", name="uq_procurement_suppliers_code"),
                    sa.CheckConstraint("status IN ('pending', 'approved', 'conditional', 'blocked')", name="ck_procurement_suppliers_status"),
                    sa.CheckConstraint("category IN ('raw_material', 'packaging', 'consumables', 'services', 'other')", name="ck_procurement_suppliers_category"))
    op.create_index("ix_procurement_suppliers_organization_id", "procurement_suppliers", ["organization_id"])
    op.create_index("ix_procurement_suppliers_org_status", "procurement_suppliers", ["organization_id", "status"])
    op.create_table("procurement_materials", sa.Column("id", uuid, primary_key=True), org(), sa.Column("material_code", sa.String(20), nullable=False),
                    sa.Column("name", sa.String(255), nullable=False), sa.Column("category", sa.String(16), nullable=False, server_default="resin"),
                    sa.Column("unit", sa.String(32), nullable=False, server_default="kg"),
                    sa.Column("inspection_required", sa.Boolean(), nullable=False, server_default=sa.true()),
                    sa.Column("spec_product_type", sa.String(120)), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
                    sa.Column("notes", sa.Text()), *stamps(),
                    sa.UniqueConstraint("organization_id", "material_code", name="uq_procurement_materials_code"),
                    sa.CheckConstraint("category IN ('resin', 'masterbatch', 'additive', 'core', 'carton', 'film', 'accessory', 'other')",
                                       name="ck_procurement_materials_category"))
    op.create_index("ix_procurement_materials_organization_id", "procurement_materials", ["organization_id"])
    op.create_table("procurement_receipts", sa.Column("id", uuid, primary_key=True), org(), sa.Column("receipt_no", sa.String(40), nullable=False),
                    sa.Column("status", sa.String(12), nullable=False, server_default="draft"), sa.Column("receipt_date", sa.Date(), nullable=False),
                    sa.Column("supplier_id", uuid, sa.ForeignKey("procurement_suppliers.id"), nullable=False),
                    sa.Column("supplier_name", sa.String(255), nullable=False), sa.Column("supplier_delivery_no", sa.String(80)),
                    sa.Column("supplier_invoice_no", sa.String(80)), sa.Column("purchase_reference", sa.String(80)),
                    sa.Column("vehicle_plate", sa.String(40)), sa.Column("driver_name", sa.String(200)), sa.Column("notes", sa.Text()),
                    sa.Column("received_at", dt), user("received_by_user_id"), sa.Column("cancel_reason", sa.Text()),
                    user("created_by_user_id", False), *stamps(),
                    sa.UniqueConstraint("organization_id", "receipt_no", name="uq_procurement_receipts_no"),
                    sa.CheckConstraint("status IN ('draft', 'received', 'cancelled')", name="ck_procurement_receipts_status"))
    for name, columns in (("ix_procurement_receipts_organization_id", ["organization_id"]), ("ix_procurement_receipts_receipt_date", ["receipt_date"]),
                          ("ix_procurement_receipts_supplier_id", ["supplier_id"]), ("ix_procurement_receipts_org_status", ["organization_id", "status"])):
        op.create_index(name, "procurement_receipts", columns)
    op.create_table("procurement_receipt_lines", sa.Column("id", uuid, primary_key=True),
                    sa.Column("receipt_id", uuid, sa.ForeignKey("procurement_receipts.id", ondelete="CASCADE"), nullable=False),
                    sa.Column("line_no", sa.Integer(), nullable=False), sa.Column("material_id", uuid, sa.ForeignKey("procurement_materials.id")),
                    sa.Column("description", sa.String(255), nullable=False), sa.Column("supplier_lot", sa.String(80)),
                    sa.Column("quantity", sa.Numeric(14, 3), nullable=False), sa.Column("unit", sa.String(32), nullable=False),
                    sa.Column("package_count", sa.Integer()), sa.Column("weight", sa.Numeric(14, 3)),
                    sa.Column("weight_unit", sa.String(8), nullable=False, server_default="kg"),
                    sa.Column("inspection_required", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("notes", sa.String(500)),
                    sa.UniqueConstraint("receipt_id", "line_no", name="uq_procurement_receipt_lines_no"),
                    sa.CheckConstraint("quantity > 0", name="ck_procurement_receipt_lines_quantity"))
    op.create_index("ix_procurement_receipt_lines_receipt_id", "procurement_receipt_lines", ["receipt_id"])
    op.create_index("ix_procurement_receipt_lines_material_id", "procurement_receipt_lines", ["material_id"])
    op.create_table("procurement_events", sa.Column("id", uuid, primary_key=True), org(), sa.Column("entity_type", sa.String(16), nullable=False),
                    sa.Column("entity_id", uuid, nullable=False), sa.Column("action", sa.String(32), nullable=False), sa.Column("from_status", sa.String(16)),
                    sa.Column("to_status", sa.String(16)), sa.Column("reason", sa.Text()),
                    sa.Column("actor_user_id", uuid, sa.ForeignKey("foundation_users.id", ondelete="SET NULL")), sa.Column("occurred_at", dt, nullable=False))
    op.create_index("ix_procurement_events_entity", "procurement_events", ["organization_id", "entity_type", "entity_id"])

    op.create_table(BACKUP, sa.Column("id", uuid, primary_key=True), sa.Column("role_id", uuid, nullable=False), sa.Column("permission_id", uuid, nullable=False))
    backup = sa.table(BACKUP, sa.column("id"), sa.column("role_id"), sa.column("permission_id"))
    for organization in bind.scalars(sa.text("SELECT id FROM foundation_organizations")).all():
        for code, name in NAMES.items():
            _module, resource, action = code.split(":")
            bind.execute(sa.text("INSERT INTO foundation_permissions (id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) "
                                 "VALUES (:id,:org,:code,:name,:description,'procurement',:resource,:action,now(),now()) ON CONFLICT (organization_id,code) DO NOTHING"),
                         dict(id=uuid4(), org=organization, code=code, name=name, description=name, resource=resource, action=action))
        ids = dict(bind.execute(sa.text("SELECT code, id FROM foundation_permissions WHERE organization_id=:org AND module_name='procurement'"),
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
    if bind.scalar(sa.text("SELECT count(*) FROM procurement_suppliers")):
        raise RuntimeError("Suppliers exist; procurement records are not dropped by a downgrade.")
    bind.execute(sa.text(f"DELETE FROM foundation_role_permissions WHERE id IN (SELECT id FROM {BACKUP})"))
    op.drop_table(BACKUP)
    codes = sa.bindparam("codes", expanding=True)
    bind.execute(sa.text("DELETE FROM foundation_role_permissions WHERE permission_id IN (SELECT id FROM foundation_permissions WHERE code IN :codes)").bindparams(codes),
                 dict(codes=list(ALL)))
    bind.execute(sa.text("DELETE FROM foundation_permissions WHERE code IN :codes").bindparams(codes), dict(codes=list(ALL)))
    for table in ("procurement_events", "procurement_receipt_lines", "procurement_receipts", "procurement_materials", "procurement_suppliers",
                  "procurement_counters", "procurement_settings"):
        op.drop_table(table)
