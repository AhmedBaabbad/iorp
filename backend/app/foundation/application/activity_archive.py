"""The activity log's retention (ORG-AUDIT-003): a month is kept RETENTION_MONTHS after it ends; then it can be downloaded
as an archive file (built on request, never stored) and, once its download is confirmed, deleted. Whoever may archive is
told when a month is due, reminded REMIND_DAYS before, and the month is deleted automatically GRACE_DAYS after it is due
if nobody did. Every download and deletion goes to the audit trail. The audit trail itself is never archived nor deleted.
"""
import csv
import io
import zipfile
from datetime import date, datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import delete, func, select

from app.core.interfaces.notifications import IMPORTANT, URGENT, Audience, Notice, notify
from app.core.utils import utc_now
from app.foundation.application.audit import log_tenant_audit
from app.foundation.domain.log_words import describe, detail_text
from app.foundation.infrastructure.models import ActivityArchive, TenantActivityLog as Activity, User

ARCHIVE = "foundation:activity_log:archive"
RETENTION_MONTHS, GRACE_DAYS, REMIND_DAYS = 12, 30, 7
ARCHIVED, PURGED = "activity_log.archived", "activity_log.purged"
LINK = "/admin/activity-log?archive=1"


class ArchiveError(ValueError):
    def __init__(self, code: str, status_code: int = 400):
        super().__init__(code)
        self.code, self.status_code = code, status_code


def _bounds(month: str) -> tuple[datetime, datetime]:
    try:
        year, number = (int(x) for x in month.split("-"))
        start = datetime(year, number, 1, tzinfo=timezone.utc)
    except ValueError as exc:
        raise ArchiveError("MONTH_INVALID") from exc
    end = datetime(year + (number == 12), 1 if number == 12 else number + 1, 1, tzinfo=timezone.utc)
    return start, end


