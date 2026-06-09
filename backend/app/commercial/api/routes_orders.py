from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.commercial.api.schemas import (
    CommercialOrderCreate,
    CommercialOrderListItem,
    CommercialOrderRead,
    CommercialOrderUpdate,
)
from app.commercial.application.order_service import OrderService
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db


router = APIRouter(tags=["commercial-orders"])


@router.post(
    "/customers/{customer_id}/orders",
    response_model=CommercialOrderRead,
    status_code=status.HTTP_201_CREATED,
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


@router.get("/orders", response_model=list[CommercialOrderListItem])
def list_orders(
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[CommercialOrderListItem]:
    service = OrderService(db)
    return service.list_orders(tenant)


@router.get("/customers/{customer_id}/orders", response_model=list[CommercialOrderListItem])
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


@router.get("/orders/{order_id}", response_model=CommercialOrderRead)
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


@router.patch("/orders/{order_id}", response_model=CommercialOrderRead)
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
