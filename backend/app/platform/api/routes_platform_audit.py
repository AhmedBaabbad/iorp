from datetime import datetime, timezone
import csv
from io import StringIO
from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.core.audit import AuditActor, PlatformAuditService, audit_request_context
from app.core.security_models import AuthSecurityEvent
from app.dependencies import get_db, require_platform_permission
from app.platform.api.schemas_audit import AuditLogListResponse, AuditLogResponse
from app.platform.domain.permissions import PlatformPermission
from app.platform.infrastructure.models import PlatformAccount

router = APIRouter(prefix="/platform/audit-logs", tags=["platform-audit"])


def _filters(
    stmt, *, event_type=None, category=None, outcome=None, severity=None, actor_id=None,
    organization_id=None, target_type=None, target_id=None, request_id=None,
    correlation_id=None, occurred_from=None, occurred_to=None, search=None, **_ignored,
):
    values = {
        AuthSecurityEvent.event_type: event_type, AuthSecurityEvent.category: category,
        AuthSecurityEvent.outcome: outcome, AuthSecurityEvent.severity: severity,
        AuthSecurityEvent.account_id: actor_id, AuthSecurityEvent.organization_id: organization_id,
        AuthSecurityEvent.target_type: target_type, AuthSecurityEvent.target_id: target_id,
        AuthSecurityEvent.request_id: request_id, AuthSecurityEvent.correlation_id: correlation_id,
    }
    for column, value in values.items():
        if value is not None:
            stmt = stmt.where(column == value)
    if occurred_from:
        stmt = stmt.where(AuthSecurityEvent.occurred_at >= occurred_from)
    if occurred_to:
        stmt = stmt.where(AuthSecurityEvent.occurred_at <= occurred_to)
    if search:
        term = f"%{search[:100]}%"
        stmt = stmt.where(or_(
            AuthSecurityEvent.event_type.ilike(term), AuthSecurityEvent.actor_email_snapshot.ilike(term),
            AuthSecurityEvent.actor_name_snapshot.ilike(term), AuthSecurityEvent.target_display_snapshot.ilike(term),
            AuthSecurityEvent.target_id.ilike(term), AuthSecurityEvent.reason.ilike(term),
        ))
    return stmt


@router.get("", response_model=AuditLogListResponse)
def list_audit_logs(
    event_type: str | None = None, category: str | None = None, outcome: str | None = None,
    severity: str | None = None, actor_id: UUID | None = None, organization_id: UUID | None = None,
    target_type: str | None = None, target_id: str | None = None, request_id: str | None = None,
    correlation_id: str | None = None, occurred_from: datetime | None = None, occurred_to: datetime | None = None,
    search: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    _account: PlatformAccount = Depends(require_platform_permission(PlatformPermission.AUDIT_READ)),
    db: Session = Depends(get_db),
):
    filter_values = dict(locals())
    stmt = _filters(select(AuthSecurityEvent), **filter_values)
    count_stmt = _filters(select(func.count()).select_from(AuthSecurityEvent), **filter_values)
    total = int(db.scalar(count_stmt) or 0)
    ordering = AuthSecurityEvent.occurred_at.asc() if sort_order == "asc" else AuthSecurityEvent.occurred_at.desc()
    items = list(db.scalars(stmt.order_by(ordering, AuthSecurityEvent.id.desc()).offset((page - 1) * page_size).limit(page_size)))
    return AuditLogListResponse(items=[AuditLogResponse.model_validate(item) for item in items], total=total, page=page, page_size=page_size, pages=ceil(total / page_size) if total else 0)


def _csv_safe(value) -> str:
    text = "" if value is None else str(value).replace("\r", " ").replace("\n", " ")
    return "'" + text if text.startswith(("=", "+", "-", "@")) else text


@router.get("/export.csv")
def export_audit_logs(
    request: Request, locale: str = Query("en", pattern="^(ar|en)$"), event_type: str | None = None,
    category: str | None = None, outcome: str | None = None, severity: str | None = None,
    actor_id: UUID | None = None, organization_id: UUID | None = None, target_type: str | None = None,
    target_id: str | None = None, request_id: str | None = None, correlation_id: str | None = None,
    occurred_from: datetime | None = None, occurred_to: datetime | None = None, search: str | None = None,
    account: PlatformAccount = Depends(require_platform_permission(PlatformPermission.AUDIT_EXPORT)),
    db: Session = Depends(get_db),
):
    stmt = _filters(select(AuthSecurityEvent), **locals()).order_by(AuthSecurityEvent.occurred_at.desc()).limit(10_000)
    rows = list(db.scalars(stmt))
    headers = ["الوقت", "الحدث", "النتيجة", "الخطورة", "المنفذ", "الهدف", "المنظمة", "معرف الطلب", "السبب"] if locale == "ar" else ["Occurred at", "Event", "Outcome", "Severity", "Actor", "Target", "Organization", "Request ID", "Reason"]
    stream = StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(headers)
    for item in rows:
        writer.writerow([_csv_safe(value) for value in [item.occurred_at.isoformat(), item.event_type, item.outcome, item.severity, item.actor_email_snapshot or item.actor_name_snapshot, item.target_display_snapshot or item.target_id, item.organization_id, item.request_id, item.reason]])
    PlatformAuditService(db).record(event_type="audit_export_requested", category="audit", actor=AuditActor("platform", account.id, account.email, account.full_name), target_type="audit_log", metadata={"row_count": len(rows), "locale": locale}, request=audit_request_context(request))
    db.commit()
    content = "\ufeff" + stream.getvalue()
    filename = f"platform-audit-{datetime.now(timezone.utc).date().isoformat()}.csv"
    return Response(content=content.encode("utf-8"), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/{event_id}", response_model=AuditLogResponse)
def get_audit_log(
    event_id: UUID,
    _account: PlatformAccount = Depends(require_platform_permission(PlatformPermission.AUDIT_READ)),
    db: Session = Depends(get_db),
):
    event = db.get(AuthSecurityEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Audit event not found.")
    return AuditLogResponse.model_validate(event)
