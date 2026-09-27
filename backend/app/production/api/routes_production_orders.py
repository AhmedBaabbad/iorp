from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, get_customer_lookup, require_permission
from app.production.api.planning_schemas import PlanningOrderRead, PlanningOrderCreate, ReleaseRequest
from app.production.application.allocation_service import AllocationLifecycleService
from app.production.application.planning_order_service import order_response, PlanningOrderService
from app.production.domain.compatibility import AllocationError
from app.production.api.schemas import (
    ProductionOrderCreate,
    ProductionOrderListItem,
    ProductionOrderRead,
    ProductionOrderUpdate,
)
from app.production.application.services import ProductionOrderService
from app.production.domain.enums import ProductionOrderPriority, ProductionOrderStatus


router = APIRouter(prefix="/production-orders", tags=["production-orders"])


@router.post("", response_model=PlanningOrderRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("production:planning:allocate")), Depends(require_permission("production:orders:create"))])
def create_production_order(
    payload: PlanningOrderCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    customers=Depends(get_customer_lookup),
) -> ProductionOrderRead:
    try:
        order = PlanningOrderService(db, tenant).create_order_from_planning(payload)
    except AllocationError as exc:
        raise HTTPException(status_code=exc.status, detail={"code": exc.code, **exc.detail}) from exc
    return order_response(order, db, tenant, customers)


@router.get("", response_model=list[ProductionOrderListItem],
    dependencies=[Depends(require_permission("production:production_orders:read"))])
def list_production_orders(
    status: ProductionOrderStatus | None = Query(default=None),
    work_center_id: UUID | None = Query(default=None),
    priority: ProductionOrderPriority | None = Query(default=None),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[ProductionOrderListItem]:
    service = ProductionOrderService(db)
    return service.list_production_orders(
        tenant,
        status=status,
        work_center_id=work_center_id,
        priority=priority,
    )


@router.get("/{production_order_id}", response_model=PlanningOrderRead,
    dependencies=[Depends(require_permission("production:production_orders:read"))])
def get_production_order(
    production_order_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    customers=Depends(get_customer_lookup),
) -> ProductionOrderRead:
    service = ProductionOrderService(db)
    production_order = service.get_production_order(tenant, production_order_id)
    if production_order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Production order not found.")
    return order_response(production_order, db, tenant, customers)


@router.patch("/{production_order_id}", response_model=ProductionOrderRead,
    dependencies=[Depends(require_permission("production:production_orders:write"))])
def update_production_order(
    production_order_id: UUID,
    payload: ProductionOrderUpdate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> ProductionOrderRead:
    service = ProductionOrderService(db)
    try:
        production_order = service.update_production_order(tenant, production_order_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if production_order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Production order not found.")
    return production_order


@router.post("/{production_order_id}/cancel", response_model=PlanningOrderRead,
    dependencies=[Depends(require_permission("production:orders:cancel"))])
def cancel_production_order(
    production_order_id: UUID,
    payload: ReleaseRequest,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    customers=Depends(get_customer_lookup),
) -> ProductionOrderRead:
    # Cancelling before execution releases every ACTIVE allocation in the same transaction.
    try:
        order = AllocationLifecycleService(db, tenant).cancel_order(production_order_id, payload.reason)
    except AllocationError as exc:
        raise HTTPException(status_code=exc.status, detail={"code": exc.code, **exc.detail}) from exc
    return order_response(order, db, tenant, customers)
