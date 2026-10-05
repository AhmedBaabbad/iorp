"""Shipping and delivery notes (SHIP-001): a new module.

- shipping_settings (note prefix), shipping_code_counters (DN-YYYY-NNNN per year), shipping_shipments,
  shipping_shipment_lines and shipping_shipment_events (history and the outbox a future notification workflow reads).
- Permissions shipping:shipments:{read,create,update,dispatch,deliver,cancel} and shipping:settings:update, granted as
  the system roles define them: organization admin and shipping manager all; warehouse manager read, create, update and
  dispatch; factory manager, commercial manager and viewer read. Grants added here are recorded so the downgrade removes
  exactly them.
No existing data changes.
"""
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "f6a1b2j1"
down_revision = "f6a1b2j0"
branch_labels = None
depends_on = None

BACKUP = "shipping_j1_added_grants"
NAMES = {
    "shipping:shipments:read": "Read Shipments", "shipping:shipments:create": "Create Shipments",
    "shipping:shipments:update": "Update Shipments", "shipping:shipments:dispatch": "Dispatch Shipments",
    "shipping:shipments:deliver": "Confirm Shipment Delivery", "shipping:shipments:cancel": "Cancel Shipments",
    "shipping:settings:update": "Update Shipping Settings",
}
ALL = tuple(NAMES)
READ = ("shipping:shipments:read",)
ROLES = {
    "organization_admin": ALL, "shipping_manager": ALL,
    "warehouse_manager": ("shipping:shipments:read", "shipping:shipments:create", "shipping:shipments:update", "shipping:shipments:dispatch"),
    "factory_manager": READ, "commercial_manager": READ, "viewer": READ,
}


