from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.commercial.api.schemas import CustomerInteractionCreate, CustomerInteractionRead
from app.commercial.application.services import CustomerService
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db


router = APIRouter(prefix="/customers/{customer_id}/interactions", tags=["customer-interactions"])


@router.post("", response_model=CustomerInteractionRead, status_code=status.HTTP_201_CREATED)
def create_interaction(
    customer_id: UUID,
    payload: CustomerInteractionCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> CustomerInteractionRead:
    service = CustomerService(db)
    try:
        interaction = service.create_interaction(tenant, customer_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if interaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return interaction


@router.get("", response_model=list[CustomerInteractionRead])
def list_interactions(
    customer_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[CustomerInteractionRead]:
    service = CustomerService(db)
    interactions = service.list_interactions(tenant, customer_id)
    if interactions is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return interactions
