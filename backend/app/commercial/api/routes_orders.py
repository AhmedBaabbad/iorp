from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.commercial.api.schemas import (
    CommercialOrderCreate,
    CommercialOrderListItem,
    CommercialOrderRead,
    CommercialOrderUpdate,
    OrderDeletionImpact,
)
from app.commercial.application.order_service import OrderService
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, require_permission


router = APIRouter(tags=["commercial-orders"])


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
) -> CommercialOrderRead:
    service = OrderService(db)
    try:
        order = service.create_order(tenant, customer_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return order


@router.get("/orders", response_model=list[CommercialOrderListItem], dependencies=[Depends(require_permission("commercial:orders:read"))])
def list_orders(
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[CommercialOrderListItem]:
    service = OrderService(db)
    return service.list_orders(tenant)


@router.get("/customers/{customer_id}/orders", response_model=list[CommercialOrderListItem], dependencies=[Depends(require_permission("commercial:orders:read"))])
def list_orders_for_customer(
    customer_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[CommercialOrderListItem]:
    service = OrderService(db)
    orders = service.list_orders_for_customer(tenant, customer_id)
    if orders is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return orders


@router.get("/orders/{order_id}", response_model=CommercialOrderRead, dependencies=[Depends(require_permission("commercial:orders:read"))])
def get_order(
    order_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> CommercialOrderRead:
    service = OrderService(db)
    order = service.get_order(tenant, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    return order


@router.patch("/orders/{order_id}", response_model=CommercialOrderRead, dependencies=[Depends(require_permission("commercial:orders:update"))])
def update_order(
    order_id: UUID,
    payload: CommercialOrderUpdate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> CommercialOrderRead:
    service = OrderService(db)
    try:
        order = service.update_order(tenant, order_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    return order


@router.get("/orders/{order_id}/deletion-impact", response_model=OrderDeletionImpact, dependencies=[Depends(require_permission("commercial:orders:read"))])
def get_order_deletion_impact(
    order_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> OrderDeletionImpact:
    service = OrderService(db)
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
    service = OrderService(db)
    found = service.delete_order(tenant, order_id)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
