from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.tenancy import TenantContext
from app.dependencies import get_current_tenant, get_db, require_permission
from app.workforce.api.schemas import (
    LinkUserRequest,
    WorkforceMemberCreate,
    WorkforceMemberDeleteResult,
    WorkforceMemberDeletionImpact,
    WorkforceMemberListItem,
    WorkforceMemberResponse,
    WorkforceMemberUpdate,
)
from app.workforce.application.services import WorkforceService
from app.workforce.domain.enums import EmploymentType, WorkforceMemberStatus, WorkerType


router = APIRouter(prefix="/workforce-members", tags=["Workforce"])


@router.post(
    "",
    response_model=WorkforceMemberResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("workforce:members:create"))],
)
def create_workforce_member(
    payload: WorkforceMemberCreate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> WorkforceMemberResponse:
    service = WorkforceService(db)
    try:
        return service.create_workforce_member(tenant, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "",
    response_model=list[WorkforceMemberListItem],
    dependencies=[Depends(require_permission("workforce:members:read"))],
)
def list_workforce_members(
    worker_type: WorkerType | None = None,
    status_filter: WorkforceMemberStatus | None = Query(default=None, alias="status"),
    employment_type: EmploymentType | None = None,
    is_system_user: bool | None = None,
    limit: int | None = Query(default=None, ge=1, le=200),
    offset: int | None = Query(default=None, ge=0),
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> list[WorkforceMemberListItem]:
    service = WorkforceService(db)
    return service.list_workforce_members(
        tenant.organization_id,
        {
            "worker_type": worker_type,
            "status": status_filter,
            "employment_type": employment_type,
            "is_system_user": is_system_user,
            "limit": limit,
            "offset": offset,
        },
    )


@router.get(
    "/{member_id}",
    response_model=WorkforceMemberResponse,
    dependencies=[Depends(require_permission("workforce:members:read"))],
)
def get_workforce_member(
    member_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> WorkforceMemberResponse:
    service = WorkforceService(db)
    member = service.get_workforce_member_by_id(member_id, tenant.organization_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workforce member not found.",
        )
    return member


@router.patch(
    "/{member_id}",
    response_model=WorkforceMemberResponse,
    dependencies=[Depends(require_permission("workforce:members:update"))],
)
def update_workforce_member(
    member_id: UUID,
    payload: WorkforceMemberUpdate,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> WorkforceMemberResponse:
    service = WorkforceService(db)
    try:
        member = service.update_workforce_member(member_id, tenant.organization_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workforce member not found.",
        )
    return member


@router.get(
    "/{member_id}/deletion-impact",
    response_model=WorkforceMemberDeletionImpact,
    dependencies=[Depends(require_permission("workforce:members:read"))],
)
def get_workforce_member_deletion_impact(
    member_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> WorkforceMemberDeletionImpact:
    service = WorkforceService(db)
    member = service.get_workforce_member_by_id(member_id, tenant.organization_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workforce member not found.",
        )
    return WorkforceMemberDeletionImpact(is_blocked=False)


@router.delete(
    "/{member_id}",
    response_model=WorkforceMemberDeleteResult,
    dependencies=[Depends(require_permission("workforce:members:delete"))],
)
def delete_workforce_member(
    member_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> WorkforceMemberDeleteResult:
    service = WorkforceService(db)
    try:
        deleted = service.delete_workforce_member(member_id, tenant.organization_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workforce member not found.",
        )
    return WorkforceMemberDeleteResult(id=member_id, deleted=True)


@router.post(
    "/{member_id}/link-user",
    response_model=WorkforceMemberResponse,
    dependencies=[Depends(require_permission("workforce:members:link_user"))],
)
def link_user_to_member(
    member_id: UUID,
    payload: LinkUserRequest,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> WorkforceMemberResponse:
    service = WorkforceService(db)
    try:
        member = service.link_user_to_member(member_id, payload.user_id, tenant.organization_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workforce member not found.",
        )
    return member


@router.delete(
    "/{member_id}/link-user",
    response_model=WorkforceMemberResponse,
    dependencies=[Depends(require_permission("workforce:members:link_user"))],
)
def unlink_user_from_member(
    member_id: UUID,
    tenant: TenantContext = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> WorkforceMemberResponse:
    service = WorkforceService(db)
    try:
        member = service.unlink_user_from_member(member_id, tenant.organization_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workforce member not found.",
        )
    return member
