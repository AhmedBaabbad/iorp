from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.commercial.api.schemas import CustomerInteractionCreate, CustomerInteractionPage, CustomerInteractionRead, CustomerInteractionUpdate
from app.core.pagination import PageParams, page_of, page_params
from app.commercial.application.services import CustomerService
from app.core.interfaces.authorization_policy import AuthorizationPolicy
from app.core.tenancy import TenantContext
from app.dependencies import build_auth_context, get_authorization_policy, get_current_tenant, get_db, require_permission


router = APIRouter(prefix="/customers/{customer_id}/interactions", tags=["customer-interactions"])


@router.post("", response_model=CustomerInteractionRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("commercial:interactions:create"))])
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


@router.get("", response_model=CustomerInteractionPage, dependencies=[Depends(require_permission("commercial:interactions:read"))])
def list_interactions(
    customer_id: UUID,
    params: PageParams = Depends(page_params),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
) -> CustomerInteractionPage:
    """One page of the customer's interactions, the latest first (ARCH-PAGE-001)."""
    service = CustomerService(db)
    ctx = build_auth_context(db, tenant, "commercial:interactions:read")
    found = service.page_interactions(tenant, customer_id, params, policy=policy, auth_context=ctx)
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return CustomerInteractionPage(**page_of(*found, params))


@router.patch("/{interaction_id}", response_model=CustomerInteractionRead, dependencies=[Depends(require_permission("commercial:interactions:update"))])
def update_interaction(
    customer_id: UUID,
    interaction_id: UUID,
    payload: CustomerInteractionUpdate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
) -> CustomerInteractionRead:
    """Corrects a recorded interaction; only one the user may see (RBAC-002)."""
    ctx = build_auth_context(db, tenant, "commercial:interactions:read")
    try:
        interaction = CustomerService(db).update_interaction(tenant, customer_id, interaction_id, payload, policy=policy, auth_context=ctx)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if interaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interaction not found.")
    return interaction


@router.delete("/{interaction_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("commercial:interactions:delete"))])
def delete_interaction(
    customer_id: UUID,
    interaction_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
) -> None:
    ctx = build_auth_context(db, tenant, "commercial:interactions:read")
    try:
        found = CustomerService(db).delete_interaction(tenant, customer_id, interaction_id, policy=policy, auth_context=ctx)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interaction not found.")
