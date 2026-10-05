"""Returns and delivery outcomes (SHIP-004).

- Shipments: attempt (a returned note is rescheduled under its number), gate and received weights, failed_at,
  close_reason; new statuses partially_delivered, returned and not_delivered.
- Lines: production_order_id / production_order_no (the batch the goods come from), delivered_quantity (filled for
  notes already delivered: all of it).
- shipping_returns / shipping_return_lines (RT-YYYY-NNNN, per-year counter shipping_return_counters), and
  shipping_attachments (proof of delivery, photos). Events may belong to a return (return_id).
- Settings: return_prefix (RT-), return_window_days (30), weight_tolerance_pct (1.00).
- Permissions shipping:returns:{read,create,approve,receive,cancel}, granted as the system roles define them;
  sales representatives, quality and finance managers also read shipments. Grants added here are recorded so the
  downgrade removes exactly them. The labels of shipments:deliver and shipments:cancel follow their wider meaning.
"""
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "f6a1b2j4"
down_revision = "f6a1b2j3"
branch_labels = None
depends_on = None

BACKUP = "shipping_j4_added_grants"
NAMES = {
    "shipping:returns:read": "Read Returns", "shipping:returns:create": "Register Customer Returns",
    "shipping:returns:approve": "Approve or Reject Returns", "shipping:returns:receive": "Receive Returned Goods",
    "shipping:returns:cancel": "Cancel Returns",
}
RENAMED = {"shipping:shipments:deliver": ("Confirm Shipment Delivery", "Record Shipment Delivery"),
           "shipping:shipments:cancel": ("Cancel Shipments", "Cancel or Close Shipments")}
RETURNS = tuple(NAMES)
SHIP_READ = ("shipping:shipments:read", "shipping:returns:read")
ROLES = {
    "organization_admin": RETURNS, "shipping_manager": RETURNS,
    "warehouse_manager": ("shipping:returns:read", "shipping:returns:receive"),
    "commercial_manager": ("shipping:returns:read", "shipping:returns:create", "shipping:returns:approve", "shipping:returns:cancel"),
    "sales_rep": (*SHIP_READ, "shipping:returns:create"),
    "factory_manager": ("shipping:returns:read", "shipping:returns:approve"),
    "quality_manager": SHIP_READ, "finance_manager": SHIP_READ, "viewer": ("shipping:returns:read",),
}
OLD_STATUSES = "('draft', 'ready', 'dispatched', 'delivered', 'cancelled')"
NEW_STATUSES = "('draft', 'ready', 'dispatched', 'delivered', 'partially_delivered', 'returned', 'not_delivered', 'cancelled')"


