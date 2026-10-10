from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.commercial.application.visibility import ORDERS_READ, visible_owner
from app.commercial.api.schemas import (
    CommercialOrderCreate,
    CommercialOrderListItem,
    CommercialOrderPage,
    CommercialOrderRead,
    CommercialOrderUpdate,
    LifecycleReason,
    OrderDeletionImpact,
)
from app.commercial.application.order_service import OrderService
from app.commercial.domain.enums import CommercialOrderStatus
from app.commercial.infrastructure.repositories import ListFilters
from app.core.pagination import PageParams, page_of, page_params
from app.core.interfaces import sales_order_source
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, permission_check, require_permission


router = APIRouter(tags=["commercial-orders"])

# The permission behind each action a sales order offers; sending it to production is production's own (named by
# production at the composition root, core/interfaces/sales_order_source.py).
ORDER_ACTIONS = {"edit": "commercial:orders:update", "confirm": "commercial:orders:confirm", "revise": "commercial:orders:revise",
                 "cancel": "commercial:orders:cancel", "delete": "commercial:orders:delete"}


def _actions(can):
    def allowed(action):
        if action == "transfer":
            return bool(sales_order_source.transfer_permission) and can(sales_order_source.transfer_permission)
        return can(ORDER_ACTIONS[action])
    return allowed


def _run(step):
    try:
        order = step()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    return order


@router.post(
    "/customers/{customer_id}/orders",
    response_model=CommercialOrderRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("commercial:orders:create"))],
)
def create_order(
    customer_id: UUID,
    payload: CommercialOrderCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    can=Depends(permission_check),
) -> CommercialOrderRead:
    service = OrderService(db, visible_owner(db, tenant, ORDERS_READ))
    try:
        order = service.create_order(tenant, customer_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return service.get_order(tenant, order.id, _actions(can))


@router.get("/orders", response_model=CommercialOrderPage, dependencies=[Depends(require_permission("commercial:orders:read"))])
def list_orders(
    search: str | None = Query(None, max_length=120),
    status_filter: CommercialOrderStatus | None = Query(None, alias="status"),
    customer_id: UUID | None = None,
    params: PageParams = Depends(page_params),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> CommercialOrderPage:
    """One page of sales orders (ARCH-PAGE-001): search by number, customer reference or customer; filter by status or customer."""
    items, total = OrderService(db, visible_owner(db, tenant, ORDERS_READ)).page_orders(tenant, ListFilters(search=(search or "").strip() or None, status=status_filter.value if status_filter else None, customer_id=customer_id), params)
    return CommercialOrderPage(**page_of(items, total, params))


@router.get("/customers/{customer_id}/orders", response_model=list[CommercialOrderListItem], dependencies=[Depends(require_permission("commercial:orders:read"))])
def list_orders_for_customer(
    customer_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[CommercialOrderListItem]:
    service = OrderService(db, visible_owner(db, tenant, ORDERS_READ))
    orders = service.list_orders_for_customer(tenant, customer_id)
    if orders is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return orders


@router.get("/orders/{order_id}", response_model=CommercialOrderRead, dependencies=[Depends(require_permission("commercial:orders:read"))])
def get_order(
    order_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    can=Depends(permission_check),
) -> CommercialOrderRead:
    service = OrderService(db, visible_owner(db, tenant, ORDERS_READ))
    order = service.get_order(tenant, order_id, _actions(can))
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    return order


@router.patch("/orders/{order_id}", response_model=CommercialOrderRead, dependencies=[Depends(require_permission("commercial:orders:update"))])
def update_order(
    order_id: UUID,
    payload: CommercialOrderUpdate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    can=Depends(permission_check),
) -> CommercialOrderRead:
    service = OrderService(db, visible_owner(db, tenant, ORDERS_READ))
    _run(lambda: service.update_order(tenant, order_id, payload))
    return service.get_order(tenant, order_id, _actions(can))


@router.post("/orders/{order_id}/confirm", response_model=CommercialOrderRead, dependencies=[Depends(require_permission("commercial:orders:confirm"))])
def confirm_order(order_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                  can=Depends(permission_check)) -> CommercialOrderRead:
    """Locks the lines, quantities, specifications and prices: production works from it from now on."""
    service = OrderService(db, visible_owner(db, tenant, ORDERS_READ))
    _run(lambda: service.confirm(tenant, order_id))
    return service.get_order(tenant, order_id, _actions(can))


@router.post("/orders/{order_id}/revise", response_model=CommercialOrderRead, dependencies=[Depends(require_permission("commercial:orders:revise"))])
def revise_order(order_id: UUID, payload: LifecycleReason, tenant: TenantContext = Depends(get_current_tenant),
                 db: Session = Depends(get_db), can=Depends(permission_check)) -> CommercialOrderRead:
    """Back to a draft as a new revision, only while nothing of it is with production."""
    service = OrderService(db, visible_owner(db, tenant, ORDERS_READ))
    _run(lambda: service.revise(tenant, order_id, payload.reason))
    return service.get_order(tenant, order_id, _actions(can))


@router.post("/orders/{order_id}/cancel", response_model=CommercialOrderRead, dependencies=[Depends(require_permission("commercial:orders:cancel"))])
def cancel_order(order_id: UUID, payload: LifecycleReason, tenant: TenantContext = Depends(get_current_tenant),
                 db: Session = Depends(get_db), can=Depends(permission_check)) -> CommercialOrderRead:
    service = OrderService(db, visible_owner(db, tenant, ORDERS_READ))
    _run(lambda: service.cancel(tenant, order_id, payload.reason))
    return service.get_order(tenant, order_id, _actions(can))


@router.post("/quotes/{quote_id}/sales-order", response_model=CommercialOrderRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permission("commercial:orders:create"))])
def create_order_from_quote(quote_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                            can=Depends(permission_check)) -> CommercialOrderRead:
    """A draft sales order with the accepted quotation's lines, specifications, prices and currency."""
    service = OrderService(db, visible_owner(db, tenant, ORDERS_READ))
    order = _run(lambda: service.create_from_quote(tenant, quote_id))
    return service.get_order(tenant, order.id, _actions(can))


@router.get("/orders/{order_id}/deletion-impact", response_model=OrderDeletionImpact, dependencies=[Depends(require_permission("commercial:orders:read"))])
def get_order_deletion_impact(
    order_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> OrderDeletionImpact:
    service = OrderService(db, visible_owner(db, tenant, ORDERS_READ))
    impact = service.get_deletion_impact(tenant, order_id)
    if impact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    return impact


@router.delete("/orders/{order_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("commercial:orders:delete"))])
def delete_order(
    order_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> None:
    service = OrderService(db, visible_owner(db, tenant, ORDERS_READ))
    try:
        found = service.delete_order(tenant, order_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
