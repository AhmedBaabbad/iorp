from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.commercial.api.schemas import QuoteCreate, QuoteListItem, QuoteRead, QuoteUpdate
from app.commercial.application.quote_service import QuoteService
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db


router = APIRouter(tags=["commercial-quotes"])


@router.post(
    "/customers/{customer_id}/quotes",
    response_model=QuoteRead,
    status_code=status.HTTP_201_CREATED,
)
def create_quote(
    customer_id: UUID,
    payload: QuoteCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> QuoteRead:
    service = QuoteService(db)
    try:
        quote = service.create_quote(tenant, customer_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if quote is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return quote


@router.get("/quotes", response_model=list[QuoteListItem])
def list_quotes(
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[QuoteListItem]:
    service = QuoteService(db)
    return service.list_quotes(tenant)


@router.get("/customers/{customer_id}/quotes", response_model=list[QuoteListItem])
def list_quotes_for_customer(
    customer_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[QuoteListItem]:
    service = QuoteService(db)
    quotes = service.list_quotes_for_customer(tenant, customer_id)
    if quotes is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return quotes


@router.get("/quotes/{quote_id}", response_model=QuoteRead)
def get_quote(
    quote_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> QuoteRead:
    service = QuoteService(db)
    quote = service.get_quote(tenant, quote_id)
    if quote is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found.")
    return quote


@router.patch("/quotes/{quote_id}", response_model=QuoteRead)
def update_quote(
    quote_id: UUID,
    payload: QuoteUpdate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> QuoteRead:
    service = QuoteService(db)
    try:
        quote = service.update_quote(tenant, quote_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if quote is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found.")
    return quote
