"""The organization's security log (who signed in, from where, failures, locks, password changes) and activity log (what
happened in the daily work). Read only, one server page at a time; each entry names the person, not only their id.
The administration's changes have their own audit trail (routes_audit.py)."""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.pagination import PageParams, page_of, page_params, paginate
from app.dependencies import CurrentUserContext, get_db, require_permission
from app.foundation.application.activity_archive import ARCHIVE, ActivityArchiveService, ArchiveError
from app.foundation.application.security_log import ROUTINE
from app.foundation.infrastructure.models import TenantActivityLog as Activity, TenantSecurityEvent as Security, User

security_router = APIRouter(prefix="/security-log", tags=["tenant-security-log"])
activity_router = APIRouter(prefix="/activity-log", tags=["tenant-activity-log"])
SECURITY_READ = require_permission("foundation:security_log:read")
ACTIVITY_READ = require_permission("foundation:activity_log:read")
ACTIVITY_ARCHIVE = require_permission(ARCHIVE)
# Each department's records in the activity log (the area filter), by the first word of the operation.
AREAS: dict[str, tuple[str, ...]] = {
    "commercial": ("customer", "followup", "interaction", "quote", "sample", "order", "complaint"),
    "production": ("production_order", "production_order_item", "production_allocation", "production_result", "production_waste",
                   "production_downtime", "production_demand", "production_run", "work_center", "shift", "shift_roster"),
    "quality": ("quality_check", "quality_defect", "quality_rejection", "quality_certificate", "quality_specification", "ncr_report"),
    "shipping": ("shipment", "return"),
    "procurement": ("supplier", "material", "goods_receipt", "purchase_order"),
    "masterdata": ("product", "list_item"),
    "workforce": ("workforce_member",),
}


def _names(db, organization_id, ids) -> dict:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return dict(db.execute(select(User.id, User.full_name).where(User.organization_id == organization_id, User.id.in_(ids))).all())


def _security_views(db, organization_id, rows) -> list[dict]:
    names = _names(db, organization_id, [r.actor_id for r in rows])
    return [dict(id=r.id, created_at=r.created_at, event_type=r.event_type, actor_id=r.actor_id,
                 actor_name=names.get(r.actor_id), actor_email=r.actor_email, ip_address=r.ip_address, user_agent=r.user_agent,
                 details=r.details, occurrences=r.occurrences or 1, last_seen_at=r.last_seen_at, routine=r.event_type in ROUTINE) for r in rows]


def _activity_views(db, organization_id, rows) -> list[dict]:
    names = _names(db, organization_id, [r.actor_id for r in rows if not r.actor_name])
    return [dict(id=r.id, created_at=r.created_at, action=r.action, entity_type=r.entity_type, entity_id=r.entity_id,
                 entity_name=r.entity_name, actor_id=r.actor_id, actor_name=r.actor_name or names.get(r.actor_id), details=r.details)
            for r in rows]


def _between(query, column, date_from, date_to):
    if date_from:
        query = query.where(column >= date_from)
    if date_to:
        query = query.where(column <= date_to)
    return query


@security_router.get("")
def tenant_security(event_type: str | None = Query(None, max_length=80), important: bool = False, actor_id: UUID | None = None, date_from: datetime | None = None,
                    date_to: datetime | None = None, params: PageParams = Depends(page_params),
                    current: CurrentUserContext = Depends(SECURITY_READ), db: Session = Depends(get_db)):
    org = current.tenant.organization_id
    query = select(Security).where(Security.organization_id == org)
    if event_type:
        query = query.where(Security.event_type == event_type)
    elif important:  # everything but the routine sign-ins
        query = query.where(Security.event_type.notin_(ROUTINE))
    if actor_id:
        query = query.where(Security.actor_id == actor_id)
    rows, total = paginate(db, _between(query, Security.created_at, date_from, date_to).order_by(Security.created_at.desc(), Security.id.desc()), params)
    return page_of(_security_views(db, org, rows), total, params)


@security_router.get("/kinds")
def tenant_security_kinds(current: CurrentUserContext = Depends(SECURITY_READ), db: Session = Depends(get_db)):
    """The kinds of event the organization's log holds (the filter's choices)."""
    return sorted(db.scalars(select(Security.event_type).where(Security.organization_id == current.tenant.organization_id).distinct()))


