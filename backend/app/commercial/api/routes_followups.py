from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.commercial.api.schemas import (
    FollowUpComplete,
    FollowUpCreate,
    FollowUpRead,
)
from app.commercial.application.services import CustomerService
from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db


customer_router = APIRouter(
    prefix="/customers/{customer_id}/follow-ups",
    tags=["commercial-follow-ups"],
)
router = APIRouter(tags=["commercial-follow-ups"])


@customer_router.post(
    "",
    response_model=FollowUpRead,
    status_code=status.HTTP_201_CREATED,
)
def create_follow_up(
    customer_id: UUID,
    payload: FollowUpCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> FollowUpRead:
    service = CustomerService(db)
    try:
        follow_up = service.create_follow_up(tenant, customer_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if follow_up is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return follow_up


@router.get("/follow-ups", response_model=list[FollowUpRead])
def list_follow_ups(
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[FollowUpRead]:
    service = CustomerService(db)
    return service.list_follow_ups(tenant)


@customer_router.get("", response_model=list[FollowUpRead])
def list_follow_ups_for_customer(
    customer_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[FollowUpRead]:
    service = CustomerService(db)
    follow_ups = service.list_follow_ups_for_customer(tenant, customer_id)
    if follow_ups is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return follow_ups


@router.patch("/follow-ups/{follow_up_id}/complete", response_model=FollowUpRead)
def complete_follow_up(
    follow_up_id: UUID,
    payload: FollowUpComplete,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> FollowUpRead:
    service = CustomerService(db)
    follow_up = service.complete_follow_up(tenant, follow_up_id, payload)
    if follow_up is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Follow-up not found.")
    return follow_up
