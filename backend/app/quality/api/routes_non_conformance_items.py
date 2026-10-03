from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, require_permission
from app.quality.domain import permissions as Q
from app.quality.api.schemas import (
    NonConformanceItemCreate,
    NonConformanceItemListItem,
    NonConformanceItemRead,
    NonConformanceItemUpdate,
)
from app.quality.application.services import NonConformanceItemService


router = APIRouter(tags=["non-conformance-items"])


@router.post(
    "/non-conformance-reports/{report_id}/items",
    response_model=NonConformanceItemRead,
    status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission(Q.NCR_UPDATE))]
)
def create_non_conformance_item(
    report_id: UUID,
    payload: NonConformanceItemCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> NonConformanceItemRead:
    service = NonConformanceItemService(db)
    try:
        return service.create_item(tenant, report_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/non-conformance-reports/{report_id}/items",
    response_model=list[NonConformanceItemListItem], dependencies=[Depends(require_permission(Q.NCR_READ))]
)
def list_non_conformance_items(
    report_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[NonConformanceItemListItem]:
    service = NonConformanceItemService(db)
    try:
        return service.list_items(tenant, report_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/non-conformance-items/{item_id}", response_model=NonConformanceItemRead, dependencies=[Depends(require_permission(Q.NCR_READ))])
def get_non_conformance_item(
    item_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> NonConformanceItemRead:
    service = NonConformanceItemService(db)
    item = service.get_item(tenant, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Non-conformance item not found.")
    return item


@router.patch("/non-conformance-items/{item_id}", response_model=NonConformanceItemRead, dependencies=[Depends(require_permission(Q.NCR_UPDATE))])
def update_non_conformance_item(
    item_id: UUID,
    payload: NonConformanceItemUpdate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> NonConformanceItemRead:
    service = NonConformanceItemService(db)
    try:
        item = service.update_item(tenant, item_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Non-conformance item not found.")
    return item
