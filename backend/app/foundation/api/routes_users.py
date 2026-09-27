from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.interfaces.follow_up_queries import FollowUpQueryInterface
from app.core.interfaces.customer_queries import CustomerQueryInterface
from app.core.interfaces.workforce_queries import WorkforceQueryInterface
from app.core.interfaces.platform_email_queries import PlatformEmailQueryInterface
from app.core.exceptions import EmailAlreadyExistsError
from app.dependencies import (
    CurrentUserContext,
    get_db,
    get_follow_up_queries,
    get_customer_queries,
    get_workforce_queries,
    get_platform_email_queries,
    require_permission,
)
from app.foundation.api.schemas import (
    AdminPasswordResetRequest,
    UserCreateRequest,
    UserDetailResponse,
    UserDeactivationImpactResponse,
    UserListItem,
    UserRoleAssignRequest,
    UserUpdateRequest,
    AssignedRoleResponse,
    AssignableRoleResponse,
    AssignableRolesResponse,
    RoleAssignerResponse,
    RoleAssignmentResponse,
    RoleRemovalResponse,
    RoleRef,
    UserRolesResponse,
    EffectiveAccessResponse,
)
from app.foundation.application.effective_access import compute_effective_access
from app.foundation.application.services import (
    FoundationService,
    OrganizationRootProtectionError,
    RoleAssignmentSafetyError,
    UserHasOpenFollowUpsError,
    UserHasOpenDependenciesError,
)
from app.foundation.domain.enums import UserStatus
from app.foundation.domain.user_lifecycle import InvalidUserStateTransitionError

router = APIRouter(tags=["foundation-users"])


_SCOPE_LABELS = {
    "en": {"own": "My Data Only", "team": "My Team's Data", "organization": "Entire Organization"},
    "ar": {"own": "بياناتي فقط", "team": "بيانات فريقي", "organization": "كل المنظمة"},
}


def _effective_access_locale(request: Request, current: CurrentUserContext) -> str:
    header = request.headers.get("accept-language", "").lower()
    for item in header.split(","):
        code = item.strip().split(";", 1)[0].split("-", 1)[0]
        if code in ("ar", "en"):
            return code
    return current.user.preferred_locale or current.user.organization.default_locale or "ar"


def _effective_access_response(report, locale: str) -> EffectiveAccessResponse:
    permissions_by_module = {}
    for module, permissions in report.permissions_by_module.items():
        permissions_by_module[module] = [{
            "code": item.code, "module": item.module, "resource": item.resource,
            "action": item.action, "name": getattr(item, f"name_{locale}"),
            "description": getattr(item, f"description_{locale}"),
            "effective_scope": item.effective_scope, "scopable": item.scopable,
            "scope_label": _SCOPE_LABELS[locale][item.effective_scope],
            "granted_by_roles": item.granted_by_roles,
            "is_root_bypass": item.is_root_bypass,
        } for item in permissions]
    missing = [{
        "code": item["code"], "module": item["module"], "name": item[f"name_{locale}"],
    } for item in report.missing_permissions]
    return EffectiveAccessResponse(
        user_id=report.user_id, user_full_name=report.user_full_name,
        user_email=report.user_email, is_organization_root=report.is_organization_root,
        total_permissions=report.total_permissions, total_roles=report.total_roles,
        roles=report.roles, permissions_by_module=permissions_by_module,
        missing_permissions_count=len(missing), missing_permissions=missing,
        generated_at=report.generated_at,
    )


@router.get("/users/{user_id}/effective-access", response_model=EffectiveAccessResponse)
def get_user_effective_access(
    user_id: UUID,
    request: Request,
    current: CurrentUserContext = Depends(require_permission("foundation:users:read")),
    db: Session = Depends(get_db),
) -> EffectiveAccessResponse:
    try:
        report = compute_effective_access(db, user_id, current.tenant.organization_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="User not found.") from exc
    return _effective_access_response(report, _effective_access_locale(request, current))


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: UUID,
    payload: AdminPasswordResetRequest,
    current: CurrentUserContext = Depends(require_permission("foundation:users:reset_password")),
    db: Session = Depends(get_db),
) -> dict[str, str | bool]:
    try:
        FoundationService(db).reset_user_password_for_tenant(
            current.tenant.organization_id,
            user_id,
            payload.new_password,
            payload.new_password_confirmation,
            current.user,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except OrganizationRootProtectionError as exc:
        return _root_protection_response(exc)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"message": "Password reset successfully", "sessions_invalidated": True}


