from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, require_permission
from app.production.api.schemas import (
    WasteRecordCreate,
    WasteRecordListItem,
    WasteRecordRead,
    WasteRecordUpdate,
)
from app.production.application.services import WasteRecordService
from app.production.domain.enums import WasteCategory


router = APIRouter(prefix="/waste-records", tags=["production-waste-records"])


@router.post("", response_model=WasteRecordRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("production:waste_records:write"))])
def create_waste_record(
    payload: WasteRecordCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> WasteRecordRead:
    service = WasteRecordService(db)
    try:
        return service.create_waste_record(tenant, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("", response_model=list[WasteRecordListItem],
    dependencies=[Depends(require_permission("production:waste_records:read"))])
def list_waste_records(
    production_order_id: UUID | None = Query(default=None),
    work_center_id: UUID | None = Query(default=None),
    waste_category: WasteCategory | None = Query(default=None),
    waste_date: date | None = Query(default=None),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[WasteRecordListItem]:
    service = WasteRecordService(db)
    return service.list_waste_records(
        tenant,
        production_order_id=production_order_id,
        work_center_id=work_center_id,
        waste_category=waste_category,
        waste_date=waste_date,
    )


@router.get("/{waste_record_id}", response_model=WasteRecordRead,
    dependencies=[Depends(require_permission("production:waste_records:read"))])
def get_waste_record(
    waste_record_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> WasteRecordRead:
    service = WasteRecordService(db)
    waste_record = service.get_waste_record(tenant, waste_record_id)
    if waste_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Waste record not found.")
    return waste_record


@router.patch("/{waste_record_id}", response_model=WasteRecordRead,
    dependencies=[Depends(require_permission("production:waste_records:write"))])
def update_waste_record(
    waste_record_id: UUID,
    payload: WasteRecordUpdate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> WasteRecordRead:
    service = WasteRecordService(db)
    try:
        waste_record = service.update_waste_record(tenant, waste_record_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if waste_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Waste record not found.")
    return waste_record
