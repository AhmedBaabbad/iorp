from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.commercial.api.schemas import (
    CustomerCreate,
    CustomerDeletionImpact,
    CustomerLookupItem,
    CustomerPage,
    CustomerRead,
    CustomerUpdate,
    EligibleSalesOwnerResponse,
    CustomerOwnerBulkReassignRequest,
    CustomerOwnerBulkReassignResponse,
)
from app.commercial.application.services import CustomerService
from app.commercial.domain.enums import CustomerStatus, RelationshipStage
from app.commercial.infrastructure.repositories import CustomerFilters
from app.core.pagination import PageParams, page_of, page_params
from app.core.interfaces.authorization_policy import AuthorizationPolicy
from app.core.tenancy import TenantContext
from app.dependencies import get_production_demand_count, build_auth_context, get_authorization_policy, get_current_tenant, get_db, require_any_permission, require_permission


router = APIRouter(prefix="/customers", tags=["customers"])


@router.post(
    "/reassign-by-owner",
    response_model=CustomerOwnerBulkReassignResponse,
    dependencies=[Depends(require_permission("commercial:customers:assign_owner"))],
)
def reassign_customers_by_owner(payload: CustomerOwnerBulkReassignRequest, tenant: TenantContext = Depends(get_current_tenant), db: Session = Depends(get_db)):
    try:
        count = CustomerService(db).reassign_customers_by_owner(tenant, payload.from_user_id, payload.to_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CustomerOwnerBulkReassignResponse(from_user_id=payload.from_user_id, to_user_id=payload.to_user_id, reassigned_count=count)


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("commercial:customers:create"))])
def create_customer(
    payload: CustomerCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    demand_count=Depends(get_production_demand_count),
) -> CustomerRead:
    service = CustomerService(db, demand_count)
    try:
        return service.create_customer(tenant, payload)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("", response_model=CustomerPage, dependencies=[Depends(require_permission("commercial:customers:read"))])
def list_customers(
    search: str | None = Query(None, max_length=120),
    status_filter: CustomerStatus | None = Query(None, alias="status"),
    relationship_stage: RelationshipStage | None = None,
    sales_owner_user_id: UUID | None = None,
    sector: str | None = Query(None, max_length=120),
    params: PageParams = Depends(page_params),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    demand_count=Depends(get_production_demand_count),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
) -> CustomerPage:
    """One page of the customers the user may see (`page`, `page_size` up to 100), searched and filtered by the server."""
    service = CustomerService(db, demand_count)
    ctx = build_auth_context(db, tenant, "commercial:customers:read")
    filters = CustomerFilters(search=(search or "").strip() or None, status=status_filter.value if status_filter else None,
                              relationship_stage=relationship_stage.value if relationship_stage else None,
                              sales_owner_user_id=sales_owner_user_id, sector=sector or None)
    items, total = service.page_customers(tenant, filters, params, policy=policy, auth_context=ctx)
    return CustomerPage(**page_of(items, total, params))


@router.get("/lookup", response_model=list[CustomerLookupItem], dependencies=[Depends(require_permission("commercial:customers:read"))])
def lookup_customers(
    search: str | None = Query(None, max_length=120),
    ids: list[UUID] = Query(default=[], max_length=100),
    limit: int = Query(20, ge=1, le=100),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
) -> list[CustomerLookupItem]:
    """For choosing a customer: the first matches of a code or name; with `ids`, those customers (names on a list)."""
    ctx = build_auth_context(db, tenant, "commercial:customers:read")
    return CustomerService(db).lookup_customers(tenant, (search or "").strip() or None, ids, max(limit, len(ids)),
                                                policy=policy, auth_context=ctx)


@router.get(
    "/eligible-sales-owners",
    response_model=list[EligibleSalesOwnerResponse],
    dependencies=[
        Depends(require_any_permission(["commercial:customers:read", "commercial:customers:assign_owner"])),
    ],
)
def list_eligible_sales_owners(
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    demand_count=Depends(get_production_demand_count),
) -> list[EligibleSalesOwnerResponse]:
    service = CustomerService(db, demand_count)
    return service.get_eligible_sales_owners(tenant)


@router.get("/{customer_id}", response_model=CustomerRead, dependencies=[Depends(require_permission("commercial:customers:read"))])
def get_customer(
    customer_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    demand_count=Depends(get_production_demand_count),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
) -> CustomerRead:
    service = CustomerService(db, demand_count)
    ctx = build_auth_context(db, tenant, "commercial:customers:read")
    customer = service.get_customer(tenant, customer_id, policy=policy, auth_context=ctx)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return customer


@router.patch("/{customer_id}", response_model=CustomerRead, dependencies=[Depends(require_permission("commercial:customers:update"))])
def update_customer(
    customer_id: UUID,
    payload: CustomerUpdate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    demand_count=Depends(get_production_demand_count),
) -> CustomerRead:
    service = CustomerService(db, demand_count)
    try:
        customer = service.update_customer(tenant, customer_id, payload)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return customer


@router.get("/{customer_id}/deletion-impact", response_model=CustomerDeletionImpact, dependencies=[Depends(require_permission("commercial:customers:read"))])
def get_customer_deletion_impact(
    customer_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    demand_count=Depends(get_production_demand_count),
) -> CustomerDeletionImpact:
    service = CustomerService(db, demand_count)
    impact = service.get_deletion_impact(tenant, customer_id)
    if impact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return impact


@router.delete("/{customer_id}", dependencies=[Depends(require_permission("commercial:customers:delete"))])
def delete_customer(
    customer_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    demand_count=Depends(get_production_demand_count),
) -> dict[str, str]:
    service = CustomerService(db, demand_count)
    try:
        deleted = service.delete_customer(tenant, customer_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return {"status": "deleted"}
