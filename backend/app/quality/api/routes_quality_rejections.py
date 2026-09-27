from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db
from app.quality.api.schemas import (
    QualityRejectionCreate,
    QualityRejectionListItem,
    QualityRejectionRead,
    QualityRejectionUpdate,
)
from app.quality.application.services import QualityRejectionService
from app.quality.domain.enums import Disposition, DispositionStatus, RejectionReason


router = APIRouter(prefix="/quality-rejections", tags=["quality-rejections"])


@router.post("", response_model=QualityRejectionRead, status_code=status.HTTP_201_CREATED)
def create_quality_rejection(
    payload: QualityRejectionCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> QualityRejectionRead:
    service = QualityRejectionService(db)
    try:
        return service.create_quality_rejection(tenant, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("", response_model=list[QualityRejectionListItem])
def list_quality_rejections(
    rejection_reason: RejectionReason | None = Query(default=None),
    disposition: Disposition | None = Query(default=None),
    disposition_status: DispositionStatus | None = Query(default=None),
    quality_check_id: UUID | None = Query(default=None),
    production_output_id: UUID | None = Query(default=None),
    rejection_date: date | None = Query(default=None),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[QualityRejectionListItem]:
    service = QualityRejectionService(db)
    return service.list_quality_rejections(
        tenant,
        rejection_reason=rejection_reason,
        disposition=disposition,
        disposition_status=disposition_status,
        quality_check_id=quality_check_id,
        production_output_id=production_output_id,
        rejection_date=rejection_date,
    )


@router.get("/{rejection_id}", response_model=QualityRejectionRead)
def get_quality_rejection(
    rejection_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> QualityRejectionRead:
    service = QualityRejectionService(db)
    quality_rejection = service.get_quality_rejection(tenant, rejection_id)
    if quality_rejection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quality rejection not found.")
    return quality_rejection


@router.patch("/{rejection_id}", response_model=QualityRejectionRead)
def update_quality_rejection(
    rejection_id: UUID,
    payload: QualityRejectionUpdate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> QualityRejectionRead:
    service = QualityRejectionService(db)
    try:
        quality_rejection = service.update_quality_rejection(tenant, rejection_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if quality_rejection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quality rejection not found.")
    return quality_rejection
