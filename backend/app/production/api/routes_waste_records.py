"""Operational waste records (PROD-WASTE-001). Errors answer {"code": ...} like the order result."""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, require_permission
from app.production.domain import permissions as P
from app.production.api.order_views import permission_check
from app.production.api.waste_schemas import WasteRecordCreate, WasteRecordListItem, WasteRecordRead, WasteRecordUpdate, WasteSummaryRead
from app.production.application.waste_service import WasteService
from app.production.domain.enums import WasteCategory
from app.production.domain.waste_rules import WasteError

router = APIRouter(prefix="/waste-records", tags=["production-waste-records"])
READ = Depends(require_permission(P.WASTE_READ))
CREATE = Depends(require_permission(P.WASTE_CREATE))
UPDATE = Depends(require_permission(P.WASTE_UPDATE))
DELETE = Depends(require_permission(P.WASTE_DELETE))


def _error(exc):
    return HTTPException(status_code=exc.status, detail={"code": exc.code, **exc.detail})


def _read(service, record, can):
    return WasteRecordRead.model_validate(record).model_copy(update={"labels": service.labels([record], can)[record.id]})


@router.post("", response_model=WasteRecordRead, status_code=status.HTTP_201_CREATED, dependencies=[CREATE])
def create_waste_record(payload: WasteRecordCreate, tenant: TenantContext = Depends(get_current_tenant),
                        db: Session = Depends(get_db), can=Depends(permission_check)):
    """While the order is in progress, on hold or completed."""
    service = WasteService(db, tenant)
    try:
        return _read(service, service.get(service.create(payload)), can)
    except WasteError as exc:
        raise _error(exc) from exc


@router.get("", response_model=list[WasteRecordListItem], dependencies=[READ])
def list_waste_records(
    production_order_id: UUID | None = Query(default=None),
    production_run_id: UUID | None = Query(default=None),
    work_center_id: UUID | None = Query(default=None),
    waste_category: WasteCategory | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    can=Depends(permission_check),
):
    service = WasteService(db, tenant)
    records = service.list(production_order_id=production_order_id, production_run_id=production_run_id, work_center_id=work_center_id,
                           waste_category=waste_category, date_from=date_from, date_to=date_to)
    labels = service.labels(records, can)
    return [WasteRecordListItem.model_validate(r).model_copy(update={"labels": labels[r.id]}) for r in records]


# Before /{waste_record_id}, so "summary" is never read as an id.
@router.get("/summary", response_model=WasteSummaryRead, dependencies=[READ])
def order_waste_summary(production_order_id: UUID = Query(...), tenant: TenantContext = Depends(get_current_tenant),
                        db: Session = Depends(get_db), can=Depends(permission_check)):
    """An order's waste per unit and category. Kept apart from the final result's scrap."""
    try:
        return WasteService(db, tenant).summary(production_order_id, can)
    except WasteError as exc:
        raise _error(exc) from exc


@router.get("/{waste_record_id}", response_model=WasteRecordRead, dependencies=[READ])
def get_waste_record(waste_record_id: UUID, tenant: TenantContext = Depends(get_current_tenant),
                     db: Session = Depends(get_db), can=Depends(permission_check)):
    service = WasteService(db, tenant)
    try:
        return _read(service, service.get(waste_record_id), can)
    except WasteError as exc:
        raise _error(exc) from exc


@router.patch("/{waste_record_id}", response_model=WasteRecordRead, dependencies=[UPDATE])
def update_waste_record(waste_record_id: UUID, payload: WasteRecordUpdate, tenant: TenantContext = Depends(get_current_tenant),
                        db: Session = Depends(get_db), can=Depends(permission_check)):
    service = WasteService(db, tenant)
    try:
        return _read(service, service.get(service.update(waste_record_id, payload)), can)
    except WasteError as exc:
        raise _error(exc) from exc


@router.delete("/{waste_record_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[DELETE])
def delete_waste_record(waste_record_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    try:
        WasteService(db, tenant).delete(waste_record_id)
    except WasteError as exc:
        raise _error(exc) from exc
