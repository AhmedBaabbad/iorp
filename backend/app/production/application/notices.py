"""What production tells people (PROJECT-NOTIFY-001), through core/interfaces/notifications; added to the session of
the change it reports. Words: notifications.events.<event> in the screens."""
from app.core.interfaces.notifications import IMPORTANT, URGENT, WORK, Audience, Notice, notify, settle
from app.production.domain import permissions as P


def _order(event, order, severity="info"):
    priority = str(getattr(order.priority, "value", order.priority))
    severity = URGENT if priority == "urgent" and severity != "info" else severity
    return Notice(event, WORK, dict(number=order.production_order_number, start=order.planned_start_date),
                  f"/production-orders/{order.id}", severity, "production_order", order.id)


def order_awaits_release(db, tenant, order):
    notify(db, tenant.organization_id, Audience.holders(P.ORDERS_RELEASE), _order("production.order.awaiting_release", order, IMPORTANT),
           tenant.user_id)


def order_status_changed(db, tenant, order, action_name, actor_user_id):
    """Released or cancelled: no longer waits for release; completed: waits for closing; closed: nothing waits."""
    if action_name in ("release", "cancel", "close"):
        settle(db, tenant.organization_id, "production_order", order.id)
    if action_name == "complete":
        notify(db, tenant.organization_id, Audience.holders(P.ORDERS_CLOSE), _order("production.order.awaiting_close", order), actor_user_id)