@security_router.get("/{entry_id}")
def tenant_security_detail(entry_id: UUID, current: CurrentUserContext = Depends(SECURITY_READ), db: Session = Depends(get_db)):
    entry = db.scalar(select(Security).where(Security.id == entry_id, Security.organization_id == current.tenant.organization_id))
    if entry is None:
        raise HTTPException(404, "Security event not found.")
    return _security_views(db, current.tenant.organization_id, [entry])[0]


@activity_router.get("")
def tenant_activity(action: str | None = Query(None, max_length=80), entity_type: str | None = Query(None, max_length=50),
                    area: str | None = Query(None, pattern="^(" + "|".join(AREAS) + ")$"),
                    entity_id: UUID | None = None, actor_id: UUID | None = None, date_from: datetime | None = None, date_to: datetime | None = None,
                    params: PageParams = Depends(page_params), current: CurrentUserContext = Depends(ACTIVITY_READ), db: Session = Depends(get_db)):
    org = current.tenant.organization_id
    query = select(Activity).where(Activity.organization_id == org)
    if action:
        query = query.where(Activity.action == action)
    if area:
        query = query.where(or_(*[Activity.action.like(f"{prefix}.%") for prefix in AREAS[area]]))
    if entity_type:
        query = query.where(Activity.entity_type == entity_type)
    if entity_id:
        query = query.where(Activity.entity_id == entity_id)
    if actor_id:
        query = query.where(Activity.actor_id == actor_id)
    rows, total = paginate(db, _between(query, Activity.created_at, date_from, date_to).order_by(Activity.created_at.desc(), Activity.id.desc()), params)
    return page_of(_activity_views(db, org, rows), total, params)


@activity_router.get("/kinds")
def tenant_activity_kinds(current: CurrentUserContext = Depends(ACTIVITY_READ), db: Session = Depends(get_db)):
    """The kinds of operation the organization's log holds (the filter's choices)."""
    return sorted(db.scalars(select(Activity.action).where(Activity.organization_id == current.tenant.organization_id).distinct()))


@activity_router.get("/actors")
def tenant_activity_actors(current: CurrentUserContext = Depends(ACTIVITY_READ), db: Session = Depends(get_db)):
    """The people who appear in the organization's activity log (the filter's choices)."""
    org = current.tenant.organization_id
    ids = set(db.scalars(select(Activity.actor_id).where(Activity.organization_id == org, Activity.actor_id.isnot(None)).distinct()))
    return sorted(({"id": i, "name": n} for i, n in _names(db, org, ids).items()), key=lambda p: p["name"])


def _archive(fn):
    try:
        return fn()
    except ArchiveError as exc:
        raise HTTPException(exc.status_code, detail=exc.code) from exc


@activity_router.get("/archive")
def activity_archive(current: CurrentUserContext = Depends(ACTIVITY_ARCHIVE), db: Session = Depends(get_db)):
    """The months past their 12-month retention: to download, then delete (else deleted automatically after 30 days)."""
    return ActivityArchiveService(db, current.tenant).due()


@activity_router.get("/archive/{month}/download")
def activity_archive_download(month: str, locale: str = Query("ar", pattern="^(ar|en)$"),
                              current: CurrentUserContext = Depends(ACTIVITY_ARCHIVE), db: Session = Depends(get_db)):
    name, content = _archive(lambda: ActivityArchiveService(db, current.tenant).download(month, locale))
    return Response(content=content, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@activity_router.post("/archive/{month}/delete")
def activity_archive_delete(month: str, current: CurrentUserContext = Depends(ACTIVITY_ARCHIVE), db: Session = Depends(get_db)):
    return _archive(lambda: ActivityArchiveService(db, current.tenant).delete(month))


@activity_router.get("/{entry_id}")
def tenant_activity_detail(entry_id: UUID, current: CurrentUserContext = Depends(ACTIVITY_READ), db: Session = Depends(get_db)):
    entry = db.scalar(select(Activity).where(Activity.id == entry_id, Activity.organization_id == current.tenant.organization_id))
    if entry is None:
        raise HTTPException(404, "Activity entry not found.")
    return _activity_views(db, current.tenant.organization_id, [entry])[0]
