"""Procurement (PROC-001): suppliers, materials and goods receipts; one permission per action."""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.reporting.routes import generate_response
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_current_user, get_db, permission_check, require_any_permission, require_permission
from app.procurement.api.schemas import (MaterialCreate, MaterialRead, MaterialUpdate, ReasonInput, ReceiptCreate, ReceiptListItem, ReceiptRead,
                                         ReceiptUpdate, SettingsInput, SettingsRead, SupplierCreate, SupplierOption, SupplierRead, SupplierStatusInput,
                                         SupplierUpdate)
from app.procurement.application.services import MaterialService, ReceiptService, SupplierService
from app.procurement.domain import permissions as P
from app.procurement.domain.rules import ProcurementError

router = APIRouter(tags=["procurement"])


def _attempt(db, action):
    try:
        return action()
    except ProcurementError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status, detail={"code": exc.code, **exc.detail}) from exc


def _supplier(db, tenant, can, action, detail=True):
    service = SupplierService(db, tenant)

    def run():
        found = action(service)
        return SupplierRead.model_validate({**SupplierRead.model_validate(found).model_dump(), **service.views([found], can, detail)[0]})
    return _attempt(db, run)


def _receipt(db, tenant, can, action):
    service = ReceiptService(db, tenant)

    def run():
        found = action(service)
        return ReceiptRead.model_validate({**ReceiptRead.model_validate(found).model_dump(), **service.views([found], can, True)[0]})
    return _attempt(db, run)


# ── suppliers ────────────────────────────────────────────────────────────────────────────────────
@router.get("/suppliers", response_model=list[SupplierRead], dependencies=[Depends(require_permission(P.SUPPLIERS_READ))])
def list_suppliers(status_filter: str | None = Query(default=None, alias="status", pattern="^(pending|approved|conditional|blocked)$"),
                   category: str | None = Query(default=None, max_length=16), search: str | None = Query(default=None, max_length=60),
                   tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    service = SupplierService(db, tenant)
    rows = service.list(status_filter, category, search)
    return [SupplierRead.model_validate({**SupplierRead.model_validate(s).model_dump(), **v}) for s, v in zip(rows, service.views(rows, can))]


@router.get("/suppliers/lookup", response_model=list[SupplierOption],
            dependencies=[Depends(require_any_permission([P.SUPPLIERS_READ, P.RECEIPTS_CREATE, P.RECEIPTS_UPDATE]))])
def supplier_options(q: str = Query(default="", max_length=60), tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """Suppliers a receipt may come from (blocked ones are left out)."""
    return SupplierService(db, tenant).list(search=q, usable=True, limit=50)


@router.post("/suppliers", response_model=SupplierRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission(P.SUPPLIERS_CREATE))])
def create_supplier(payload: SupplierCreate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                    can=Depends(permission_check)):
    """A new supplier (SUP-NNNN), pending evaluation."""
    return _supplier(db, tenant, can, lambda s: s.create(payload))


