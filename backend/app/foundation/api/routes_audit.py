from datetime import datetime, timezone
import csv
from io import StringIO
from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security_models import AuthSecurityEvent
from app.dependencies import CurrentUserContext, get_db, require_permission
from app.foundation.api.schemas_audit import TenantAuditListResponse, TenantAuditResponse

router = APIRouter(prefix="/audit-log", tags=["Tenant Audit"])


def _scoped_filters(stmt, organization_id: UUID, *, entity_type=None, action=None, entity_id=None, actor_id=None, date_from=None, date_to=None, **_ignored):
    stmt = stmt.where(AuthSecurityEvent.organization_id == organization_id)
    if entity_type:
        stmt = stmt.where(AuthSecurityEvent.target_type == entity_type)
    if action:
        stmt = stmt.where(AuthSecurityEvent.event_type == action)
    if entity_id:
        stmt = stmt.where(AuthSecurityEvent.target_id == str(entity_id))
    if actor_id:
        stmt = stmt.where(AuthSecurityEvent.account_id == actor_id)
    if date_from:
        stmt = stmt.where(AuthSecurityEvent.occurred_at >= date_from)
    if date_to:
        stmt = stmt.where(AuthSecurityEvent.occurred_at <= date_to)
    return stmt


@router.get("", response_model=TenantAuditListResponse)
def list_tenant_audit(
    entity_type: str | None = Query(None, pattern="^(user|role|role_assignment|organization)$"),
    action: str | None = Query(None, max_length=64), entity_id: str | None = Query(None, max_length=128),
    actor_id: UUID | None = None, date_from: datetime | None = None, date_to: datetime | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
    current: CurrentUserContext = Depends(require_permission("foundation:audit:read")),
    db: Session = Depends(get_db),
):
    values = dict(locals())
    stmt = _scoped_filters(select(AuthSecurityEvent), current.tenant.organization_id, **values)
    count = _scoped_filters(select(func.count()).select_from(AuthSecurityEvent), current.tenant.organization_id, **values)
    total = int(db.scalar(count) or 0)
    items = list(db.scalars(stmt.order_by(AuthSecurityEvent.occurred_at.desc(), AuthSecurityEvent.id.desc()).offset((page - 1) * page_size).limit(page_size)))
    return TenantAuditListResponse(items=[TenantAuditResponse.model_validate(item) for item in items], total=total, page=page, page_size=page_size, pages=ceil(total / page_size) if total else 0)


@router.get("/export")
def export_tenant_audit(
    locale: str = Query("en", pattern="^(ar|en)$"), entity_type: str | None = None,
    action: str | None = None, entity_id: str | None = None, actor_id: UUID | None = None,
    date_from: datetime | None = None, date_to: datetime | None = None,
    current: CurrentUserContext = Depends(require_permission("foundation:audit:read")), db: Session = Depends(get_db),
):
    rows = list(db.scalars(_scoped_filters(select(AuthSecurityEvent), current.tenant.organization_id, **locals()).order_by(AuthSecurityEvent.occurred_at.desc()).limit(10_000)))
    headers = ["الوقت", "العملية", "الكيان", "المنفذ", "الهدف", "عنوان IP"] if locale == "ar" else ["Occurred at", "Action", "Entity", "Actor", "Target", "IP address"]
    stream = StringIO(newline=""); writer = csv.writer(stream); writer.writerow(headers)
    for item in rows:
        values = [item.occurred_at.isoformat(), item.event_type, item.target_type, item.actor_name_snapshot or item.actor_email_snapshot, item.target_display_snapshot or item.target_id, item.ip_address]
        writer.writerow([("'" + str(value)) if value is not None and str(value).startswith(("=", "+", "-", "@")) else value for value in values])
    filename = f"organization-audit-{datetime.now(timezone.utc).date().isoformat()}.csv"
    return Response(content=("\ufeff" + stream.getvalue()).encode("utf-8"), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/{event_id}", response_model=TenantAuditResponse)
def get_tenant_audit(event_id: UUID, current: CurrentUserContext = Depends(require_permission("foundation:audit:read")), db: Session = Depends(get_db)):
    event = db.scalar(select(AuthSecurityEvent).where(AuthSecurityEvent.id == event_id, AuthSecurityEvent.organization_id == current.tenant.organization_id))
    if event is None:
        raise HTTPException(status_code=404, detail="Audit event not found.")
    return TenantAuditResponse.model_validate(event)
