"""Purchase orders (PROC-003): one permission per step; the stages are explicit endpoints."""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.reporting.routes import generate_response
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_current_user, get_db, permission_check, require_any_permission, require_permission
from app.procurement.api.routes import _attempt
from app.procurement.api.schemas import OpenOrder, OrderCreate, OrderListItem, OrderRead, OrderUpdate, ReasonInput
from app.procurement.application.purchase_order_service import PurchaseOrderService
from app.procurement.domain import permissions as P

router = APIRouter(tags=["purchase-orders"])
PATH = "/purchase-orders"
STATUSES = "^(draft|approved|sent|partially_received|received|closed|cancelled)$"


def _order(db, tenant, can, action):
    service = PurchaseOrderService(db, tenant)

    def run():
        found = action(service)
        return OrderRead.model_validate({**OrderRead.model_validate(found).model_dump(), **service.views([found], can, True)[0]})
    return _attempt(db, run)


@router.get(PATH, response_model=list[OrderListItem], dependencies=[Depends(require_permission(P.PO_READ))])
def list_orders(status_filter: str | None = Query(default=None, alias="status", pattern=STATUSES), supplier_id: UUID | None = None,
                open_only: bool = False, date_from: date | None = None, date_to: date | None = None,
                search: str | None = Query(default=None, max_length=60), tenant: TenantContext = Depends(get_current_tenant),
                db: Session = Depends(get_db), can=Depends(permission_check)):
    service = PurchaseOrderService(db, tenant)
    rows = service.list(status_filter, supplier_id, date_from, date_to, search, open_only)
    return [OrderListItem.model_validate({**OrderListItem.model_validate(o).model_dump(), **v}) for o, v in zip(rows, service.views(rows, can))]


@router.get(f"{PATH}/open-for-receipt", response_model=list[OpenOrder],
            dependencies=[Depends(require_any_permission([P.RECEIPTS_CREATE, P.RECEIPTS_UPDATE]))])
def open_for_receipt(supplier_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    """The supplier's orders goods may be received against, with what each line still expects."""
    return PurchaseOrderService(db, tenant).open_for_receipt(supplier_id)


@router.post(PATH, response_model=OrderRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission(P.PO_CREATE))])
def create_order(payload: OrderCreate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    """A draft purchase order (PO-YYYY-NNNN) to a registered supplier that is not blocked; amounts are computed here."""
    return _order(db, tenant, can, lambda s: s.create(payload))


@router.get(f"{PATH}/{{order_id}}", response_model=OrderRead, dependencies=[Depends(require_permission(P.PO_READ))])
def get_order(order_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    return _order(db, tenant, can, lambda s: s.get(order_id))


@router.patch(f"{PATH}/{{order_id}}", response_model=OrderRead, dependencies=[Depends(require_permission(P.PO_UPDATE))])
def update_order(order_id: UUID, payload: OrderUpdate, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                 can=Depends(permission_check)):
    """A draft only; the lines, when given, replace the current ones."""
    return _order(db, tenant, can, lambda s: s.update(order_id, payload))


@router.post(f"{PATH}/{{order_id}}/approve", response_model=OrderRead, dependencies=[Depends(require_permission(P.PO_APPROVE))])
def approve_order(order_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    return _order(db, tenant, can, lambda s: s.approve(order_id))


@router.post(f"{PATH}/{{order_id}}/send", response_model=OrderRead, dependencies=[Depends(require_permission(P.PO_SEND))])
def send_order(order_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db), can=Depends(permission_check)):
    """Recorded as sent to the supplier (the document is downloaded and sent outside the system)."""
    return _order(db, tenant, can, lambda s: s.send(order_id))


@router.post(f"{PATH}/{{order_id}}/close", response_model=OrderRead, dependencies=[Depends(require_permission(P.PO_CLOSE))])
def close_order(order_id: UUID, payload: ReasonInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                can=Depends(permission_check)):
    """Nothing more is expected (the rest will not come), with the reason."""
    return _order(db, tenant, can, lambda s: s.close(order_id, payload.reason))


@router.post(f"{PATH}/{{order_id}}/cancel", response_model=OrderRead, dependencies=[Depends(require_permission(P.PO_CANCEL))])
def cancel_order(order_id: UUID, payload: ReasonInput, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                 can=Depends(permission_check)):
    return _order(db, tenant, can, lambda s: s.cancel(order_id, payload.reason))


@router.get(f"{PATH}/{{order_id}}/document.pdf", dependencies=[Depends(require_permission(P.PO_READ))])
def order_document(order_id: UUID, lang: str = Query("ar", pattern="^(ar|en)$"), current=Depends(get_current_user), db: Session = Depends(get_db)):
    """The purchase order as a PDF with the company's identity, in Arabic or English."""
    return generate_response("procurement.purchase_order", dict(order_id=str(order_id), lang=lang), "pdf", current, db)
