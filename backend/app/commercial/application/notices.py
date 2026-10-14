"""What the commercial module tells people (PROJECT-NOTIFY-001), through core/interfaces/notifications; added to the
session of the change it reports. Words: notifications.events.<event> in the screens."""
from app.core.interfaces.notifications import IMPORTANT, URGENT, WORK, Audience, Notice, notify, settle
from app.commercial.domain.complaints import PREFIX


def _complaint(event, row, severity="info", **params):
    severity = URGENT if row.priority == "critical" and severity != "info" else severity
    return Notice(event, WORK, dict(number=row.number, **params), f"/complaints/{row.id}", severity, "complaint", row.id)


def complaint_assigned(db, tenant, row):
    notify(db, tenant.organization_id, Audience.to(row.owner_user_id), _complaint("commercial.complaint.assigned", row, IMPORTANT, due=row.due_date),
           tenant.user_id)


def complaint_close_requested(db, tenant, row):
    notify(db, tenant.organization_id, Audience.holders(PREFIX + "close"), _complaint("commercial.complaint.close_requested", row, IMPORTANT),
           tenant.user_id)


def complaint_closed(db, tenant, row):
    settle(db, tenant.organization_id, "complaint", row.id)
    notify(db, tenant.organization_id, Audience.to(row.owner_user_id, row.closure_requested_by), _complaint("commercial.complaint.closed", row),
           tenant.user_id)


def complaint_reopened(db, tenant, row):
    notify(db, tenant.organization_id, Audience.to(row.owner_user_id), _complaint("commercial.complaint.reopened", row, IMPORTANT), tenant.user_id)


def complaint_returned(db, tenant, row):
    """Closure refused: back to processing; the closing approvers have nothing left to do."""
    settle(db, tenant.organization_id, "complaint", row.id, ("commercial.complaint.close_requested",))
    notify(db, tenant.organization_id, Audience.to(row.owner_user_id, row.closure_requested_by),
           _complaint("commercial.complaint.returned", row, IMPORTANT), tenant.user_id)


def complaint_cancelled(db, tenant, row):
    settle(db, tenant.organization_id, "complaint", row.id)


def follow_up_assigned(db, tenant, follow_up):
    priority = str(getattr(follow_up.priority, "value", follow_up.priority))
    notify(db, tenant.organization_id, Audience.to(follow_up.assigned_user_id),
           Notice("commercial.follow_up.assigned", WORK, dict(reason=follow_up.reason, due=follow_up.due_date), "/follow-ups",
                  IMPORTANT if priority in ("high", "urgent") else "info", "follow_up", follow_up.id), tenant.user_id)
