"""What quality tells people in the system (PROJECT-NOTIFY-001), through core/interfaces/notifications; added to the
session of the change it reports. (capa_notices.py sends the e-mails.) Words: notifications.events.<event> in the screens."""
from app.core.interfaces.notifications import IMPORTANT, URGENT, WORK, Audience, Notice, notify, settle
from app.quality.domain import permissions as Q


def _report(event, report, severity="info", **params):
    severity = URGENT if report.severity == "critical" and severity != "info" else severity
    return Notice(event, WORK, dict(number=report.report_number, title=report.title, **params), f"/non-conformance-reports/{report.id}",
                  severity, "ncr", report.id)


def report_owner(db, tenant, report):
    notify(db, tenant.organization_id, Audience.to(report.owner_user_id), _report("quality.ncr.assigned", report, IMPORTANT), tenant.user_id)


def report_awaits_verification(db, tenant, report):
    notify(db, tenant.organization_id, Audience.holders(Q.NCR_VERIFY), _report("quality.ncr.awaiting_verification", report, IMPORTANT), tenant.user_id)


def report_verified(db, tenant, report, effective):
    settle(db, tenant.organization_id, "ncr", report.id, ("quality.ncr.awaiting_verification",))
    event = "quality.ncr.closed" if effective else "quality.ncr.not_effective"
    notify(db, tenant.organization_id, Audience.to(report.owner_user_id, report.detected_by_user_id),
           _report(event, report, "info" if effective else IMPORTANT), tenant.user_id)


def report_cancelled(db, tenant, report):
    settle(db, tenant.organization_id, "ncr", report.id)


def action_assigned(db, tenant, action, report):
    notify(db, tenant.organization_id, Audience.to(action.owner_user_id),
           Notice("quality.ncr_action.assigned", WORK, dict(number=report.report_number, action=action.description, due=action.due_date),
                  f"/non-conformance-reports/{report.id}", IMPORTANT, "ncr_action", action.id), tenant.user_id)


def action_finished(db, tenant, action):
    settle(db, tenant.organization_id, "ncr_action", action.id)


def _rejection(event, rejection, severity="info"):
    return Notice(event, WORK, dict(number=rejection.rejection_code, quantity=rejection.quantity_rejected, unit=rejection.unit),
                  f"/quality-rejections/{rejection.id}", severity, "quality_rejection", rejection.id)


def rejection_awaits_decision(db, tenant, rejection):
    notify(db, tenant.organization_id, Audience.holders(Q.REJECTIONS_DECIDE), _rejection("quality.rejection.awaiting_decision", rejection, IMPORTANT),
           tenant.user_id)


def rejection_decided(db, tenant, rejection):
    settle(db, tenant.organization_id, "quality_rejection", rejection.id)
    notify(db, tenant.organization_id, Audience.holders(Q.REJECTIONS_EXECUTE), _rejection("quality.rejection.awaiting_execution", rejection),
           tenant.user_id)


def rejection_executed(db, tenant, rejection):
    settle(db, tenant.organization_id, "quality_rejection", rejection.id)
