"""What shipping tells people (PROJECT-NOTIFY-001), through core/interfaces/notifications; added to the session of the
change it reports. Words: notifications.events.<event> in the screens."""
from app.core.interfaces.notifications import IMPORTANT, WORK, Audience, Notice, notify, settle
from app.shipping.domain import permissions as P


def _return(event, ret, severity="info"):
    return Notice(event, WORK, dict(number=ret.return_no, customer=ret.customer_name), f"/shipment-returns/{ret.id}", severity,
                  "shipment_return", ret.id)


def return_awaits_approval(db, tenant, ret):
    notify(db, tenant.organization_id, Audience.holders(P.RETURNS_APPROVE), _return("shipping.return.awaiting_approval", ret, IMPORTANT), tenant.user_id)


def return_approved(db, tenant, ret):
    """Approved: the warehouse expects the goods back; who registered it is told."""
    settle(db, tenant.organization_id, "shipment_return", ret.id)
    notify(db, tenant.organization_id, Audience.holders(P.RETURNS_RECEIVE), _return("shipping.return.awaiting_receipt", ret), tenant.user_id)
    notify(db, tenant.organization_id, Audience.to(ret.created_by_user_id), _return("shipping.return.approved", ret), tenant.user_id)


def return_rejected(db, tenant, ret):
    settle(db, tenant.organization_id, "shipment_return", ret.id)
    notify(db, tenant.organization_id, Audience.to(ret.created_by_user_id), _return("shipping.return.rejected", ret, IMPORTANT), tenant.user_id)


def return_closed(db, tenant, ret):
    """Received or cancelled: nothing about it waits any more."""
    settle(db, tenant.organization_id, "shipment_return", ret.id)
