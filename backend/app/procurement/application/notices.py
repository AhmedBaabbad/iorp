"""What procurement tells people (PROJECT-NOTIFY-001), through core/interfaces/notifications; added to the session of
the change it reports. Words: notifications.events.<event> in the screens."""
from app.core.interfaces.notifications import IMPORTANT, WORK, Audience, Notice, notify, settle
from app.procurement.domain import permissions as P


def _order(event, order, severity="info"):
    return Notice(event, WORK, dict(number=order.po_number, supplier=order.supplier_name), f"/purchase-orders/{order.id}", severity,
                  "purchase_order", order.id)


def order_awaits_approval(db, tenant, order):
    """A new order waits for an approver other than its preparer."""
    notify(db, tenant.organization_id, Audience.holders(P.PO_APPROVE), _order("procurement.purchase_order.awaiting_approval", order, IMPORTANT),
           tenant.user_id)


def order_approved(db, tenant, order):
    settle(db, tenant.organization_id, "purchase_order", order.id)
    notify(db, tenant.organization_id, Audience.to(order.created_by_user_id), _order("procurement.purchase_order.approved", order), tenant.user_id)


def order_cancelled(db, tenant, order):
    settle(db, tenant.organization_id, "purchase_order", order.id)
    notify(db, tenant.organization_id, Audience.to(order.created_by_user_id), _order("procurement.purchase_order.cancelled", order), tenant.user_id)


def _supplier(event, supplier, severity="info", **params):
    return Notice(event, WORK, dict(name=supplier.name, code=supplier.supplier_code, **params), f"/suppliers/{supplier.id}", severity,
                  "supplier", supplier.id)


def supplier_awaits_approval(db, tenant, supplier):
    notify(db, tenant.organization_id, Audience.holders(P.SUPPLIERS_APPROVE), _supplier("procurement.supplier.awaiting_approval", supplier, IMPORTANT),
           tenant.user_id)


def supplier_status_changed(db, tenant, supplier):
    settle(db, tenant.organization_id, "supplier", supplier.id, ("procurement.supplier.awaiting_approval",))
    notify(db, tenant.organization_id, Audience.to(supplier.created_by_user_id),
           _supplier("procurement.supplier.status_changed", supplier, status=supplier.status), tenant.user_id)
