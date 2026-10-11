"""Machine downtime (PROD-DOWNTIME-001). Errors answer {"code": ...} like the order result and waste."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.pagination import Page, PageParams, page_of, page_params
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, require_permission
from app.production.domain import permissions as P
from app.production.api.downtime_schemas import (
    DowntimeClose, DowntimeEventCreate, DowntimeEventListItem, DowntimeEventRead, DowntimeEventUpdate, DowntimeFilters, DowntimeSummaryRead,
)
from app.production.api.order_views import permission_check
from app.production.application.downtime_service import DowntimeService
from app.production.domain.downtime_rules import DowntimeError

router = APIRouter(prefix="/downtime-events", tags=["production-downtime-events"])
READ = Depends(require_permission(P.DOWNTIME_READ))
CREATE = Depends(require_permission(P.DOWNTIME_CREATE))
UPDATE = Depends(require_permission(P.DOWNTIME_UPDATE))
DELETE = Depends(require_permission(P.DOWNTIME_DELETE))
CLOSE = Depends(require_permission(P.DOWNTIME_CLOSE))


def _error(exc):
    return HTTPException(status_code=exc.status, detail={"code": exc.code, **exc.detail})


def _read(service, event, can):
    return DowntimeEventRead.model_validate(event).model_copy(update={"labels": service.labels([event], can)[event.id]})


@router.post("", response_model=DowntimeEventRead, status_code=status.HTTP_201_CREATED, dependencies=[CREATE])
def create_downtime_event(payload: DowntimeEventCreate, tenant: TenantContext = Depends(get_current_tenant),
                          db: Session = Depends(get_db), can=Depends(permission_check)):
    """Without end_time the stop is open (ongoing); with it, closed and its duration computed."""
    service = DowntimeService(db, tenant)
    try:
        return _read(service, service.get(service.create(payload)), can)
    except DowntimeError as exc:
        raise _error(exc) from exc


@router.get("", response_model=Page[DowntimeEventListItem], dependencies=[READ])
def list_downtime_events(filters: DowntimeFilters = Depends(), params: PageParams = Depends(page_params),
                         tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    """One page of downtime events, latest first (ARCH-PAGE-001)."""
    service = DowntimeService(db, tenant)
    events, total = service.list(params, **filters.model_dump())
    labels = service.labels(events, can)
    return page_of([DowntimeEventListItem.model_validate(e).model_copy(update={"labels": labels[e.id]}) for e in events], total, params)


# Before /{downtime_event_id}, so "summary" is never read as an id.
@router.get("/summary", response_model=DowntimeSummaryRead, dependencies=[READ])
def downtime_summary(filters: DowntimeFilters = Depends(), tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """Totals for reports: minutes planned vs. availability loss, by category and machine, open stops, MTTR."""
    return DowntimeService(db, tenant).summary(**filters.model_dump())


@router.get("/{downtime_event_id}", response_model=DowntimeEventRead, dependencies=[READ])
def get_downtime_event(downtime_event_id: UUID, tenant: TenantContext = Depends(get_current_tenant),
                       db: Session = Depends(get_db), can=Depends(permission_check)):
    service = DowntimeService(db, tenant)
    try:
        return _read(service, service.get(downtime_event_id), can)
    except DowntimeError as exc:
        raise _error(exc) from exc


@router.patch("/{downtime_event_id}", response_model=DowntimeEventRead, dependencies=[UPDATE])
def update_downtime_event(downtime_event_id: UUID, payload: DowntimeEventUpdate, tenant: TenantContext = Depends(get_current_tenant),
                          db: Session = Depends(get_db), can=Depends(permission_check)):
    service = DowntimeService(db, tenant)
    try:
        return _read(service, service.get(service.update(downtime_event_id, payload)), can)
    except DowntimeError as exc:
        raise _error(exc) from exc


@router.post("/{downtime_event_id}/close", response_model=DowntimeEventRead, dependencies=[CLOSE])
def close_downtime_event(downtime_event_id: UUID, payload: DowntimeClose, tenant: TenantContext = Depends(get_current_tenant),
                         db: Session = Depends(get_db), can=Depends(permission_check)):
    """End an ongoing stop, now unless end_time is given."""
    service = DowntimeService(db, tenant)
    try:
        return _read(service, service.get(service.close(downtime_event_id, payload.end_time)), can)
    except DowntimeError as exc:
        raise _error(exc) from exc


@router.delete("/{downtime_event_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[DELETE])
def delete_downtime_event(downtime_event_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    try:
        DowntimeService(db, tenant).delete(downtime_event_id)
    except DowntimeError as exc:
        raise _error(exc) from exc
