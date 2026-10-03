from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, require_permission
from app.production.domain import permissions as P
from app.production.api.schemas import (
    WorkCenterCreate,
    WorkCenterDeleteSummary,
    WorkCenterListItem,
    WorkCenterRead,
    WorkCenterUpdate,
)
from app.production.application.services import WorkCenterService


router = APIRouter(prefix="/work-centers", tags=["production-work-centers"])


@router.post("", response_model=WorkCenterRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(P.WORK_CENTERS_CREATE))])
def create_work_center(
    payload: WorkCenterCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> WorkCenterRead:
    service = WorkCenterService(db)
    try:
        return service.create_work_center(tenant, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("", response_model=list[WorkCenterListItem],
    dependencies=[Depends(require_permission(P.WORK_CENTERS_READ))])
def list_work_centers(
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[WorkCenterListItem]:
    service = WorkCenterService(db)
    return service.list_work_centers(tenant)


@router.get("/{work_center_id}", response_model=WorkCenterRead,
    dependencies=[Depends(require_permission(P.WORK_CENTERS_READ))])
def get_work_center(
    work_center_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> WorkCenterRead:
    service = WorkCenterService(db)
    work_center = service.get_work_center(tenant, work_center_id)
    if work_center is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work center not found.")
    return work_center


@router.get("/{work_center_id}/delete-summary", response_model=WorkCenterDeleteSummary,
    dependencies=[Depends(require_permission(P.WORK_CENTERS_READ))])
def get_work_center_delete_summary(
    work_center_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> WorkCenterDeleteSummary:
    service = WorkCenterService(db)
    summary = service.get_work_center_delete_summary(tenant, work_center_id)
    if summary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work center not found.")
    return WorkCenterDeleteSummary(**summary)


@router.patch("/{work_center_id}", response_model=WorkCenterRead,
    dependencies=[Depends(require_permission(P.WORK_CENTERS_UPDATE))])
def update_work_center(
    work_center_id: UUID,
    payload: WorkCenterUpdate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> WorkCenterRead:
    service = WorkCenterService(db)
    try:
        work_center = service.update_work_center(tenant, work_center_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if work_center is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work center not found.")
    return work_center


@router.delete("/{work_center_id}", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission(P.WORK_CENTERS_DELETE))])
def delete_work_center(
    work_center_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> None:
    service = WorkCenterService(db)
    try:
        found = service.delete_work_center(tenant, work_center_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work center not found.")
