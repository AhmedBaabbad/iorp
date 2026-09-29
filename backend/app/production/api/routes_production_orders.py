from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, get_customer_lookup, require_permission
from app.core.db import Base
from app.production.api.planning_schemas import PlanningOrderRead, PlanningOrderCreate, ReleaseRequest, StatusHistoryRead, TransitionRequest
from app.production.application.order_status_service import OrderStatusService
from app.production.api.order_views import lifecycle_errors, permission_check, with_lifecycle
from app.production.application.planning_order_service import PlanningOrderService
from app.production.domain.compatibility import AllocationError
from app.production.domain.order_lifecycle import TransitionError
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
    can=Depends(permission_check),
) -> ProductionOrderRead:
    try:
        order = PlanningOrderService(db, tenant).create_order_from_planning(payload)
    except AllocationError as exc:
        raise HTTPException(status_code=exc.status, detail={"code": exc.code, **exc.detail}) from exc
    return with_lifecycle(order, db, tenant, customers, can)


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
    can=Depends(permission_check),
) -> ProductionOrderRead:
    service = ProductionOrderService(db)
    production_order = service.get_production_order(tenant, production_order_id)
    if production_order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Production order not found.")
    return with_lifecycle(production_order, db, tenant, customers, can)


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


@router.post("/{production_order_id}/transitions", response_model=PlanningOrderRead,
    dependencies=[Depends(require_permission("production:production_orders:read"))])
def transition_production_order(
    production_order_id: UUID,
    payload: TransitionRequest,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    customers=Depends(get_customer_lookup),
    can=Depends(permission_check),
) -> ProductionOrderRead:
    """The only way to change an order's status. Each action checks its own permission."""
    try:
        order = OrderStatusService(db, tenant).transition(production_order_id, payload.action, can=can, reason=payload.reason,
                                                          expected_version=payload.expected_version)
    except (TransitionError, AllocationError) as exc:
        raise lifecycle_errors(exc) from exc
    return with_lifecycle(order, db, tenant, customers, can)


@router.get("/{production_order_id}/status-history", response_model=list[StatusHistoryRead],
    dependencies=[Depends(require_permission("production:production_orders:read"))])
def production_order_status_history(
    production_order_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    try:
        rows = OrderStatusService(db, tenant).history(production_order_id)
    except TransitionError as exc:
        raise lifecycle_errors(exc) from exc
    ids = {r.actor_user_id for r in rows if r.actor_user_id}
    # Read-only name lookup through the shared table, as demand_service does: no foundation model import.
    users = Base.metadata.tables["foundation_users"]
    names = dict(db.execute(select(users.c.id, users.c.full_name).where(users.c.id.in_(ids), users.c.organization_id == tenant.organization_id)).all()) if ids else {}
    return [StatusHistoryRead.model_validate(r).model_copy(update={"actor_name": names.get(r.actor_user_id)}) for r in rows]


@router.post("/{production_order_id}/cancel", response_model=PlanningOrderRead,
    dependencies=[Depends(require_permission("production:orders:cancel"))])
def cancel_production_order(
    production_order_id: UUID,
    payload: ReleaseRequest,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    customers=Depends(get_customer_lookup),
    can=Depends(permission_check),
) -> ProductionOrderRead:
    """Kept for existing clients; the same as the "cancel" transition."""
    try:
        order = OrderStatusService(db, tenant).transition(production_order_id, "cancel", can=can, reason=payload.reason)
    except (TransitionError, AllocationError) as exc:
        raise lifecycle_errors(exc) from exc
    return with_lifecycle(order, db, tenant, customers, can)
