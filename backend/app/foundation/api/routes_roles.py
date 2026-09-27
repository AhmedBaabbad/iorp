from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.dependencies import CurrentUserContext, get_db, require_permission
from app.foundation.api.schemas import (
    AssignPermissionRequest,
    RoleCreateRequest,
    RoleDetailResponse,
    RoleDeletionImpactResponse,
    RoleListItem,
    RolePermissionScopeUpdateRequest,
    RoleUpdateRequest,
)
from app.foundation.application.services import FoundationService, RoleGovernanceError

router = APIRouter(tags=["foundation-roles"])


def _role_to_list_item(role, service: FoundationService) -> RoleListItem:
    permissions = service.get_role_permissions(role.id)
    user_count = service.count_users_for_role(role.id)
    return RoleListItem(
        id=role.id,
        name=role.name,
        code=role.code,
        description=role.description,
        is_system=role.is_system,
        is_protected=role.is_protected,
        is_editable=role.is_editable,
        permission_count=len(permissions),
        user_count=user_count,
        permissions_count=len(permissions),
        users_count=user_count,
        created_at=role.created_at,
    )


def _role_to_detail(role, service: FoundationService) -> RoleDetailResponse:
    permission_scope_pairs = service.get_role_permissions_with_scope(role.id)
    user_count = service.count_users_for_role(role.id)
    return RoleDetailResponse(
        id=role.id,
        organization_id=role.organization_id,
        name=role.name,
        code=role.code,
        description=role.description,
        is_system=role.is_system,
        is_protected=role.is_protected,
        is_editable=role.is_editable,
        permission_count=len(permission_scope_pairs),
        user_count=user_count,
        permissions=service.group_permissions_with_scope(permission_scope_pairs),
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.get("/roles", response_model=list[RoleListItem])
def list_roles(
    current: CurrentUserContext = Depends(require_permission("foundation:roles:read")),
    db: Session = Depends(get_db),
) -> list[RoleListItem]:
    service = FoundationService(db)
    roles = service.list_roles(current.tenant.organization_id)
    return [_role_to_list_item(r, service) for r in roles]


@router.post("/roles", response_model=RoleDetailResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreateRequest,
    current: CurrentUserContext = Depends(require_permission("foundation:roles:write")),
    db: Session = Depends(get_db),
) -> RoleDetailResponse:
    service = FoundationService(db)
    try:
        role = service.create_role_for_tenant(current.tenant.organization_id, payload, current.user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _role_to_detail(role, service)


@router.get("/roles/{role_id}", response_model=RoleDetailResponse)
def get_role(
    role_id: UUID,
    current: CurrentUserContext = Depends(require_permission("foundation:roles:read")),
    db: Session = Depends(get_db),
) -> RoleDetailResponse:
    service = FoundationService(db)
    try:
        role = service.get_role_for_tenant(current.tenant.organization_id, role_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RoleGovernanceError as exc:
        return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "message": exc.message})
    return _role_to_detail(role, service)


@router.get("/roles/{role_id}/deletion-impact", response_model=RoleDeletionImpactResponse)
def get_role_deletion_impact(
    role_id: UUID,
    current: CurrentUserContext = Depends(require_permission("foundation:roles:read")),
    db: Session = Depends(get_db),
) -> RoleDeletionImpactResponse:
    service = FoundationService(db)
    try:
        role = service.get_role_for_tenant(current.tenant.organization_id, role_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    user_count = service.count_users_for_role(role.id)
    reason = "ROLE_IS_PROTECTED" if role.is_protected else "SYSTEM_ROLE_CANNOT_BE_DELETED" if role.is_system else "ROLE_HAS_ASSIGNED_USERS" if user_count else None
    return RoleDeletionImpactResponse(role_id=role.id, user_count=user_count, assigned_user_count=user_count, can_delete=reason is None, reason_code=reason)


@router.patch("/roles/{role_id}", response_model=RoleDetailResponse)
def update_role(
    role_id: UUID,
    payload: RoleUpdateRequest,
    current: CurrentUserContext = Depends(require_permission("foundation:roles:write")),
    db: Session = Depends(get_db),
) -> RoleDetailResponse:
    service = FoundationService(db)
    try:
        role = service.update_role_for_tenant(current.tenant.organization_id, role_id, payload, current.user)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RoleGovernanceError as exc:
        return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "message": exc.message})
    return _role_to_detail(role, service)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: UUID,
    current: CurrentUserContext = Depends(require_permission("foundation:roles:write")),
    db: Session = Depends(get_db),
) -> None:
    service = FoundationService(db)
    try:
        service.delete_role_for_tenant(current.tenant.organization_id, role_id, current.user)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RoleGovernanceError as exc:
        content = {"code": exc.code, "message": exc.message}
        if exc.user_count is not None:
            content["user_count"] = exc.user_count
        return JSONResponse(status_code=exc.status_code, content=content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return None


@router.post("/roles/{role_id}/permissions", response_model=RoleDetailResponse, status_code=status.HTTP_201_CREATED)
def assign_permission_to_role(
    role_id: UUID,
    payload: AssignPermissionRequest,
    current: CurrentUserContext = Depends(require_permission("foundation:role_permissions:write")),
    db: Session = Depends(get_db),
) -> RoleDetailResponse:
    service = FoundationService(db)
    try:
        service.assign_permission_to_role_by_code(
            current.tenant.organization_id,
            role_id,
            payload.permission_code,
            current.user,
            scope=payload.scope,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except RoleGovernanceError as exc:
        return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "message": exc.message})
    role = service.get_role_for_tenant(current.tenant.organization_id, role_id)
    return _role_to_detail(role, service)


@router.patch("/roles/{role_id}/permissions/{permission_id}", response_model=RoleDetailResponse)
def update_role_permission_scope(
    role_id: UUID,
    permission_id: str,
    payload: RolePermissionScopeUpdateRequest,
    current: CurrentUserContext = Depends(require_permission("foundation:role_permissions:write")),
    db: Session = Depends(get_db),
) -> RoleDetailResponse:
    service = FoundationService(db)
    try:
        service.update_role_permission_scope_by_code(
            current.tenant.organization_id,
            role_id,
            permission_id,
            payload.scope,
            current.user,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RoleGovernanceError as exc:
        return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "message": exc.message})
    role = service.get_role_for_tenant(current.tenant.organization_id, role_id)
    return _role_to_detail(role, service)


@router.delete("/roles/{role_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_permission_from_role(
    role_id: UUID,
    permission_id: str,
    current: CurrentUserContext = Depends(require_permission("foundation:role_permissions:write")),
    db: Session = Depends(get_db),
) -> None:
    service = FoundationService(db)
    try:
        service.remove_permission_from_role_by_code(
            current.tenant.organization_id,
            role_id,
            permission_id,
            current.user,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RoleGovernanceError as exc:
        return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "message": exc.message})
    return None