def due_on(month: str) -> date:
    """The day the month may be archived: RETENTION_MONTHS after it ends."""
    _, end = _bounds(month)
    return date(end.year + (end.month + RETENTION_MONTHS - 1) // 12, (end.month + RETENTION_MONTHS - 1) % 12 + 1, 1)


def delete_on(month: str) -> date:
    return due_on(month) + timedelta(days=GRACE_DAYS)


def _cutoff(now: datetime) -> datetime:
    """Entries before this are in months past their retention."""
    first = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    months = first.year * 12 + first.month - 1 - RETENTION_MONTHS
    return datetime(months // 12, months % 12 + 1, 1, tzinfo=timezone.utc)


def _months(db, organization_id, now) -> dict[str, int]:
    """{YYYY-MM: rows} of the months past their retention that still hold entries (counted by the database)."""
    year, month = func.extract("year", Activity.created_at), func.extract("month", Activity.created_at)
    rows = db.execute(select(year, month, func.count()).where(Activity.organization_id == organization_id, Activity.created_at < _cutoff(now))
                      .group_by(year, month)).all()
    return {f"{int(y):04d}-{int(m):02d}": n for y, m, n in rows}


def _record(db, organization_id, month) -> ActivityArchive:
    row = db.scalar(select(ActivityArchive).where(ActivityArchive.organization_id == organization_id, ActivityArchive.month == month))
    if row is None:
        row = ActivityArchive(organization_id=organization_id, month=month)
        db.add(row)
        db.flush()
    return row


def _name(db, user_id):
    return db.scalar(select(User.full_name).where(User.id == user_id)) if user_id else None


class ActivityArchiveService:
    def __init__(self, db, tenant):
        self.db, self.tenant, self.org = db, tenant, tenant.organization_id

    def due(self, now: datetime | None = None) -> list[dict]:
        """The months that may be archived now, oldest first."""
        now = now or utc_now()
        months = _months(self.db, self.org, now)
        records = {r.month: r for r in self.db.scalars(select(ActivityArchive).where(ActivityArchive.organization_id == self.org,
                                                                                       ActivityArchive.month.in_(list(months))))} if months else {}
        return [dict(month=m, rows=n, due_on=due_on(m), delete_on=delete_on(m),
                     downloaded_at=records[m].downloaded_at if m in records else None,
                     downloaded_by_name=records[m].downloaded_by_name if m in records else None)
                for m, n in sorted(months.items())]

    def _due_month(self, month):
        start, end = _bounds(month)
        if end > _cutoff(utc_now()):
            raise ArchiveError("ARCHIVE_NOT_DUE", 409)
        return start, end

    def download(self, month: str, locale: str) -> tuple[str, bytes]:
        """The month as a compressed CSV in the reader's language, built now; the download is recorded."""
        start, end = self._due_month(month)
        entries = self.db.scalars(select(Activity).where(Activity.organization_id == self.org, Activity.created_at >= start,
                                                         Activity.created_at < end).order_by(Activity.created_at)).all()
        if not entries:
            raise ArchiveError("ARCHIVE_EMPTY", 404)
        ar = locale == "ar"
        text = io.StringIO(newline="")
        writer = csv.writer(text)
        writer.writerow(["الوقت", "العملية", "على", "بواسطة", "التفاصيل"] if ar else ["Time", "Operation", "On", "By", "Details"])
        for e in entries:
            values = [e.created_at.isoformat(), describe(e.action, e.details, locale), e.entity_name or "", e.actor_name or "",
                      detail_text(e.details, locale)]
            writer.writerow([("'" + v) if v.startswith(("=", "+", "-", "@")) else v for v in values])
        name = f"activity-{month}"
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(f"{name}.csv", "﻿" + text.getvalue())
        record = _record(self.db, self.org, month)
        record.rows, record.downloaded_at, record.downloaded_by_name = len(entries), utc_now(), _name(self.db, self.tenant.user_id)
        log_tenant_audit(self.db, self.org, ARCHIVED, "activity_log", None, self.tenant.user_id, target_display=month,
                         details=dict(month=month, rows=len(entries)))
        self.db.commit()
        return f"{name}.zip", buffer.getvalue()

    def delete(self, month: str) -> dict:
        """Deletes a month whose archive was downloaded (the person confirms they kept the file)."""
        start, end = self._due_month(month)
        record = _record(self.db, self.org, month)
        if record.downloaded_at is None:
            raise ArchiveError("ARCHIVE_NOT_DOWNLOADED", 409)
        removed = _purge(self.db, self.org, start, end)
        record.deleted_at, record.deleted_by_name = utc_now(), _name(self.db, self.tenant.user_id)
        log_tenant_audit(self.db, self.org, PURGED, "activity_log", None, self.tenant.user_id, target_display=month,
                         details=dict(month=month, rows=removed, automatic=False))
        self.db.commit()
        return dict(month=month, rows=removed)


def _purge(db, organization_id, start, end) -> int:
    return db.execute(delete(Activity).where(Activity.organization_id == organization_id, Activity.created_at >= start, Activity.created_at < end)
                      .execution_options(synchronize_session=False)).rowcount or 0


def run_daily(db, now: datetime | None = None) -> dict:
    """For every organization: tell whoever may archive that a month is due, remind them before its deletion, and delete
    the months nobody archived in time."""
    now = now or utc_now()
    today = now.date()
    told = reminded = deleted = 0
    organizations = db.scalars(select(Activity.organization_id).where(Activity.created_at < _cutoff(now)).distinct()).all()
    for org in organizations:
        for month, rows in _months(db, org, now).items():
            record = _record(db, org, month)
            record.rows = rows
            params = dict(month=month, rows=rows, delete_on=delete_on(month))
            resource = uuid5(NAMESPACE_URL, f"activity-archive/{org}/{month}")
            if delete_on(month) <= today:
                start, end = _bounds(month)
                removed = _purge(db, org, start, end)
                record.deleted_at, record.deleted_by_name = now, None
                log_tenant_audit(db, org, PURGED, "activity_log", None, None, target_display=month,
                                 details=dict(month=month, rows=removed, automatic=True))
                notify(db, org, Audience.holders(ARCHIVE), Notice("foundation.activity_archive.deleted", "work", params, LINK,
                                                                  resource_type="activity_archive", resource_id=resource))
                deleted += 1
            elif record.notified_at is None:
                notify(db, org, Audience.holders(ARCHIVE), Notice("foundation.activity_archive.ready", "work", params, LINK, IMPORTANT,
                                                                  "activity_archive", resource))
                record.notified_at = now
                told += 1
            elif record.reminded_at is None and delete_on(month) - timedelta(days=REMIND_DAYS) <= today:
                notify(db, org, Audience.holders(ARCHIVE), Notice("foundation.activity_archive.reminder", "work", params, LINK, URGENT,
                                                                  "activity_archive", resource))
                record.reminded_at = now
                reminded += 1
    db.commit()
    return dict(told=told, reminded=reminded, deleted=deleted)