def upgrade():
    bind = op.get_bind()
    uuid, dt, qty = sa.Uuid(), sa.DateTime(timezone=True), sa.Numeric(14, 3)
    org = lambda: sa.Column("organization_id", uuid, sa.ForeignKey("foundation_organizations.id"), nullable=False)  # noqa: E731
    user = lambda name, nullable=True: sa.Column(name, uuid, sa.ForeignKey("foundation_users.id"), nullable=nullable)  # noqa: E731

    op.add_column("shipping_settings", sa.Column("return_prefix", sa.String(20), nullable=False, server_default="RT-"))
    op.add_column("shipping_settings", sa.Column("return_window_days", sa.Integer(), nullable=False, server_default="30"))
    op.add_column("shipping_settings", sa.Column("weight_tolerance_pct", sa.Numeric(5, 2), nullable=False, server_default="1.00"))
    op.create_table("shipping_return_counters", org(), sa.Column("year", sa.Integer(), nullable=False),
                    sa.Column("value", sa.Integer(), nullable=False, server_default="0"), sa.PrimaryKeyConstraint("organization_id", "year"))

    op.add_column("shipping_shipments", sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("shipping_shipments", sa.Column("gate_weight_kg", qty))
    op.add_column("shipping_shipments", sa.Column("received_weight_kg", qty))
    op.add_column("shipping_shipments", sa.Column("failed_at", dt))
    op.add_column("shipping_shipments", sa.Column("close_reason", sa.Text()))
    op.drop_constraint("ck_shipping_shipments_status", "shipping_shipments", type_="check")
    op.create_check_constraint("ck_shipping_shipments_status", "shipping_shipments", f"status IN {NEW_STATUSES}")

    op.add_column("shipping_shipment_lines", sa.Column("production_order_id", uuid))
    op.add_column("shipping_shipment_lines", sa.Column("production_order_no", sa.String(64)))
    op.add_column("shipping_shipment_lines", sa.Column("delivered_quantity", qty))
    op.create_index("ix_shipping_shipment_lines_production_order_id", "shipping_shipment_lines", ["production_order_id"])
    op.execute("UPDATE shipping_shipment_lines SET delivered_quantity = quantity WHERE shipment_id IN "
               "(SELECT id FROM shipping_shipments WHERE status = 'delivered')")

    op.create_table("shipping_returns", sa.Column("id", uuid, primary_key=True), org(),
                    sa.Column("return_no", sa.String(40), nullable=False), sa.Column("kind", sa.String(12), nullable=False),
                    sa.Column("status", sa.String(12), nullable=False),
                    sa.Column("shipment_id", uuid, sa.ForeignKey("shipping_shipments.id"), nullable=False),
                    sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"), sa.Column("customer_id", uuid),
                    sa.Column("customer_name", sa.String(255), nullable=False), sa.Column("reason", sa.String(32), nullable=False),
                    sa.Column("responsibility", sa.String(16), nullable=False), sa.Column("details", sa.Text()),
                    sa.Column("customer_reference", sa.String(80)), sa.Column("carrier_claim_ref", sa.String(80)),
                    sa.Column("requested_at", dt, nullable=False), sa.Column("is_late", sa.Boolean(), nullable=False, server_default=sa.false()),
                    sa.Column("decided_at", dt), user("decided_by_user_id"), sa.Column("decision_note", sa.Text()),
                    sa.Column("received_at", dt), user("received_by_user_id"), sa.Column("receipt_notes", sa.Text()),
                    sa.Column("cancel_reason", sa.Text()), user("created_by_user_id", False),
                    sa.Column("created_at", dt, nullable=False), sa.Column("updated_at", dt, nullable=False),
                    sa.UniqueConstraint("organization_id", "return_no", name="uq_shipping_returns_org_no"),
                    sa.CheckConstraint("kind IN ('delivery', 'customer')", name="ck_shipping_returns_kind"),
                    sa.CheckConstraint("status IN ('requested', 'approved', 'rejected', 'received', 'cancelled')", name="ck_shipping_returns_status"),
                    sa.CheckConstraint("responsibility IN ('factory', 'carrier', 'customer', 'undetermined')", name="ck_shipping_returns_responsibility"))
    op.create_index("ix_shipping_returns_organization_id", "shipping_returns", ["organization_id"])
    op.create_index("ix_shipping_returns_shipment_id", "shipping_returns", ["shipment_id"])
    op.create_index("ix_shipping_returns_customer_id", "shipping_returns", ["customer_id"])
    op.create_index("ix_shipping_returns_org_status", "shipping_returns", ["organization_id", "status"])
    op.create_table("shipping_return_lines", sa.Column("id", uuid, primary_key=True),
                    sa.Column("return_id", uuid, sa.ForeignKey("shipping_returns.id", ondelete="CASCADE"), nullable=False),
                    sa.Column("shipment_line_id", uuid, sa.ForeignKey("shipping_shipment_lines.id"), nullable=False),
                    sa.Column("line_no", sa.Integer(), nullable=False), sa.Column("description", sa.String(255), nullable=False),
                    sa.Column("width_mm", sa.Numeric(10, 3)), sa.Column("thickness_mm", sa.Numeric(10, 3)),
                    sa.Column("unit", sa.String(32), nullable=False), sa.Column("weight_unit", sa.String(8), nullable=False, server_default="kg"),
                    sa.Column("production_order_no", sa.String(64)), sa.Column("quantity", qty, nullable=False), sa.Column("weight", qty),
                    sa.Column("received_quantity", qty), sa.Column("received_weight", qty),
                    sa.UniqueConstraint("return_id", "line_no", name="uq_shipping_return_lines_no"),
                    sa.CheckConstraint("quantity > 0", name="ck_shipping_return_lines_quantity"))
    op.create_index("ix_shipping_return_lines_return_id", "shipping_return_lines", ["return_id"])
    op.create_index("ix_shipping_return_lines_shipment_line_id", "shipping_return_lines", ["shipment_line_id"])
    op.create_table("shipping_attachments", sa.Column("id", uuid, primary_key=True), org(),
                    sa.Column("shipment_id", uuid, sa.ForeignKey("shipping_shipments.id"), nullable=False),
                    sa.Column("return_id", uuid, sa.ForeignKey("shipping_returns.id")), sa.Column("kind", sa.String(24), nullable=False),
                    sa.Column("file_name", sa.String(255), nullable=False), sa.Column("content_type", sa.String(80), nullable=False),
                    sa.Column("size_bytes", sa.Integer(), nullable=False), sa.Column("storage_path", sa.String(500), nullable=False),
                    user("uploaded_by_user_id", False), sa.Column("uploaded_at", dt, nullable=False))
    op.create_index("ix_shipping_attachments_owner", "shipping_attachments", ["organization_id", "shipment_id", "return_id"])
    op.add_column("shipping_shipment_events", sa.Column("return_id", uuid, sa.ForeignKey("shipping_returns.id", ondelete="CASCADE",
                                                                                         name="fk_shipping_events_return")))

    for code, (_old, new) in RENAMED.items():
        bind.execute(sa.text("UPDATE foundation_permissions SET name=:name, description=:description WHERE code=:code"), dict(name=new, description=new, code=code))
    op.create_table(BACKUP, sa.Column("id", uuid, primary_key=True), sa.Column("role_id", uuid, nullable=False),
                    sa.Column("permission_id", uuid, nullable=False))
    backup = sa.table(BACKUP, sa.column("id"), sa.column("role_id"), sa.column("permission_id"))
    for organization in bind.scalars(sa.text("SELECT id FROM foundation_organizations")).all():
        for code, name in NAMES.items():
            _module, resource, action = code.split(":")
            bind.execute(sa.text("INSERT INTO foundation_permissions (id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) "
                                 "VALUES (:id,:org,:code,:name,:description,'shipping',:resource,:action,now(),now()) ON CONFLICT (organization_id,code) DO NOTHING"),
                         dict(id=uuid4(), org=organization, code=code, name=name, description=name, resource=resource, action=action))
        ids = dict(bind.execute(sa.text("SELECT code, id FROM foundation_permissions WHERE organization_id=:org AND module_name='shipping'"),
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
    if bind.scalar(sa.text("SELECT count(*) FROM shipping_returns")) or bind.scalar(sa.text(
            "SELECT count(*) FROM shipping_shipments WHERE status IN ('partially_delivered', 'returned', 'not_delivered') OR attempt > 1")):
        raise RuntimeError("Returns or returned shipments exist; they are records and are not dropped by a downgrade.")
    if bind.scalar(sa.text("SELECT count(*) FROM shipping_attachments")):
        raise RuntimeError("Shipping attachments exist; remove them in the application first.")
    bind.execute(sa.text(f"DELETE FROM foundation_role_permissions WHERE id IN (SELECT id FROM {BACKUP})"))
    op.drop_table(BACKUP)
    codes = sa.bindparam("codes", expanding=True)
    bind.execute(sa.text("DELETE FROM foundation_role_permissions WHERE permission_id IN (SELECT id FROM foundation_permissions WHERE code IN :codes)").bindparams(codes),
                 dict(codes=list(RETURNS)))
    bind.execute(sa.text("DELETE FROM foundation_permissions WHERE code IN :codes").bindparams(codes), dict(codes=list(RETURNS)))
    for code, (old, _new) in RENAMED.items():
        bind.execute(sa.text("UPDATE foundation_permissions SET name=:name, description=:description WHERE code=:code"), dict(name=old, description=old, code=code))
    op.drop_constraint("fk_shipping_events_return", "shipping_shipment_events", type_="foreignkey")
    op.drop_column("shipping_shipment_events", "return_id")
    for table in ("shipping_attachments", "shipping_return_lines", "shipping_returns", "shipping_return_counters"):
        op.drop_table(table)
    op.drop_index("ix_shipping_shipment_lines_production_order_id", "shipping_shipment_lines")
    for column in ("delivered_quantity", "production_order_no", "production_order_id"):
        op.drop_column("shipping_shipment_lines", column)
    op.drop_constraint("ck_shipping_shipments_status", "shipping_shipments", type_="check")
    op.create_check_constraint("ck_shipping_shipments_status", "shipping_shipments", f"status IN {OLD_STATUSES}")
    for column in ("close_reason", "failed_at", "received_weight_kg", "gate_weight_kg", "attempt"):
        op.drop_column("shipping_shipments", column)
    for column in ("weight_tolerance_pct", "return_window_days", "return_prefix"):
        op.drop_column("shipping_settings", column)
