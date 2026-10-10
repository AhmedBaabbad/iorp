"""Purchase orders (PROC-003).

- procurement_purchase_orders and procurement_purchase_order_lines; procurement_settings gains the PO prefix and the
  general terms printed on every order; goods receipts (and their lines) may name the order (and line) they deliver.
- procurement_events statuses widen to 20 characters (partially_received).
- Permissions procurement:purchase_orders:{read,create,update,approve,cancel}, granted as the system roles define them.
  Grants added here are recorded so the downgrade removes exactly them.
No existing data changes.
"""
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "f6a1b2k1"
down_revision = "f6a1b2j9"
branch_labels = None
depends_on = None

BACKUP = "procurement_k1_added_grants"
NAMES = {
    "procurement:purchase_orders:read": "Read Purchase Orders", "procurement:purchase_orders:create": "Create Purchase Orders",
    "procurement:purchase_orders:update": "Update and Send Purchase Orders", "procurement:purchase_orders:approve": "Approve and Close Purchase Orders",
    "procurement:purchase_orders:cancel": "Cancel Purchase Orders",
}
ALL = tuple(NAMES)
READ = ("procurement:purchase_orders:read",)
ROLES = {"organization_admin": ALL, "procurement_manager": ALL, "warehouse_manager": READ, "quality_manager": READ, "factory_manager": READ,
         "finance_manager": READ, "viewer": READ}
STATUSES = "('draft', 'approved', 'sent', 'partially_received', 'received', 'closed', 'cancelled')"


