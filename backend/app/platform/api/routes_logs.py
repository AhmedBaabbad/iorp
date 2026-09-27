from datetime import datetime
from math import ceil
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.dependencies import get_db, require_platform_permission
from app.platform.domain.permissions import PlatformPermission
from app.platform.infrastructure.models import PlatformActivityLog, PlatformAccount, PlatformSecurityEvent

security_router = APIRouter(prefix="/platform/security-log", tags=["platform-security-log"])
activity_router = APIRouter(prefix="/platform/activity-log", tags=["platform-activity-log"])

def _page(db, model, conditions, page, page_size):
    total = int(db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0)
    rows = list(db.scalars(select(model).where(*conditions).order_by(model.created_at.desc(), model.id.desc()).offset((page - 1) * page_size).limit(page_size)))
    return {"items": rows, "total": total, "page": page, "page_size": page_size, "pages": ceil(total / page_size) if total else 0}

@security_router.get("")
def platform_security(event_type: str | None = None, actor_id: UUID | None = None, date_from: datetime | None = None, date_to: datetime | None = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), _account: PlatformAccount = Depends(require_platform_permission(PlatformPermission.SECURITY_LOG_READ)), db: Session = Depends(get_db)):
    c = []
    if event_type: c.append(PlatformSecurityEvent.event_type == event_type)
    if actor_id: c.append(PlatformSecurityEvent.actor_id == actor_id)
    if date_from: c.append(PlatformSecurityEvent.created_at >= date_from)
    if date_to: c.append(PlatformSecurityEvent.created_at <= date_to)
    return _page(db, PlatformSecurityEvent, c, page, page_size)

@security_router.get("/{entry_id}")
def platform_security_detail(entry_id: UUID, _account: PlatformAccount = Depends(require_platform_permission(PlatformPermission.SECURITY_LOG_READ)), db: Session = Depends(get_db)):
    entry = db.get(PlatformSecurityEvent, entry_id)
    if entry is None: raise HTTPException(404, "Security event not found.")
    return entry

@activity_router.get("")
def platform_activity(action: str | None = None, entity_type: str | None = None, actor_id: UUID | None = None, date_from: datetime | None = None, date_to: datetime | None = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), _account: PlatformAccount = Depends(require_platform_permission(PlatformPermission.ACTIVITY_LOG_READ)), db: Session = Depends(get_db)):
    c = []
    if action: c.append(PlatformActivityLog.action == action)
    if entity_type: c.append(PlatformActivityLog.entity_type == entity_type)
    if actor_id: c.append(PlatformActivityLog.actor_id == actor_id)
    if date_from: c.append(PlatformActivityLog.created_at >= date_from)
    if date_to: c.append(PlatformActivityLog.created_at <= date_to)
    return _page(db, PlatformActivityLog, c, page, page_size)

@activity_router.get("/{entry_id}")
def platform_activity_detail(entry_id: UUID, _account: PlatformAccount = Depends(require_platform_permission(PlatformPermission.ACTIVITY_LOG_READ)), db: Session = Depends(get_db)):
    entry = db.get(PlatformActivityLog, entry_id)
    if entry is None: raise HTTPException(404, "Activity entry not found.")
    return entry
