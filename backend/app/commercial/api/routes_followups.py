from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.commercial.api.schemas import (
    EligibleSalesOwnerResponse,
    FollowUpComplete,
    FollowUpBulkReassignRequest,
    FollowUpBulkReassignResponse,
    FollowUpCreate,
    FollowUpListResponse,
    FollowUpRead,
    FollowUpUpdate,
)
from app.commercial.application.services import CustomerService
from app.commercial.domain.enums import FollowUpPriority, FollowUpStatus
from app.commercial.infrastructure.repositories import FollowUpListFilters
from app.core.interfaces.authorization_policy import AuthorizationPolicy
from app.core.tenancy import TenantContext
from app.dependencies import build_auth_context, get_authorization_policy, get_current_tenant, get_db, require_permission


customer_router = APIRouter(
    prefix="/customers/{customer_id}/follow-ups",
    tags=["commercial-follow-ups"],
)
router = APIRouter(prefix="/follow-ups", tags=["commercial-follow-ups"])


@customer_router.post(
    "",
    response_model=FollowUpRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("commercial:follow_ups:create"))],
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
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if follow_up is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return follow_up


@customer_router.get(
    "",
    response_model=list[FollowUpRead],
    dependencies=[Depends(require_permission("commercial:follow_ups:read"))],
)
def list_follow_ups_for_customer(
    customer_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
) -> list[FollowUpRead]:
    service = CustomerService(db)
    ctx = build_auth_context(db, tenant, "commercial:follow_ups:read")
    follow_ups = service.list_follow_ups_for_customer(tenant, customer_id, policy=policy, auth_context=ctx)
    if follow_ups is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return follow_ups


# Static routes MUST be registered before the dynamic "/{follow_up_id}" route
# below -- otherwise FastAPI tries to parse "eligible-assignees" as a UUID.
@router.get(
    "/eligible-assignees",
    response_model=list[EligibleSalesOwnerResponse],
    dependencies=[Depends(require_permission("commercial:follow_ups:read"))],
)
def list_eligible_assignees(
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[EligibleSalesOwnerResponse]:
    service = CustomerService(db)
    return service.get_eligible_follow_up_assignees(tenant)


@router.post(
    "/reassign-by-user",
    response_model=FollowUpBulkReassignResponse,
    dependencies=[Depends(require_permission("commercial:follow_ups:assign"))],
)
def reassign_follow_ups_by_user(
    payload: FollowUpBulkReassignRequest,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> FollowUpBulkReassignResponse:
    service = CustomerService(db)
    try:
        count = service.reassign_open_follow_ups_by_user(
            tenant,
            payload.from_user_id,
            payload.to_user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return FollowUpBulkReassignResponse(
        from_user_id=payload.from_user_id,
        to_user_id=payload.to_user_id,
        reassigned_count=count,
    )


@router.get(
    "",
    response_model=FollowUpListResponse,
    dependencies=[Depends(require_permission("commercial:follow_ups:read"))],
)
def list_follow_ups(
    scope: Literal["mine", "all"] = "mine",
    status_filter: FollowUpStatus | None = Query(default=None, alias="status"),
    priority: FollowUpPriority | None = None,
    customer_id: UUID | None = None,
    assigned_user_id: UUID | None = None,
    unassigned: bool = False,
    due_from: datetime | None = None,
    due_to: datetime | None = None,
    overdue: bool = False,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
) -> FollowUpListResponse:
    effective_assigned_user_id = assigned_user_id
    if scope == "mine" and assigned_user_id is None and not unassigned:
        effective_assigned_user_id = tenant.user_id

    filters = FollowUpListFilters(
        status=status_filter,
        priority=priority,
        customer_id=customer_id,
        assigned_user_id=effective_assigned_user_id,
        unassigned_only=unassigned,
        due_from=due_from,
        due_to=due_to,
        overdue_only=overdue,
        search=search,
        page=page,
        page_size=page_size,
    )
    service = CustomerService(db)
    ctx = build_auth_context(db, tenant, "commercial:follow_ups:read")
    items, total = service.list_follow_ups(tenant, filters, policy=policy, auth_context=ctx)
    return FollowUpListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/{follow_up_id}",
    response_model=FollowUpRead,
    dependencies=[Depends(require_permission("commercial:follow_ups:read"))],
)
def get_follow_up(
    follow_up_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    policy: AuthorizationPolicy = Depends(get_authorization_policy),
) -> FollowUpRead:
    service = CustomerService(db)
    ctx = build_auth_context(db, tenant, "commercial:follow_ups:read")
    follow_up = service.get_follow_up_by_id(tenant, follow_up_id, policy=policy, auth_context=ctx)
    if follow_up is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Follow-up not found.")
    return follow_up


@router.patch(
    "/{follow_up_id}",
    response_model=FollowUpRead,
    dependencies=[Depends(require_permission("commercial:follow_ups:update"))],
)
def update_follow_up(
    follow_up_id: UUID,
    payload: FollowUpUpdate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> FollowUpRead:
    service = CustomerService(db)
    try:
        follow_up = service.update_follow_up(tenant, follow_up_id, payload)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if follow_up is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Follow-up not found.")
    return follow_up


@router.delete(
    "/{follow_up_id}",
    dependencies=[Depends(require_permission("commercial:follow_ups:delete"))],
)
def delete_follow_up(
    follow_up_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    service = CustomerService(db)
    deleted = service.delete_follow_up(tenant, follow_up_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Follow-up not found.")
    return {"status": "deleted"}


@router.post(
    "/{follow_up_id}/complete",
    response_model=FollowUpRead,
    dependencies=[Depends(require_permission("commercial:follow_ups:complete"))],
)
def complete_follow_up(
    follow_up_id: UUID,
    payload: FollowUpComplete,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> FollowUpRead:
    service = CustomerService(db)
    try:
        follow_up = service.complete_follow_up(tenant, follow_up_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if follow_up is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Follow-up not found.")
    return follow_up


@router.post(
    "/{follow_up_id}/reopen",
    response_model=FollowUpRead,
    dependencies=[Depends(require_permission("commercial:follow_ups:reopen"))],
)
def reopen_follow_up(
    follow_up_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> FollowUpRead:
    service = CustomerService(db)
    try:
        follow_up = service.reopen_follow_up(tenant, follow_up_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if follow_up is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Follow-up not found.")
    return follow_up


@router.post(
    "/{follow_up_id}/cancel",
    response_model=FollowUpRead,
    dependencies=[Depends(require_permission("commercial:follow_ups:cancel"))],
)
def cancel_follow_up(
    follow_up_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> FollowUpRead:
    service = CustomerService(db)
    try:
        follow_up = service.cancel_follow_up(tenant, follow_up_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if follow_up is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Follow-up not found.")
    return follow_up