@router.get("/suppliers/{supplier_id}", response_model=SupplierRead, dependencies=[Depends(require_permission(P.SUPPLIERS_READ))])
def get_supplier(supplier_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    """The supplier with its receipts and the non-conformance reports raised about it."""
    return _supplier(db, tenant, can, lambda s: s.get(supplier_id))


@router.patch("/suppliers/{supplier_id}", response_model=SupplierRead, dependencies=[Depends(require_permission(P.SUPPLIERS_UPDATE))])
def update_supplier(supplier_id: UUID, payload: SupplierUpdate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                    can=Depends(permission_check)):
    return _supplier(db, tenant, can, lambda s: s.update(supplier_id, payload))


@router.post("/suppliers/{supplier_id}/status", response_model=SupplierRead, dependencies=[Depends(require_permission(P.SUPPLIERS_APPROVE))])
def set_supplier_status(supplier_id: UUID, payload: SupplierStatusInput, tenant: TenantContext = Depends(get_current_tenant),
                        db: Session = Depends(get_db), can=Depends(permission_check)):
    """Approved, conditional (on probation) or blocked; anything but approved needs a reason."""
    return _supplier(db, tenant, can, lambda s: s.set_status(supplier_id, payload.status, payload.reason))


# ── materials ────────────────────────────────────────────────────────────────────────────────────
@router.get("/materials", response_model=list[MaterialRead],
            dependencies=[Depends(require_any_permission([P.MATERIALS_READ, P.RECEIPTS_CREATE, P.RECEIPTS_UPDATE]))])
def list_materials(category: str | None = Query(default=None, max_length=16), search: str | None = Query(default=None, max_length=60),
                   active_only: bool = False, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return MaterialService(db, tenant).list(category, search, active_only)


@router.post("/materials", response_model=MaterialRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission(P.MATERIALS_CREATE))])
def create_material(payload: MaterialCreate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """A purchased material (MAT-NNNN)."""
    return _attempt(db, lambda: MaterialService(db, tenant).create(payload))


@router.patch("/materials/{material_id}", response_model=MaterialRead, dependencies=[Depends(require_permission(P.MATERIALS_UPDATE))])
def update_material(material_id: UUID, payload: MaterialUpdate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return _attempt(db, lambda: MaterialService(db, tenant).update(material_id, payload))


# ── goods receipts ───────────────────────────────────────────────────────────────────────────────
@router.get("/receipts", response_model=list[ReceiptListItem], dependencies=[Depends(require_permission(P.RECEIPTS_READ))])
def list_receipts(status_filter: str | None = Query(default=None, alias="status", pattern="^(draft|received|cancelled)$"), supplier_id: UUID | None = None,
                  date_from: date | None = None, date_to: date | None = None, search: str | None = Query(default=None, max_length=60),
                  tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    service = ReceiptService(db, tenant)
    rows = service.list(status_filter, supplier_id, date_from, date_to, search)
    return [ReceiptListItem.model_validate({**ReceiptListItem.model_validate(r).model_dump(), **v}) for r, v in zip(rows, service.views(rows, can))]


@router.post("/receipts", response_model=ReceiptRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission(P.RECEIPTS_CREATE))])
def create_receipt(payload: ReceiptCreate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                   can=Depends(permission_check)):
    """A draft goods receipt (GRN-YYYY-NNNN) from a registered supplier that is not blocked."""
    return _receipt(db, tenant, can, lambda s: s.create(payload))


@router.get("/receipts/{receipt_id}", response_model=ReceiptRead, dependencies=[Depends(require_permission(P.RECEIPTS_READ))])
def get_receipt(receipt_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    return _receipt(db, tenant, can, lambda s: s.get(receipt_id))


@router.patch("/receipts/{receipt_id}", response_model=ReceiptRead, dependencies=[Depends(require_permission(P.RECEIPTS_UPDATE))])
def update_receipt(receipt_id: UUID, payload: ReceiptUpdate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                   can=Depends(permission_check)):
    """A draft only; the lines, when given, replace the current ones."""
    return _receipt(db, tenant, can, lambda s: s.update(receipt_id, payload))


@router.post("/receipts/{receipt_id}/receive", response_model=ReceiptRead, dependencies=[Depends(require_permission(P.RECEIPTS_RECEIVE))])
def receive_receipt(receipt_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    """The material arrived: the receipt is final."""
    return _receipt(db, tenant, can, lambda s: s.receive(receipt_id))


@router.post("/receipts/{receipt_id}/cancel", response_model=ReceiptRead, dependencies=[Depends(require_permission(P.RECEIPTS_CANCEL))])
def cancel_receipt(receipt_id: UUID, payload: ReasonInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                   can=Depends(permission_check)):
    return _receipt(db, tenant, can, lambda s: s.cancel(receipt_id, payload.reason))


@router.get("/receipts/{receipt_id}/document.pdf", dependencies=[Depends(require_permission(P.RECEIPTS_READ))])
def receipt_document(receipt_id: UUID, lang: str = Query("ar", pattern="^(ar|en)$"), current=Depends(get_current_user), db: Session = Depends(get_db)):
    """The goods receipt note as a PDF with the company's identity."""
    return generate_response("procurement.goods_receipt", dict(receipt_id=str(receipt_id), lang=lang), "pdf", current, db)


@router.get("/settings", response_model=SettingsRead, dependencies=[Depends(require_permission(P.RECEIPTS_READ))])
def read_settings(tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    return ReceiptService(db, tenant).settings()


@router.patch("/settings", response_model=SettingsRead, dependencies=[Depends(require_permission(P.SETTINGS_UPDATE))])
def update_settings(payload: SettingsInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """The goods receipt number prefix (GRN- by default); numbers already issued keep theirs."""
    return ReceiptService(db, tenant).update_settings(payload.receipt_prefix)
