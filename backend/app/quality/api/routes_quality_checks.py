from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db
from app.quality.api.schemas import (
    QualityCheckCreate,
    QualityCheckListItem,
    QualityCheckRead,
    QualityCheckUpdate,
)
from app.quality.application.services import QualityCheckService
from app.quality.domain.enums import (
    QualityCheckResult,
    QualityCheckStatus,
    QualityCheckType,
)


router = APIRouter(prefix="/quality-checks", tags=["quality-checks"])


@router.post("", response_model=QualityCheckRead, status_code=status.HTTP_201_CREATED)
def create_quality_check(
    payload: QualityCheckCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> QualityCheckRead:
    service = QualityCheckService(db)
    try:
        return service.create_quality_check(tenant, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("", response_model=list[QualityCheckListItem])
def list_quality_checks(
    check_type: QualityCheckType | None = Query(default=None),
    check_status: QualityCheckStatus | None = Query(default=None),
    result: QualityCheckResult | None = Query(default=None),
    production_order_id: UUID | None = Query(default=None),
    shift_report_id: UUID | None = Query(default=None),
    check_date: date | None = Query(default=None),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[QualityCheckListItem]:
    service = QualityCheckService(db)
    return service.list_quality_checks(
        tenant,
        check_type=check_type,
        status=check_status,
        result=result,
        production_order_id=production_order_id,
        shift_report_id=shift_report_id,
        check_date=check_date,
    )


@router.get("/{check_id}", response_model=QualityCheckRead)
def get_quality_check(
    check_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> QualityCheckRead:
    service = QualityCheckService(db)
    quality_check = service.get_quality_check(tenant, check_id)
    if quality_check is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quality check not found.",
        )
    return quality_check


@router.patch("/{check_id}", response_model=QualityCheckRead)
def update_quality_check(
    check_id: UUID,
    payload: QualityCheckUpdate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> QualityCheckRead:
    service = QualityCheckService(db)
    try:
        quality_check = service.update_quality_check(tenant, check_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if quality_check is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quality check not found.",
        )
    return quality_check