def upgrade():
    bind = op.get_bind()
    uuid, dt, qty = sa.Uuid(), sa.DateTime(timezone=True), sa.Numeric(14, 3)
    org = lambda: sa.Column("organization_id", uuid, sa.ForeignKey("foundation_organizations.id"), nullable=False)  # noqa: E731
    user = lambda name, nullable=True: sa.Column(name, uuid, sa.ForeignKey("foundation_users.id"), nullable=nullable)  # noqa: E731
    op.create_table("shipping_settings",
                    sa.Column("organization_id", uuid, sa.ForeignKey("foundation_organizations.id"), primary_key=True),
                    sa.Column("note_prefix", sa.String(20), nullable=False, server_default="DN-"),
                    sa.Column("updated_at", dt, nullable=False, server_default=sa.func.now()))
    op.create_table("shipping_code_counters",
                    sa.Column("organization_id", uuid, sa.ForeignKey("foundation_organizations.id"), primary_key=True),
                    sa.Column("year", sa.Integer(), primary_key=True), sa.Column("value", sa.Integer(), nullable=False, server_default="0"))
    op.create_table("shipping_shipments",
                    sa.Column("id", uuid, primary_key=True), org(),
                    sa.Column("shipment_no", sa.String(40), nullable=False), sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
                    sa.Column("delivery_method", sa.String(20), nullable=False), sa.Column("shipment_date", sa.Date(), nullable=False),
                    sa.Column("customer_id", uuid), sa.Column("customer_name", sa.String(255), nullable=False),
                    sa.Column("customer_reference", sa.String(80)), sa.Column("consignee_name", sa.String(255)),
                    sa.Column("consignee_phone", sa.String(20)), sa.Column("consignee_email", sa.String(255)),
                    sa.Column("notify_consignee", sa.Boolean(), nullable=False, server_default=sa.false()),
                    sa.Column("delivery_address", sa.Text()), sa.Column("delivery_city", sa.String(120)), sa.Column("location_url", sa.String(500)),
                    sa.Column("driver_name", sa.String(200)), sa.Column("driver_phone", sa.String(20)), sa.Column("driver_id_no", sa.String(40)),
                    sa.Column("vehicle_plate", sa.String(40)), sa.Column("vehicle_type", sa.String(80)),
                    sa.Column("carrier_name", sa.String(200)), sa.Column("tracking_no", sa.String(80)), sa.Column("notes", sa.Text()),
                    sa.Column("ready_at", dt), sa.Column("dispatched_at", dt), user("dispatched_by_user_id"),
                    sa.Column("delivered_at", dt), sa.Column("received_by_name", sa.String(200)), sa.Column("delivery_notes", sa.Text()),
                    user("delivered_recorded_by_user_id"), sa.Column("cancel_reason", sa.Text()), user("created_by_user_id", False),
                    sa.Column("created_at", dt, nullable=False, server_default=sa.func.now()),
                    sa.Column("updated_at", dt, nullable=False, server_default=sa.func.now()),
                    sa.UniqueConstraint("organization_id", "shipment_no", name="uq_shipping_shipments_org_no"),
                    sa.CheckConstraint("status IN ('draft', 'ready', 'dispatched', 'delivered', 'cancelled')", name="ck_shipping_shipments_status"),
                    sa.CheckConstraint("delivery_method IN ('pickup', 'factory_delivery', 'carrier')", name="ck_shipping_shipments_method"))
    op.create_index("ix_shipping_shipments_organization_id", "shipping_shipments", ["organization_id"])
    op.create_index("ix_shipping_shipments_customer_id", "shipping_shipments", ["customer_id"])
    op.create_index("ix_shipping_shipments_shipment_date", "shipping_shipments", ["shipment_date"])
    op.create_index("ix_shipping_shipments_org_status", "shipping_shipments", ["organization_id", "status"])
    op.create_table("shipping_shipment_lines",
                    sa.Column("id", uuid, primary_key=True),
                    sa.Column("shipment_id", uuid, sa.ForeignKey("shipping_shipments.id", ondelete="CASCADE"), nullable=False, index=True),
                    sa.Column("line_no", sa.Integer(), nullable=False), sa.Column("description", sa.String(255), nullable=False),
                    sa.Column("specification", sa.String(500)), sa.Column("quantity", qty, nullable=False), sa.Column("unit", sa.String(32), nullable=False),
                    sa.Column("package_count", sa.Integer()), sa.Column("package_type", sa.String(40)),
                    sa.Column("net_weight_kg", qty), sa.Column("gross_weight_kg", qty), sa.Column("batch_no", sa.String(80)), sa.Column("notes", sa.String(500)),
                    sa.UniqueConstraint("shipment_id", "line_no", name="uq_shipping_shipment_lines_no"),
                    sa.CheckConstraint("quantity > 0", name="ck_shipping_lines_quantity"))
    op.create_table("shipping_shipment_events",
                    sa.Column("id", uuid, primary_key=True), org(),
                    sa.Column("shipment_id", uuid, sa.ForeignKey("shipping_shipments.id", ondelete="CASCADE"), nullable=False),
                    sa.Column("event_type", sa.String(40), nullable=False), sa.Column("from_status", sa.String(16)),
                    sa.Column("to_status", sa.String(16), nullable=False), sa.Column("reason", sa.Text()), sa.Column("payload", sa.JSON()),
                    sa.Column("actor_user_id", uuid, sa.ForeignKey("foundation_users.id", ondelete="SET NULL")),
                    sa.Column("occurred_at", dt, nullable=False, server_default=sa.func.now()), sa.Column("processed_at", dt))
    op.create_index("ix_shipping_events_shipment", "shipping_shipment_events", ["organization_id", "shipment_id"])
    op.create_index("ix_shipping_events_unprocessed", "shipping_shipment_events", ["organization_id", "processed_at"])

    op.create_table(BACKUP, sa.Column("id", uuid, primary_key=True), sa.Column("role_id", uuid, nullable=False),
                    sa.Column("permission_id", uuid, nullable=False))
    backup = sa.table(BACKUP, sa.column("id"), sa.column("role_id"), sa.column("permission_id"))
    for organization in bind.scalars(sa.text("SELECT id FROM foundation_organizations")).all():
        ids = {}
        for code, name in NAMES.items():
            _module, resource, action = code.split(":")
            bind.execute(sa.text("INSERT INTO foundation_permissions (id,organization_id,code,name,description,module_name,resource_name,action_name,created_at,updated_at) "
                                 "VALUES (:id,:org,:code,:name,:description,'shipping',:resource,:action,now(),now()) ON CONFLICT (organization_id,code) DO NOTHING"),
                         dict(id=uuid4(), org=organization, code=code, name=name, description=name, resource=resource, action=action))
            ids[code] = bind.scalar(sa.text("SELECT id FROM foundation_permissions WHERE organization_id=:org AND code=:code"), dict(org=organization, code=code))
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
    if bind.scalar(sa.text("SELECT count(*) FROM shipping_shipments")):
        raise RuntimeError("Shipments exist; delivery notes are records and are not dropped by a downgrade.")
    bind.execute(sa.text(f"DELETE FROM foundation_role_permissions WHERE id IN (SELECT id FROM {BACKUP})"))
    op.drop_table(BACKUP)
    codes = sa.bindparam("codes", expanding=True)
    bind.execute(sa.text("DELETE FROM foundation_role_permissions WHERE permission_id IN (SELECT id FROM foundation_permissions WHERE code IN :codes)").bindparams(codes),
                 dict(codes=list(ALL)))
    bind.execute(sa.text("DELETE FROM foundation_permissions WHERE code IN :codes").bindparams(codes), dict(codes=list(ALL)))
    for table in ("shipping_shipment_events", "shipping_shipment_lines", "shipping_shipments", "shipping_code_counters", "shipping_settings"):
        op.drop_table(table)
