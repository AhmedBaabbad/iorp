from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, require_permission
from app.production.api.schemas import (
    ProductionOutputCreate,
    ProductionOutputListItem,
    ProductionOutputRead,
    ProductionOutputUpdate,
)
from app.production.application.services import ProductionOutputService
from app.production.domain.enums import ProductionOutputStatus


router = APIRouter(prefix="/production-outputs", tags=["production-outputs"])


@router.post("", response_model=ProductionOutputRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("production:production_outputs:write"))])
def create_production_output(
    payload: ProductionOutputCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> ProductionOutputRead:
    service = ProductionOutputService(db)
    try:
        return service.create_production_output(tenant, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("", response_model=list[ProductionOutputListItem],
    dependencies=[Depends(require_permission("production:production_outputs:read"))])
def list_production_outputs(
    production_order_id: UUID | None = Query(default=None),
    shift_report_id: UUID | None = Query(default=None),
    work_center_id: UUID | None = Query(default=None),
    output_date: date | None = Query(default=None),
    output_status: ProductionOutputStatus | None = Query(default=None),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[ProductionOutputListItem]:
    service = ProductionOutputService(db)
    return service.list_production_outputs(
        tenant,
        production_order_id=production_order_id,
        shift_report_id=shift_report_id,
        work_center_id=work_center_id,
        output_date=output_date,
        output_status=output_status,
    )


@router.get("/{production_output_id}", response_model=ProductionOutputRead,
    dependencies=[Depends(require_permission("production:production_outputs:read"))])
def get_production_output(
    production_output_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> ProductionOutputRead:
    service = ProductionOutputService(db)
    production_output = service.get_production_output(tenant, production_output_id)
    if production_output is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Production output not found.")
    return production_output


@router.patch("/{production_output_id}", response_model=ProductionOutputRead,
    dependencies=[Depends(require_permission("production:production_outputs:write"))])
def update_production_output(
    production_output_id: UUID,
    payload: ProductionOutputUpdate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> ProductionOutputRead:
    service = ProductionOutputService(db)
    try:
        production_output = service.update_production_output(tenant, production_output_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if production_output is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Production output not found.")
    return production_output
