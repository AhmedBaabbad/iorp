from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, require_permission
from app.production.api.schemas import (
    DowntimeEventCreate,
    DowntimeEventListItem,
    DowntimeEventRead,
    DowntimeEventUpdate,
)
from app.production.application.services import DowntimeEventService
from app.production.domain.enums import DowntimeCategory, DowntimeStatus


router = APIRouter(prefix="/downtime-events", tags=["production-downtime-events"])


@router.post("", response_model=DowntimeEventRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("production:downtime_events:write"))])
def create_downtime_event(
    payload: DowntimeEventCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> DowntimeEventRead:
    service = DowntimeEventService(db)
    try:
        return service.create_downtime_event(tenant, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("", response_model=list[DowntimeEventListItem],
    dependencies=[Depends(require_permission("production:downtime_events:read"))])
def list_downtime_events(
    work_center_id: UUID | None = Query(default=None),
    production_order_id: UUID | None = Query(default=None),
    status: DowntimeStatus | None = Query(default=None),
    category: DowntimeCategory | None = Query(default=None),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[DowntimeEventListItem]:
    service = DowntimeEventService(db)
    return service.list_downtime_events(
        tenant,
        work_center_id=work_center_id,
        production_order_id=production_order_id,
        status=status,
        category=category,
    )


@router.get("/{downtime_event_id}", response_model=DowntimeEventRead,
    dependencies=[Depends(require_permission("production:downtime_events:read"))])
def get_downtime_event(
    downtime_event_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> DowntimeEventRead:
    service = DowntimeEventService(db)
    downtime_event = service.get_downtime_event(tenant, downtime_event_id)
    if downtime_event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Downtime event not found.")
    return downtime_event


@router.patch("/{downtime_event_id}", response_model=DowntimeEventRead,
    dependencies=[Depends(require_permission("production:downtime_events:write"))])
def update_downtime_event(
    downtime_event_id: UUID,
    payload: DowntimeEventUpdate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> DowntimeEventRead:
    service = DowntimeEventService(db)
    try:
        downtime_event = service.update_downtime_event(tenant, downtime_event_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if downtime_event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Downtime event not found.")
    return downtime_event
