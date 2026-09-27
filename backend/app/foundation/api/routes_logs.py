from datetime import datetime
from math import ceil
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.dependencies import CurrentUserContext, get_db, require_permission
from app.foundation.infrastructure.models import TenantActivityLog, TenantSecurityEvent

security_router = APIRouter(prefix="/security-log", tags=["tenant-security-log"])
activity_router = APIRouter(prefix="/activity-log", tags=["tenant-activity-log"])

def _page(db, model, conditions, page, page_size):
    total = int(db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0)
    rows = list(db.scalars(select(model).where(*conditions).order_by(model.created_at.desc(), model.id.desc()).offset((page - 1) * page_size).limit(page_size)))
    return {"items": rows, "total": total, "page": page, "page_size": page_size, "pages": ceil(total / page_size) if total else 0}

@security_router.get("")
def tenant_security(event_type: str | None = None, actor_id: UUID | None = None, date_from: datetime | None = None, date_to: datetime | None = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), current: CurrentUserContext = Depends(require_permission("foundation:security_log:read")), db: Session = Depends(get_db)):
    c = [TenantSecurityEvent.organization_id == current.tenant.organization_id]
    if event_type: c.append(TenantSecurityEvent.event_type == event_type)
    if actor_id: c.append(TenantSecurityEvent.actor_id == actor_id)
    if date_from: c.append(TenantSecurityEvent.created_at >= date_from)
    if date_to: c.append(TenantSecurityEvent.created_at <= date_to)
    return _page(db, TenantSecurityEvent, c, page, page_size)

@security_router.get("/{entry_id}")
def tenant_security_detail(entry_id: UUID, current: CurrentUserContext = Depends(require_permission("foundation:security_log:read")), db: Session = Depends(get_db)):
    entry = db.scalar(select(TenantSecurityEvent).where(TenantSecurityEvent.id == entry_id, TenantSecurityEvent.organization_id == current.tenant.organization_id))
    if entry is None: raise HTTPException(404, "Security event not found.")
    return entry

@activity_router.get("")
def tenant_activity(action: str | None = None, entity_type: str | None = None, entity_id: UUID | None = None, actor_id: UUID | None = None, date_from: datetime | None = None, date_to: datetime | None = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), current: CurrentUserContext = Depends(require_permission("foundation:activity_log:read")), db: Session = Depends(get_db)):
    c = [TenantActivityLog.organization_id == current.tenant.organization_id]
    if action: c.append(TenantActivityLog.action == action)
    if entity_type: c.append(TenantActivityLog.entity_type == entity_type)
    if entity_id: c.append(TenantActivityLog.entity_id == entity_id)
    if actor_id: c.append(TenantActivityLog.actor_id == actor_id)
    if date_from: c.append(TenantActivityLog.created_at >= date_from)
    if date_to: c.append(TenantActivityLog.created_at <= date_to)
    return _page(db, TenantActivityLog, c, page, page_size)

@activity_router.get("/{entry_id}")
def tenant_activity_detail(entry_id: UUID, current: CurrentUserContext = Depends(require_permission("foundation:activity_log:read")), db: Session = Depends(get_db)):
    entry = db.scalar(select(TenantActivityLog).where(TenantActivityLog.id == entry_id, TenantActivityLog.organization_id == current.tenant.organization_id))
    if entry is None: raise HTTPException(404, "Activity entry not found.")
    return entry
