"""Final order result (PROD-OUTPUT-001). Every write answers with the full, recomputed result."""
from uuid import UUID

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, require_permission
from app.production.domain import permissions as P
from app.production.api.order_views import permission_check
from app.production.api.result_schemas import OrderResultRead, ResultCorrectionCreate, ResultEntryCreate, ResultEntryUpdate, ResultOverviewRow
from app.production.application.result_service import OrderResultService
from app.production.domain.result_rules import ResultError

router = APIRouter(prefix="/production-orders", tags=["production-results"])
# The results list lives on its own path so it never collides with /production-orders/{id}.
overview_router = APIRouter(prefix="/production-results", tags=["production-results"])
READ = Depends(require_permission(P.RESULTS_READ))
CREATE = Depends(require_permission(P.RESULTS_CREATE))
UPDATE = Depends(require_permission(P.RESULTS_UPDATE))
DELETE = Depends(require_permission(P.RESULTS_DELETE))
CORRECT = Depends(require_permission(P.RESULTS_CORRECT))


def _error(exc):
    return HTTPException(status_code=exc.status, detail={"code": exc.code, **exc.detail})


@router.get("/{production_order_id}/result", response_model=OrderResultRead, dependencies=[READ])
def get_order_result(production_order_id: UUID, tenant: TenantContext = Depends(get_current_tenant),
                     db: Session = Depends(get_db), can=Depends(permission_check)):
    try:
        return OrderResultService(db, tenant).result(production_order_id, can)
    except ResultError as exc:
        raise _error(exc) from exc


@router.post("/{production_order_id}/result/entries", response_model=OrderResultRead, status_code=status.HTTP_201_CREATED, dependencies=[CREATE])
def create_result_entry(production_order_id: UUID, payload: ResultEntryCreate, tenant: TenantContext = Depends(get_current_tenant),
                        db: Session = Depends(get_db), can=Depends(permission_check)):
    """Completed orders only."""
    service = OrderResultService(db, tenant)
    try:
        service.create(production_order_id, payload)
        return service.result(production_order_id, can)
    except ResultError as exc:
        raise _error(exc) from exc


@router.patch("/{production_order_id}/result/entries/{entry_id}", response_model=OrderResultRead, dependencies=[UPDATE])
def update_result_entry(production_order_id: UUID, entry_id: UUID, payload: ResultEntryUpdate, tenant: TenantContext = Depends(get_current_tenant),
                        db: Session = Depends(get_db), can=Depends(permission_check)):
    """Completed orders only; a closed order's entries change only through corrections."""
    service = OrderResultService(db, tenant)
    try:
        service.update(production_order_id, entry_id, payload)
        return service.result(production_order_id, can)
    except ResultError as exc:
        raise _error(exc) from exc


@router.delete("/{production_order_id}/result/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[DELETE])
def delete_result_entry(production_order_id: UUID, entry_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    try:
        OrderResultService(db, tenant).delete(production_order_id, entry_id)
    except ResultError as exc:
        raise _error(exc) from exc


@router.post("/{production_order_id}/result/entries/{entry_id}/corrections", response_model=OrderResultRead,
             status_code=status.HTTP_201_CREATED, dependencies=[CORRECT])
def correct_result_entry(production_order_id: UUID, entry_id: UUID, payload: ResultCorrectionCreate,
                         tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    """Closed orders only: a signed delta with a mandatory reason; the original entry stays unchanged."""
    service = OrderResultService(db, tenant)
    try:
        service.correct(production_order_id, entry_id, payload)
        return service.result(production_order_id, can)
    except ResultError as exc:
        raise _error(exc) from exc


@overview_router.get("", response_model=list[ResultOverviewRow], dependencies=[READ])
def list_order_results(result_status: Literal["completed", "closed"] | None = Query(default=None, alias="status"),
                       tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """Completed and closed orders with their result totals per unit."""
    return OrderResultService(db, tenant).overview(result_status)
