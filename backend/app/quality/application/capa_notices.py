"""Corrective-action notices (QUAL-CAPA-001): an email when an action is assigned to someone, and a daily digest of what
is late or due soon. Best effort: a message that cannot be sent never undoes the work it is about.

Recipients and their language are read from the shared users table (ADR-004); links point to the frontend.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import timedelta
from html import escape

from sqlalchemy import or_, select

from app.core.config import get_settings
from app.core.email.service import EmailService
from app.quality.domain import ncr as N
from app.quality.infrastructure.models import NCRAction, NonConformanceReport
from .support import _t

logger = logging.getLogger(__name__)

TEXT = {
    "ar": dict(assigned="إجراء تصحيحي مُسند إليك", hello="مرحبًا {name}،", assigned_line="أُسند إليك إجراء في تقرير عدم المطابقة {number}: {title}.",
               due="الموعد: {date}", no_due="بلا موعد محدد", open="فتح التقرير", digest="متابعة الإجراءات التصحيحية",
               digest_line="هذه الأمور تحتاج متابعتك:", overdue="إجراء متأخر", due_soon="إجراء يحل موعده قريبًا", report_overdue="تقرير متأخر",
               review_due="مراجعة فعالية مستحقة", open_list="فتح الإجراءات التصحيحية", kinds=dict(correction="تصحيح فوري", corrective="إجراء تصحيحي", preventive="إجراء وقائي")),
    "en": dict(assigned="A corrective action assigned to you", hello="Hello {name},",
               assigned_line="An action of non-conformance report {number} was assigned to you: {title}.", due="Due: {date}", no_due="No due date",
               open="Open the report", digest="Corrective actions to follow up", digest_line="These need your follow-up:", overdue="Overdue action",
               due_soon="Action due soon", report_overdue="Overdue report", review_due="Effectiveness review due", open_list="Open corrective actions",
               kinds=dict(correction="Correction", corrective="Corrective action", preventive="Preventive action")),
}


def contacts(db, organization_id, user_ids) -> dict:
    """{user_id: (name, email, language)} of active users, in their language or the organization's."""
    ids = [i for i in set(user_ids) if i]
    if not ids:
        return {}
    users, orgs = _t("foundation_users"), _t("foundation_organizations")
    default = db.scalar(select(orgs.c.default_locale).where(orgs.c.id == organization_id)) or "ar"
    rows = db.execute(select(users.c.id, users.c.full_name, users.c.email, users.c.preferred_locale).where(
        users.c.organization_id == organization_id, users.c.id.in_(ids), users.c.status == "active")).all()
    return {r.id: (r.full_name, r.email, r.preferred_locale if r.preferred_locale in TEXT else (default if default in TEXT else "ar")) for r in rows}


def _link(report_id) -> str:
    return f"{get_settings().frontend_url.rstrip('/')}/non-conformance-reports/{report_id}"


def _page(lang, title, paragraphs, link, label) -> str:
    body = "".join(f"<p>{p}</p>" for p in paragraphs)
    return (f'<div dir="{"rtl" if lang == "ar" else "ltr"}" style="font-family:Segoe UI,Tahoma,sans-serif;max-width:640px;margin:auto;padding:20px">'
            f'<h2>{escape(title)}</h2>{body}<p><a href="{escape(link, quote=True)}" style="background:#2563eb;color:white;padding:10px 24px;'
            f'text-decoration:none;border-radius:8px">{escape(label)}</a></p></div>')


def action_assigned(db, organization_id, action: NCRAction, report: NonConformanceReport, email: EmailService | None = None) -> bool:
    found = contacts(db, organization_id, [action.owner_user_id]).get(action.owner_user_id)
    if not found:
        return False
    name, address, lang = found
    t = TEXT[lang]
    due = t["due"].format(date=action.due_date.isoformat()) if action.due_date else t["no_due"]
    lines = [t["hello"].format(name=name), t["assigned_line"].format(number=report.report_number, title=report.title),
             f'{t["kinds"].get(action.kind, action.kind)}: {action.description}', due]
    html = _page(lang, t["assigned"], [escape(line) for line in lines], _link(report.id), t["open"])
    text = "\n\n".join([*lines, _link(report.id)])
    return (email or EmailService()).send_email(address, f'{t["assigned"]} — {report.report_number}', html, text)


def follow_ups(db, organization_id, today) -> dict:
    """{user_id: [(kind, report, detail)]}: open actions late or due soon (their owners), reports past their due date (their
    owners), and effectiveness reviews that are due (whoever verified the report)."""
    out = defaultdict(list)
    rows = db.execute(select(NCRAction, NonConformanceReport).join(NonConformanceReport, NonConformanceReport.id == NCRAction.ncr_id).where(
        NCRAction.organization_id == organization_id, NCRAction.status == N.ACTION_OPEN, NCRAction.owner_user_id.is_not(None),
        NonConformanceReport.status.notin_(N.FINAL), NCRAction.due_date.is_not(None),
        NCRAction.due_date <= today + timedelta(days=N.DUE_SOON_DAYS)).order_by(NCRAction.due_date)).all()
    for action, report in rows:
        out[action.owner_user_id].append(("overdue" if N.is_overdue(action, today) else "due_soon", report, action))
    for report in db.scalars(select(NonConformanceReport).where(
            NonConformanceReport.organization_id == organization_id, NonConformanceReport.owner_user_id.is_not(None),
            NonConformanceReport.status.notin_(N.FINAL), NonConformanceReport.due_date < today)):
        out[report.owner_user_id].append(("report_overdue", report, None))
    for report in db.scalars(select(NonConformanceReport).where(
            NonConformanceReport.organization_id == organization_id, NonConformanceReport.status == N.CLOSED,
            NonConformanceReport.effectiveness_result.is_(None), NonConformanceReport.effectiveness_due_date <= today,
            or_(NonConformanceReport.verified_by_user_id.is_not(None), NonConformanceReport.owner_user_id.is_not(None)))):
        out[report.verified_by_user_id or report.owner_user_id].append(("review_due", report, None))
    return out


def send_digests(db, organization_id, today, email: EmailService | None = None) -> int:
    """One message per person with something to follow up; returns how many were sent."""
    pending = follow_ups(db, organization_id, today)
    people = contacts(db, organization_id, list(pending))
    email, sent = email or EmailService(), 0
    for user_id, entries in pending.items():
        if user_id not in people:
            continue
        name, address, lang = people[user_id]
        t = TEXT[lang]
        lines = []
        for kind, report, action in entries:
            what = action.description if action else report.title
            when = (action.due_date if action else report.effectiveness_due_date if kind == "review_due" else report.due_date)
            lines.append(f'{t[kind]} · {report.report_number} · {what}' + (f' · {when.isoformat()}' if when else ''))
        html = _page(lang, t["digest"], [escape(t["hello"].format(name=name)), escape(t["digest_line"]),
                                         "<br>".join(escape(line) for line in lines)], f"{get_settings().frontend_url.rstrip('/')}/corrective-actions", t["open_list"])
        text = "\n".join([t["hello"].format(name=name), t["digest_line"], *lines])
        try:
            sent += bool(email.send_email(address, t["digest"], html, text))
        except Exception:  # noqa: BLE001 - a failed message never stops the others
            logger.exception("Corrective-action digest not sent")
    return sent