def _open_follow_ups_conflict(exc: UserHasOpenFollowUpsError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "code": "USER_HAS_OPEN_FOLLOW_UPS",
            "message": str(exc),
            "user_id": str(exc.user_id),
            "open_follow_up_count": exc.open_follow_up_count,
        },
    )


def _root_protection_response(exc: OrganizationRootProtectionError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": str(exc)},
    )


def _dependencies_conflict(exc: UserHasOpenDependenciesError) -> JSONResponse:
    impact = exc.impact
    return JSONResponse(status_code=409, content={
        "code": "USER_HAS_OPEN_DEPENDENCIES", "message": str(exc),
        "dependencies": {"open_follow_ups": impact.open_follow_ups, "assigned_customers": impact.assigned_customers, "active_workforce_link": impact.active_workforce_link},
        "total_blocking_items": impact.total_blocking_items,
    })


def _transition_conflict(exc: InvalidUserStateTransitionError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"code": "INVALID_USER_STATE_TRANSITION", "message": str(exc), "allowed_transitions": exc.allowed})


def _user_to_list_item(user, roles: list) -> UserListItem:
    return UserListItem(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        preferred_locale=user.preferred_locale,
        status=user.status,
        is_organization_root=user.is_organization_root,
        roles=roles,
        created_at=user.created_at,
    )


