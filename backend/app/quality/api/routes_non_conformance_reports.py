from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db
from app.quality.api.schemas import (
    NonConformanceReportCreate,
    NonConformanceReportListItem,
    NonConformanceReportRead,
    NonConformanceReportUpdate,
)
from app.quality.application.services import NonConformanceReportService
from app.quality.domain.enums import NCRReportType, NCRSourceType, NCRStatus


router = APIRouter(prefix="/non-conformance-reports", tags=["non-conformance-reports"])


@router.post("", response_model=NonConformanceReportRead, status_code=status.HTTP_201_CREATED)
def create_non_conformance_report(
    payload: NonConformanceReportCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> NonConformanceReportRead:
    service = NonConformanceReportService(db)
    try:
        return service.create_report(tenant, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("", response_model=list[NonConformanceReportListItem])
def list_non_conformance_reports(
    source_type: NCRSourceType | None = Query(default=None),
    report_type: NCRReportType | None = Query(default=None),
    ncr_status: NCRStatus | None = Query(default=None),
    report_date: date | None = Query(default=None),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[NonConformanceReportListItem]:
    service = NonConformanceReportService(db)
    return service.list_reports(
        tenant,
        source_type=source_type,
        report_type=report_type,
        status=ncr_status,
        report_date=report_date,
    )


@router.get("/{report_id}", response_model=NonConformanceReportRead)
def get_non_conformance_report(
    report_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> NonConformanceReportRead:
    service = NonConformanceReportService(db)
    report = service.get_report(tenant, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Non-conformance report not found.")
    return report


@router.patch("/{report_id}", response_model=NonConformanceReportRead)
def update_non_conformance_report(
    report_id: UUID,
    payload: NonConformanceReportUpdate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> NonConformanceReportRead:
    service = NonConformanceReportService(db)
    try:
        report = service.update_report(tenant, report_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Non-conformance report not found.")
    return report
