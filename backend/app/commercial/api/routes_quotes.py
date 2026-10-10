from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.commercial.application.visibility import QUOTES_READ, visible_owner
from app.commercial.api.schemas import (LifecycleReason, OptionalReason, QuoteCreate, QuoteDeletionImpact, QuoteListItem,
                                        QuotePage, QuoteRead, QuoteUpdate)
from app.commercial.domain.enums import QuoteStatus
from app.commercial.domain.action_permissions import QUOTE_ACTIONS
from app.commercial.infrastructure.repositories import ListFilters
from app.core.pagination import PageParams, page_of, page_params
from app.commercial.application.quote_service import QuoteService
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, permission_check, require_permission


router = APIRouter(tags=["commercial-quotes"])


def _actions(can):
    codes = {"update": "commercial:quotes:update", "edit": "commercial:quotes:update", "create_order": "commercial:orders:create", **QUOTE_ACTIONS}
    return lambda what: can(codes[what])


def _step(db, tenant, can, quote_id, action, reason=None) -> QuoteRead:
    service = QuoteService(db, visible_owner(db, tenant, QUOTES_READ))
    try:
        quote = service.transition(tenant, quote_id, action, reason)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if quote is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found.")
    return service.get_quote(tenant, quote_id, _actions(can))


@router.post(
    "/customers/{customer_id}/quotes",
    response_model=QuoteRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("commercial:quotes:create"))],
)
def create_quote(
    customer_id: UUID,
    payload: QuoteCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    can=Depends(permission_check),
) -> QuoteRead:
    service = QuoteService(db, visible_owner(db, tenant, QUOTES_READ))
    try:
        quote = service.create_quote(tenant, customer_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if quote is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return service.get_quote(tenant, quote.id, _actions(can))


@router.get("/quotes", response_model=QuotePage, dependencies=[Depends(require_permission("commercial:quotes:read"))])
def list_quotes(
    search: str | None = Query(None, max_length=120),
    status_filter: QuoteStatus | None = Query(None, alias="status"),
    customer_id: UUID | None = None,
    params: PageParams = Depends(page_params),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> QuotePage:
    """One page of quotations (ARCH-PAGE-001): search by number or customer; filter by status or customer."""
    items, total = QuoteService(db, visible_owner(db, tenant, QUOTES_READ)).page_quotes(tenant, ListFilters(search=(search or "").strip() or None, status=status_filter.value if status_filter else None, customer_id=customer_id), params)
    return QuotePage(**page_of(items, total, params))


@router.get("/customers/{customer_id}/quotes", response_model=list[QuoteListItem], dependencies=[Depends(require_permission("commercial:quotes:read"))])
def list_quotes_for_customer(
    customer_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[QuoteListItem]:
    service = QuoteService(db, visible_owner(db, tenant, QUOTES_READ))
    quotes = service.list_quotes_for_customer(tenant, customer_id)
    if quotes is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return quotes


@router.get("/quotes/{quote_id}", response_model=QuoteRead, dependencies=[Depends(require_permission("commercial:quotes:read"))])
def get_quote(
    quote_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    can=Depends(permission_check),
) -> QuoteRead:
    service = QuoteService(db, visible_owner(db, tenant, QUOTES_READ))
    quote = service.get_quote(tenant, quote_id, _actions(can))
    if quote is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found.")
    return quote


@router.patch("/quotes/{quote_id}", response_model=QuoteRead, dependencies=[Depends(require_permission("commercial:quotes:update"))])
def update_quote(
    quote_id: UUID,
    payload: QuoteUpdate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    can=Depends(permission_check),
) -> QuoteRead:
    """A draft only."""
    service = QuoteService(db, visible_owner(db, tenant, QUOTES_READ))
    try:
        quote = service.update_quote(tenant, quote_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if quote is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found.")
    return service.get_quote(tenant, quote_id, _actions(can))


@router.post("/quotes/{quote_id}/issue", response_model=QuoteRead, dependencies=[Depends(require_permission("commercial:quotes:issue"))])
def issue_quote(quote_id: UUID, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db),
                can=Depends(permission_check)) -> QuoteRead:
    """Sent to the customer: from now on it is not edited (a change is a new revision)."""
    return _step(db, tenant, can, quote_id, "issue")


@router.post("/quotes/{quote_id}/accept", response_model=QuoteRead, dependencies=[Depends(require_permission("commercial:quotes:accept"))])
def accept_quote(quote_id: UUID, payload: OptionalReason | None = None, tenant: TenantContext = Depends(get_current_tenant),
                 db: Session = Depends(get_db), can=Depends(permission_check)) -> QuoteRead:
    """The customer accepted it: final, a sales order is made from it."""
    return _step(db, tenant, can, quote_id, "accept", payload.reason if payload else None)


@router.post("/quotes/{quote_id}/reject", response_model=QuoteRead, dependencies=[Depends(require_permission("commercial:quotes:reject"))])
def reject_quote(quote_id: UUID, payload: LifecycleReason, tenant: TenantContext = Depends(get_current_tenant),
                 db: Session = Depends(get_db), can=Depends(permission_check)) -> QuoteRead:
    return _step(db, tenant, can, quote_id, "reject", payload.reason)


@router.post("/quotes/{quote_id}/expire", response_model=QuoteRead, dependencies=[Depends(require_permission("commercial:quotes:expire"))])
def expire_quote(quote_id: UUID, payload: OptionalReason | None = None, tenant: TenantContext = Depends(get_current_tenant),
                 db: Session = Depends(get_db), can=Depends(permission_check)) -> QuoteRead:
    return _step(db, tenant, can, quote_id, "expire", payload.reason if payload else None)


@router.post("/quotes/{quote_id}/revise", response_model=QuoteRead, dependencies=[Depends(require_permission("commercial:quotes:revise"))])
def revise_quote(quote_id: UUID, payload: LifecycleReason, tenant: TenantContext = Depends(get_current_tenant),
                 db: Session = Depends(get_db), can=Depends(permission_check)) -> QuoteRead:
    """Back to a draft as a new revision; the history keeps the earlier steps."""
    return _step(db, tenant, can, quote_id, "revise", payload.reason)


@router.get("/quotes/{quote_id}/deletion-impact", response_model=QuoteDeletionImpact, dependencies=[Depends(require_permission("commercial:quotes:read"))])
def get_quote_deletion_impact(
    quote_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> QuoteDeletionImpact:
    service = QuoteService(db, visible_owner(db, tenant, QUOTES_READ))
    impact = service.get_deletion_impact(tenant, quote_id)
    if impact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found.")
    return impact


@router.delete("/quotes/{quote_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(require_permission("commercial:quotes:delete"))])
def delete_quote(
    quote_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    service = QuoteService(db, visible_owner(db, tenant, QUOTES_READ))
    try:
        deleted = service.delete_quote(tenant, quote_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found.")
    return {"status": "deleted"}
