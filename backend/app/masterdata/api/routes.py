"""Master data (MD-001): products with their specification templates, legacy product types, general settings."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, permission_check, require_any_permission, require_permission
from app.masterdata.api.schemas import (LegacyMapInput, LegacyMapResult, LegacyValue, ListItemCreate, ListItemRead, ListItemUpdate,
                                        ListLegacyMapInput, ListName, ProductCreate, ProductRead, ProductUpdate, SettingsInput, SettingsRead)
from app.masterdata.application.list_service import ListService
from app.masterdata.application.services import ProductService, SettingsService
from app.masterdata.domain import permissions as M
from app.masterdata.domain import rules
from app.masterdata.domain.rules import MasterDataError

router = APIRouter(tags=["master data"])


def _attempt(db, action):
    try:
        return action()
    except MasterDataError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status, detail={"code": exc.code, **exc.detail}) from exc


def _read(product, can) -> ProductRead:
    return ProductRead.model_validate({**ProductRead.model_validate(product).model_dump(),
                                       "actions": rules.product_actions(lambda a: can(M.PRODUCT_ACTIONS[a]))})


@router.get("/products", response_model=list[ProductRead], dependencies=[Depends(require_permission(M.PRODUCTS_READ))])
def list_products(search: str | None = Query(default=None, max_length=60), kind: str | None = Query(default=None, pattern="^(finished|material)$"),
                  active_only: bool = False, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                  can=Depends(permission_check)):
    """The organization's products with their specification templates (active_only for choosing one)."""
    return [_read(p, can) for p in ProductService(db, tenant).list(search, kind, active_only)]


@router.get("/products/legacy", response_model=list[LegacyValue],
            dependencies=[Depends(require_any_permission([M.PRODUCTS_CREATE, M.PRODUCTS_MAP_LEGACY]))])
def legacy_values(tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """Product types written as free text before master data, where they are used and how often."""
    return ProductService(db, tenant).legacy()


@router.post("/products/legacy/map", response_model=LegacyMapResult, dependencies=[Depends(require_permission(M.PRODUCTS_MAP_LEGACY))])
def map_legacy_value(payload: LegacyMapInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """Every record storing this text (in every module) now stores the product's key."""
    return _attempt(db, lambda: ProductService(db, tenant).map_legacy(payload.value, payload.product_id))


@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permission(M.PRODUCTS_CREATE))])
def create_product(payload: ProductCreate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                   can=Depends(permission_check)):
    """A product (PRD-NNNN) with its key (fixed from now on) and specification template."""
    return _attempt(db, lambda: _read(ProductService(db, tenant).create(payload), can))


@router.get("/products/{product_id}", response_model=ProductRead, dependencies=[Depends(require_permission(M.PRODUCTS_READ))])
def get_product(product_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    return _attempt(db, lambda: _read(ProductService(db, tenant).get(product_id), can))


@router.patch("/products/{product_id}", response_model=ProductRead, dependencies=[Depends(require_permission(M.PRODUCTS_UPDATE))])
def update_product(product_id: UUID, payload: ProductUpdate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                   can=Depends(permission_check)):
    """Names, kind, unit, notes, active and the template; the key stays."""
    return _attempt(db, lambda: _read(ProductService(db, tenant).update(product_id, payload), can))


@router.get("/settings", response_model=SettingsRead, dependencies=[Depends(require_permission(M.SETTINGS_READ))])
def read_settings(tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """The VAT rate and the default currency of new quotations and purchase orders."""
    return SettingsService(db, tenant).read()


@router.patch("/settings", response_model=SettingsRead, dependencies=[Depends(require_permission(M.SETTINGS_UPDATE))])
def update_settings(payload: SettingsInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return _attempt(db, lambda: SettingsService(db, tenant).update(payload))


# ── reference lists (MD-002) ────────────────────────────────────────────────────────────────────
@router.get("/lists", response_model=list[ListItemRead], dependencies=[Depends(require_permission(M.LISTS_READ))])
def list_items(list_name: ListName | None = Query(default=None, alias="list"), active_only: bool = False,
               tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """Sectors, opportunity sources, countries and cities (one list, or all of them)."""
    service = ListService(db, tenant)
    return service.with_uses(service.items(list_name, active_only))


@router.post("/lists/{list_name}", response_model=ListItemRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permission(M.LISTS_UPDATE))])
def create_list_item(list_name: ListName, payload: ListItemCreate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """An item with its key (fixed from now on); a city names its country."""
    return _attempt(db, lambda: ListService(db, tenant).create(list_name, payload))


@router.post("/lists/{list_name}/standard", response_model=list[ListItemRead], dependencies=[Depends(require_permission(M.LISTS_UPDATE))])
def add_standard_items(list_name: ListName, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """The usual values not there yet, to edit afterwards."""
    return _attempt(db, lambda: ListService(db, tenant).add_standard(list_name))


@router.patch("/lists/items/{item_id}", response_model=ListItemRead, dependencies=[Depends(require_permission(M.LISTS_UPDATE))])
def update_list_item(item_id: UUID, payload: ListItemUpdate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return _attempt(db, lambda: ListService(db, tenant).update(item_id, payload))


@router.delete("/lists/items/{item_id}", dependencies=[Depends(require_permission(M.LISTS_UPDATE))])
def delete_list_item(item_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """An item no record uses; one in use answers ITEM_IN_USE with how many records (deactivate it instead)."""
    return _attempt(db, lambda: ListService(db, tenant).delete(item_id))


@router.get("/lists/{list_name}/legacy", response_model=list[LegacyValue], dependencies=[Depends(require_permission(M.LISTS_MAP_LEGACY))])
def list_legacy(list_name: ListName, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """Texts written before the list, where they are used and how often."""
    return _attempt(db, lambda: ListService(db, tenant).legacy(list_name))


@router.post("/lists/{list_name}/legacy/map", response_model=LegacyMapResult, dependencies=[Depends(require_permission(M.LISTS_MAP_LEGACY))])
def map_list_legacy(list_name: ListName, payload: ListLegacyMapInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """Every record storing this text (in every module) now stores the item's key."""
    return _attempt(db, lambda: ListService(db, tenant).map_legacy(list_name, payload.value, payload.item_id))