def _user_to_detail(user, roles: list) -> UserDetailResponse:
    service_roles = roles
    return UserDetailResponse(
        id=user.id,
        organization_id=user.organization_id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        preferred_locale=user.preferred_locale,
        status=user.status,
        is_organization_root=user.is_organization_root,
        last_login_at=user.last_login_at,
        failed_login_attempts=user.failed_login_attempts,
        auto_locked_until=user.auto_locked_until,
        last_failed_login_at=user.last_failed_login_at,
        roles=service_roles,
        permissions=[],
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get("/users", response_model=list[UserListItem])
def list_users(
    current: CurrentUserContext = Depends(require_permission("foundation:users:read")),
    db: Session = Depends(get_db),
) -> list[UserListItem]:
    service = FoundationService(db)
    users = service.list_users(current.tenant.organization_id)
    result = []
    for user in users:
        roles = service.get_user_roles(user.id, current.tenant.organization_id)
        result.append(_user_to_list_item(user, roles))
    return result


@router.post("/users", response_model=UserDetailResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateRequest,
    current: CurrentUserContext = Depends(require_permission("foundation:users:write")),
    db: Session = Depends(get_db),
    platform_emails: PlatformEmailQueryInterface = Depends(get_platform_email_queries),
) -> UserDetailResponse:
    service = FoundationService(db)
    try:
        user = service.create_user_for_tenant(current.tenant.organization_id, payload, platform_emails, current.user)
    except EmailAlreadyExistsError:
        return JSONResponse(status_code=409, content={"code": "EMAIL_ALREADY_EXISTS", "message": "This email is already registered in the system"})
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    roles = service.get_user_roles(user.id, current.tenant.organization_id)
    return _user_to_detail(user, roles)


@router.get("/users/{user_id}", response_model=UserDetailResponse)
def get_user(
    user_id: UUID,
    current: CurrentUserContext = Depends(require_permission("foundation:users:read")),
    db: Session = Depends(get_db),
) -> UserDetailResponse:
    service = FoundationService(db)
    user = service.get_user_by_id_in_organization(user_id, current.tenant.organization_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    roles = service.get_user_roles(user.id, current.tenant.organization_id)
    response = _user_to_detail(user, roles)
    response.permissions = sorted(
        p.code
        for p in service.get_user_permissions(user.id, current.tenant.organization_id)
    )
    return response


@router.patch("/users/{user_id}", response_model=UserDetailResponse)
async def update_user(
    user_id: UUID,
    payload: UserUpdateRequest,
    request: Request,
    current: CurrentUserContext = Depends(require_permission("foundation:users:write")),
    db: Session = Depends(get_db),
    follow_up_queries: FollowUpQueryInterface = Depends(get_follow_up_queries),
    platform_emails: PlatformEmailQueryInterface = Depends(get_platform_email_queries),
) -> UserDetailResponse:
    raw_payload = await request.json()
    if isinstance(raw_payload, dict) and "status" in raw_payload:
        raise HTTPException(status_code=400, detail="Use the dedicated user lifecycle endpoints to change status.")
    service = FoundationService(db)
    try:
        user = service.update_user_for_tenant(
            current.tenant.organization_id,
            current.user.id,
            user_id,
            payload,
            follow_up_queries,
            platform_emails,
        )
    except EmailAlreadyExistsError:
        return JSONResponse(status_code=409, content={"code": "EMAIL_ALREADY_EXISTS", "message": "This email is already registered in the system"})
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UserHasOpenFollowUpsError as exc:
        return _open_follow_ups_conflict(exc)
    except OrganizationRootProtectionError as exc:
        return _root_protection_response(exc)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    roles = service.get_user_roles(user.id, current.tenant.organization_id)
    return _user_to_detail(user, roles)


@router.get(
    "/users/{user_id}/deactivation-impact",
    response_model=UserDeactivationImpactResponse,
)
def get_user_deactivation_impact(
    user_id: UUID,
    current: CurrentUserContext = Depends(require_permission("foundation:users:deactivate")),
    db: Session = Depends(get_db),
    follow_up_queries: FollowUpQueryInterface = Depends(get_follow_up_queries),
    customer_queries: CustomerQueryInterface = Depends(get_customer_queries),
    workforce_queries: WorkforceQueryInterface = Depends(get_workforce_queries),
) -> UserDeactivationImpactResponse:
    service = FoundationService(db)
    try:
        impact = service.get_user_deactivation_impact(current.tenant.organization_id, user_id, follow_up_queries, customer_queries, workforce_queries)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return UserDeactivationImpactResponse(
        user_id=impact.user_id, user_full_name=impact.user_full_name,
        can_deactivate=impact.can_deactivate,
        dependencies={"open_follow_ups": impact.open_follow_ups, "assigned_customers": impact.assigned_customers, "active_workforce_link": impact.active_workforce_link},
        total_blocking_items=impact.total_blocking_items,
        message=f"User has {impact.total_blocking_items} open dependencies that must be resolved before deactivation",
    )


@router.delete("/users/{user_id}/hard", status_code=status.HTTP_200_OK, response_model=UserDetailResponse, include_in_schema=False)
@router.delete("/users/{user_id}", status_code=status.HTTP_200_OK, response_model=UserDetailResponse)
def delete_user(
    user_id: UUID,
    current: CurrentUserContext = Depends(require_permission("foundation:users:deactivate")),
    db: Session = Depends(get_db),
    follow_up_queries: FollowUpQueryInterface = Depends(get_follow_up_queries),
    customer_queries: CustomerQueryInterface = Depends(get_customer_queries),
    workforce_queries: WorkforceQueryInterface = Depends(get_workforce_queries),
) -> UserDetailResponse | JSONResponse:
    service = FoundationService(db)
    try:
        user = service.deactivate_user_for_tenant(
            current.tenant.organization_id,
            current.user.id,
            user_id,
            follow_up_queries,
            customer_queries,
            workforce_queries,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UserHasOpenDependenciesError as exc:
        return _dependencies_conflict(exc)
    except InvalidUserStateTransitionError as exc:
        return _transition_conflict(exc)
    except OrganizationRootProtectionError as exc:
        return _root_protection_response(exc)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _user_to_detail(user, service.get_user_roles(user.id, current.tenant.organization_id))


def _status_action(user_id: UUID, target: UserStatus, current: CurrentUserContext, db: Session, *, clear_auto_lock: bool = False):
    service = FoundationService(db)
    try:
        user = service.get_user_by_id_in_organization(user_id, current.tenant.organization_id)
        if user is None:
            raise LookupError("User not found.")
        if not (clear_auto_lock and user.status == UserStatus.ACTIVE):
            user = service.change_user_status_for_tenant(current.tenant.organization_id, current.user.id, user_id, target)
        if clear_auto_lock:
            user.failed_login_attempts = 0
            user.auto_locked_until = None
            user.last_failed_login_at = None
            db.commit()
            db.refresh(user)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OrganizationRootProtectionError as exc:
        return _root_protection_response(exc)
    except InvalidUserStateTransitionError as exc:
        return _transition_conflict(exc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _user_to_detail(user, service.get_user_roles(user.id, current.tenant.organization_id))


@router.post("/users/{user_id}/lock", response_model=UserDetailResponse)
def lock_user(user_id: UUID, current: CurrentUserContext = Depends(require_permission("foundation:users:lock")), db: Session = Depends(get_db)):
    return _status_action(user_id, UserStatus.LOCKED, current, db)


@router.post("/users/{user_id}/unlock", response_model=UserDetailResponse)
def unlock_user(user_id: UUID, current: CurrentUserContext = Depends(require_permission("foundation:users:lock")), db: Session = Depends(get_db)):
    return _status_action(user_id, UserStatus.ACTIVE, current, db, clear_auto_lock=True)


@router.post("/users/{user_id}/activate", response_model=UserDetailResponse)
def activate_user(user_id: UUID, current: CurrentUserContext = Depends(require_permission("foundation:users:activate")), db: Session = Depends(get_db)):
    return _status_action(user_id, UserStatus.ACTIVE, current, db)


def _assignment_error(exc: RoleAssignmentSafetyError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "message": exc.message, **exc.details})


@router.get("/users/{user_id}/roles", response_model=UserRolesResponse)
def list_user_roles(
    user_id: UUID,
    current: CurrentUserContext = Depends(require_permission("foundation:users:read")),
    db: Session = Depends(get_db),
) -> UserRolesResponse:
    service = FoundationService(db)
    try:
        assignments = service.list_user_role_assignments(current.tenant.organization_id, user_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return UserRolesResponse(roles=[AssignedRoleResponse(
        id=item.role.id, code=item.role.code, name=item.role.name,
        is_system=item.role.is_system, is_protected=item.role.is_protected,
        assigned_by=RoleAssignerResponse(id=item.assigner.id, full_name=item.assigner.full_name) if item.assigner else None,
        assigned_at=item.assigned_at,
    ) for item in assignments])


@router.get("/users/{user_id}/assignable-roles", response_model=AssignableRolesResponse)
def list_assignable_roles(
    user_id: UUID,
    current: CurrentUserContext = Depends(require_permission("foundation:user_roles:write")),
    db: Session = Depends(get_db),
) -> AssignableRolesResponse:
    service = FoundationService(db)
    try:
        roles, is_self, restricted_count = service.list_assignable_roles(current.tenant.organization_id, user_id, current.user)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AssignableRolesResponse(
        assignable_roles=[AssignableRoleResponse(
            id=role.id, code=role.code, name=role.name, is_system=role.is_system,
            is_protected=role.is_protected, permission_count=len(service.get_role_permissions(role.id)),
        ) for role in roles],
        target_user_id=user_id, is_self=is_self, restricted_count=restricted_count,
        message="You cannot assign roles to yourself" if is_self else None,
    )


@router.post("/users/{user_id}/roles", response_model=RoleAssignmentResponse, status_code=status.HTTP_201_CREATED)
def assign_role_to_user(
    user_id: UUID,
    payload: UserRoleAssignRequest,
    current: CurrentUserContext = Depends(require_permission("foundation:user_roles:write")),
    db: Session = Depends(get_db),
) -> RoleAssignmentResponse:
    service = FoundationService(db)
    try:
        assignment = service.assign_role_to_user_by_ids(current.tenant.organization_id, user_id, payload.role_id, current.user)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RoleAssignmentSafetyError as exc:
        return _assignment_error(exc)
    role = service.get_role_for_tenant(current.tenant.organization_id, payload.role_id)
    return RoleAssignmentResponse(
        message="Role assigned successfully", user_id=user_id,
        role=RoleRef(id=role.id, code=role.code, name=role.name),
        assigned_by=RoleAssignerResponse(id=current.user.id, full_name=current.user.full_name),
        assigned_at=assignment.assigned_at,
    )


@router.delete("/users/{user_id}/roles/{role_id}", response_model=RoleRemovalResponse)
def remove_role_from_user(
    user_id: UUID,
    role_id: UUID,
    current: CurrentUserContext = Depends(require_permission("foundation:user_roles:write")),
    db: Session = Depends(get_db),
) -> RoleRemovalResponse:
    service = FoundationService(db)
    try:
        service.remove_role_from_user(current.tenant.organization_id, user_id, role_id, current.user)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RoleAssignmentSafetyError as exc:
        return _assignment_error(exc)
    return RoleRemovalResponse(message="Role removed successfully", user_id=user_id, role_id=role_id)
