from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, require_permission
from app.production.api.schemas import (
    ShiftReportCreate,
    ShiftReportListItem,
    ShiftReportRead,
    ShiftReportUpdate,
)
from app.production.application.services import ShiftReportService
from app.production.domain.enums import ShiftReportStatus


router = APIRouter(prefix="/shift-reports", tags=["production-shift-reports"])


@router.post("", response_model=ShiftReportRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("production:shift_reports:write"))])
def create_shift_report(
    payload: ShiftReportCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> ShiftReportRead:
    service = ShiftReportService(db)
    try:
        return service.create_shift_report(tenant, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("", response_model=list[ShiftReportListItem],
    dependencies=[Depends(require_permission("production:shift_reports:read"))])
def list_shift_reports(
    status: ShiftReportStatus | None = Query(default=None),
    work_center_id: UUID | None = Query(default=None),
    shift_definition_id: UUID | None = Query(default=None),
    report_date: date | None = Query(default=None),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[ShiftReportListItem]:
    service = ShiftReportService(db)
    return service.list_shift_reports(
        tenant,
        status=status,
        work_center_id=work_center_id,
        shift_definition_id=shift_definition_id,
        report_date=report_date,
    )


@router.get("/{shift_report_id}", response_model=ShiftReportRead,
    dependencies=[Depends(require_permission("production:shift_reports:read"))])
def get_shift_report(
    shift_report_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> ShiftReportRead:
    service = ShiftReportService(db)
    shift_report = service.get_shift_report(tenant, shift_report_id)
    if shift_report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift report not found.")
    return shift_report


@router.patch("/{shift_report_id}", response_model=ShiftReportRead,
    dependencies=[Depends(require_permission("production:shift_reports:write"))])
def update_shift_report(
    shift_report_id: UUID,
    payload: ShiftReportUpdate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> ShiftReportRead:
    service = ShiftReportService(db)
    try:
        shift_report = service.update_shift_report(tenant, shift_report_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if shift_report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift report not found.")
    return shift_report
