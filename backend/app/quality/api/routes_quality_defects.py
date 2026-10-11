from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.pagination import Page, PageParams, page_of, page_params
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, require_permission
from app.quality.domain import permissions as Q
from app.quality.api.schemas import (
    QualityDefectBatchCreate,
    QualityDefectCreate,
    QualityDefectListItem,
    QualityDefectRead,
    QualityDefectUpdate,
)
from app.quality.application.services import QualityDefectService
from app.quality.domain.enums import DefectCategory, DefectSeverity
from app.quality.domain.rules import QualityError


router = APIRouter(tags=["quality-defects"])


@router.post(
    "/quality-checks/{check_id}/defects",
    response_model=QualityDefectRead,
    status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission(Q.DEFECTS_CREATE))]
)
def create_quality_defect(
    check_id: UUID,
    payload: QualityDefectCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> QualityDefectRead:
    service = QualityDefectService(db)
    try:
        return service.create_quality_defect(tenant, check_id, payload)
    except QualityError as exc:
        raise HTTPException(status_code=exc.status, detail={"code": exc.code, **exc.detail}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/quality-checks/{check_id}/defects/batch", response_model=list[QualityDefectRead], status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permission(Q.DEFECTS_CREATE))])
def create_quality_defects(check_id: UUID, payload: QualityDefectBatchCreate, tenant: TenantContext = Depends(get_current_tenant),
                           db: Session = Depends(get_db)) -> list[QualityDefectRead]:
    """Several defects found on one inspection, recorded together (all or none); each defect type once."""
    try:
        return QualityDefectService(db).create_quality_defects(tenant, check_id, payload.defects)
    except QualityError as exc:
        raise HTTPException(status_code=exc.status, detail={"code": exc.code, **exc.detail}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/quality-checks/{check_id}/defects",
    response_model=list[QualityDefectListItem], dependencies=[Depends(require_permission(Q.DEFECTS_READ))]
)
def list_quality_defects_by_check(
    check_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[QualityDefectListItem]:
    service = QualityDefectService(db)
    try:
        return service.list_defects_by_quality_check(tenant, check_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/quality-defects", response_model=Page[QualityDefectListItem], dependencies=[Depends(require_permission(Q.DEFECTS_READ))])
def list_quality_defects(
    defect_category: DefectCategory | None = Query(default=None),
    severity: DefectSeverity | None = Query(default=None),
    production_order_id: UUID | None = Query(default=None),
    defect_date: date | None = Query(default=None),
    params: PageParams = Depends(page_params),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    rows, total = QualityDefectService(db).list_quality_defects(
        tenant,
        params,
        defect_category=defect_category,
        severity=severity,
        production_order_id=production_order_id,
        defect_date=defect_date,
    )
    return page_of([QualityDefectListItem.model_validate(r) for r in rows], total, params)


@router.get("/quality-defects/{defect_id}", response_model=QualityDefectRead, dependencies=[Depends(require_permission(Q.DEFECTS_READ))])
def get_quality_defect(
    defect_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> QualityDefectRead:
    service = QualityDefectService(db)
    quality_defect = service.get_quality_defect(tenant, defect_id)
    if quality_defect is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quality defect not found.")
    return quality_defect


@router.patch("/quality-defects/{defect_id}", response_model=QualityDefectRead, dependencies=[Depends(require_permission(Q.DEFECTS_UPDATE))])
def update_quality_defect(
    defect_id: UUID,
    payload: QualityDefectUpdate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> QualityDefectRead:
    service = QualityDefectService(db)
    try:
        quality_defect = service.update_quality_defect(tenant, defect_id, payload)
    except QualityError as exc:
        raise HTTPException(status_code=exc.status, detail={"code": exc.code, **exc.detail}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if quality_defect is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quality defect not found.")
    return quality_defect