def upgrade():
    bind = op.get_bind()
    uuid, dt, money = sa.Uuid(), sa.DateTime(timezone=True), sa.Numeric(14, 2)
    user = lambda name: sa.Column(name, uuid, sa.ForeignKey("foundation_users.id"))  # noqa: E731
    op.add_column("procurement_settings", sa.Column("po_prefix", sa.String(20), nullable=False, server_default="PO-"))
    op.add_column("procurement_settings", sa.Column("po_terms_ar", sa.Text()))
    op.add_column("procurement_settings", sa.Column("po_terms_en", sa.Text()))
    op.alter_column("procurement_events", "from_status", type_=sa.String(20))
    op.alter_column("procurement_events", "to_status", type_=sa.String(20))

    op.create_table(
        "procurement_purchase_orders",
        sa.Column("id", uuid, primary_key=True), sa.Column("organization_id", uuid, sa.ForeignKey("foundation_organizations.id"), nullable=False),
        sa.Column("po_number", sa.String(40), nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("order_date", sa.Date(), nullable=False), sa.Column("required_date", sa.Date()),
        sa.Column("supplier_id", uuid, sa.ForeignKey("procurement_suppliers.id"), nullable=False), sa.Column("supplier_name", sa.String(255), nullable=False),
        sa.Column("attention", sa.String(200)), sa.Column("supplier_quote_ref", sa.String(80)), sa.Column("subject", sa.String(255)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="SAR"), sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False, server_default="15"),
        sa.Column("subtotal_amount", money, nullable=False, server_default="0"), sa.Column("discount_amount", money, nullable=False, server_default="0"),
        sa.Column("tax_amount", money, nullable=False, server_default="0"), sa.Column("total_amount", money, nullable=False, server_default="0"),
        sa.Column("payment_terms", sa.String(20)), sa.Column("payment_terms_note", sa.String(255)), sa.Column("incoterm", sa.String(3)),
        sa.Column("delivery_place", sa.String(500)), sa.Column("notes", sa.Text()),
        sa.Column("approved_at", dt), user("approved_by_user_id"), sa.Column("sent_at", dt), user("sent_by_user_id"),
        sa.Column("closed_at", dt), sa.Column("close_reason", sa.Text()), sa.Column("cancel_reason", sa.Text()),
        sa.Column("created_by_user_id", uuid, sa.ForeignKey("foundation_users.id"), nullable=False),
        sa.Column("created_at", dt, nullable=False), sa.Column("updated_at", dt, nullable=False),
        sa.UniqueConstraint("organization_id", "po_number", name="uq_procurement_purchase_orders_no"),
        sa.CheckConstraint(f"status IN {STATUSES}", name="ck_procurement_purchase_orders_status"),
        sa.CheckConstraint("currency IN ('SAR', 'USD')", name="ck_procurement_purchase_orders_currency"),
        sa.CheckConstraint("tax_rate IN (0, 15)", name="ck_procurement_purchase_orders_tax_rate"))
    for column in ("organization_id", "order_date", "supplier_id"):
        op.create_index(f"ix_procurement_purchase_orders_{column}", "procurement_purchase_orders", [column])
    op.create_index("ix_procurement_purchase_orders_org_status", "procurement_purchase_orders", ["organization_id", "status"])
    op.create_table(
        "procurement_purchase_order_lines",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("order_id", uuid, sa.ForeignKey("procurement_purchase_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False), sa.Column("material_id", uuid, sa.ForeignKey("procurement_materials.id")),
        sa.Column("description", sa.String(500), nullable=False), sa.Column("notes", sa.String(500)),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False), sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 4), nullable=False), sa.Column("line_total", money, nullable=False),
        sa.UniqueConstraint("order_id", "line_no", name="uq_procurement_purchase_order_lines_no"))
    op.create_index("ix_procurement_purchase_order_lines_order_id", "procurement_purchase_order_lines", ["order_id"])
    op.create_index("ix_procurement_purchase_order_lines_material_id", "procurement_purchase_order_lines", ["material_id"])
    op.add_column("procurement_receipts", sa.Column("purchase_order_id", uuid, sa.ForeignKey("procurement_purchase_orders.id")))
    op.create_index("ix_procurement_receipts_purchase_order_id", "procurement_receipts", ["purchase_order_id"])
    op.add_column("procurement_receipt_lines", sa.Column("po_line_id", uuid, sa.ForeignKey("procurement_purchase_order_lines.id")))
    op.create_index("ix_procurement_receipt_lines_po_line_id", "procurement_receipt_lines", ["po_line_id"])

    op.create_table(BACKUP, sa.Column("id", uuid, primary_key=True), sa.Column("role_id", uuid, nullable=False), sa.Column("permission_id", uuid, nullable=False))
    backup = sa.table(BACKUP, sa.column("id"), sa.column("role_id"), sa.column("permission_id"))
    for organization in bind.scalars(sa.text("SELECT id FROM foundation_organizations")).all():
        for code, name in NAMES.items():
            _module, resource, action = code.split(":")
            bind.execute(sa.text("INSERT INTO foundation_permissions (id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) "
                                 "VALUES (:id,:org,:code,:name,:description,'procurement',:resource,:action,now(),now()) ON CONFLICT (organization_id,code) DO NOTHING"),
                         dict(id=uuid4(), org=organization, code=code, name=name, description=name, resource=resource, action=action))
        ids = dict(bind.execute(sa.text("SELECT code, id FROM foundation_permissions WHERE organization_id=:org AND resource_name='purchase_orders' "
                                        "AND module_name='procurement'"), dict(org=organization)).all())
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
    if bind.scalar(sa.text("SELECT count(*) FROM procurement_purchase_orders")):
        raise RuntimeError("Purchase orders exist; they are not dropped by a downgrade.")
    bind.execute(sa.text(f"DELETE FROM foundation_role_permissions WHERE id IN (SELECT id FROM {BACKUP})"))
    op.drop_table(BACKUP)
    codes = sa.bindparam("codes", expanding=True)
    bind.execute(sa.text("DELETE FROM foundation_role_permissions WHERE permission_id IN (SELECT id FROM foundation_permissions WHERE code IN :codes)").bindparams(codes),
                 dict(codes=list(ALL)))
    bind.execute(sa.text("DELETE FROM foundation_permissions WHERE code IN :codes").bindparams(codes), dict(codes=list(ALL)))
    op.drop_index("ix_procurement_receipt_lines_po_line_id", table_name="procurement_receipt_lines")
    op.drop_column("procurement_receipt_lines", "po_line_id")
    op.drop_index("ix_procurement_receipts_purchase_order_id", table_name="procurement_receipts")
    op.drop_column("procurement_receipts", "purchase_order_id")
    op.drop_table("procurement_purchase_order_lines")
    op.drop_table("procurement_purchase_orders")
    op.alter_column("procurement_events", "to_status", type_=sa.String(16))
    op.alter_column("procurement_events", "from_status", type_=sa.String(16))
    for name in ("po_terms_en", "po_terms_ar", "po_prefix"):
        op.drop_column("procurement_settings", name)
