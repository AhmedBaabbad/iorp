from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, require_permission
from app.production.domain import permissions as P
from app.production.api.schemas import (
    ProductionOrderItemCreate,
    ProductionOrderItemListItem,
    ProductionOrderItemRead,
    ProductionOrderItemUpdate,
)
from app.production.application.services import ProductionOrderItemService


router = APIRouter(
    prefix="/production-orders/{production_order_id}/items",
    tags=["production-order-items"],
)


@router.post("", response_model=ProductionOrderItemRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(P.ORDERS_MANAGE_ITEMS))])
def create_production_order_item(
    production_order_id: UUID,
    payload: ProductionOrderItemCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> ProductionOrderItemRead:
    service = ProductionOrderItemService(db)
    try:
        item = service.create_item(tenant, production_order_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Production order not found.")
    return item


@router.get("", response_model=list[ProductionOrderItemListItem],
    dependencies=[Depends(require_permission(P.ORDERS_READ))])
def list_production_order_items(
    production_order_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[ProductionOrderItemListItem]:
    service = ProductionOrderItemService(db)
    items = service.list_items(tenant, production_order_id)
    if items is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Production order not found.")
    return items


@router.get("/{item_id}", response_model=ProductionOrderItemRead,
    dependencies=[Depends(require_permission(P.ORDERS_READ))])
def get_production_order_item(
    production_order_id: UUID,
    item_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> ProductionOrderItemRead:
    service = ProductionOrderItemService(db)
    item = service.get_item(tenant, production_order_id, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Production order item not found.")
    return item


@router.patch("/{item_id}", response_model=ProductionOrderItemRead,
    dependencies=[Depends(require_permission(P.ORDERS_MANAGE_ITEMS))])
def update_production_order_item(
    production_order_id: UUID,
    item_id: UUID,
    payload: ProductionOrderItemUpdate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> ProductionOrderItemRead:
    service = ProductionOrderItemService(db)
    try:
        item = service.update_item(tenant, production_order_id, item_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Production order item not found.")
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission(P.ORDERS_MANAGE_ITEMS))])
def delete_production_order_item(
    production_order_id: UUID,
    item_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> Response:
    service = ProductionOrderItemService(db)
    try:
        deleted = service.delete_item(tenant, production_order_id, item_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if deleted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Production order item not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
