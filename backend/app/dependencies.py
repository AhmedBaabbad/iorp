from collections.abc import Callable, Generator
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser
from app.core.authorization.scoped_policy import ScopedAuthorizationPolicy
from app.core.db import get_db_session
from app.core.permission import has_any_permission, has_permission, has_role
from app.core.security import TokenValidationError, decode_token, record_security_event
from app.core.tenancy import TenantContext
from app.core.interfaces.organization_queries import OrganizationProvisioningInterface
from app.core.interfaces.user_credentials import UserCredentialInterface
from app.core.interfaces.follow_up_queries import FollowUpQueryInterface
from app.core.interfaces.customer_queries import CustomerQueryInterface
from app.core.interfaces.workforce_queries import WorkforceQueryInterface
from app.core.interfaces.platform_email_queries import PlatformEmailQueryInterface
from app.core.interfaces.authorization_policy import AuthorizationContext, AuthorizationPolicy
from app.core.interfaces.activity_log import ActivityLogInterface
from app.core.interfaces.production_demand_lookups import CustomerLookupInterface, QuoteLookupInterface, ProductionDemandCountInterface
from app.foundation.api.schemas import CurrentUserResponse
from app.foundation.application.services import FoundationService
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, User
from app.foundation.infrastructure.organization_queries import FoundationOrganizationQueries
from app.foundation.infrastructure.user_credentials import FoundationUserCredentials
from app.core.storage import LocalFileStorage
from app.platform.domain.enums import PlatformAccountRole, PlatformAccountStatus
from app.platform.domain.permissions import PlatformPermission, has_platform_permission
from app.platform.infrastructure.models import PlatformAccount


bearer_scheme = HTTPBearer(scheme_name="BearerAuth", auto_error=False)


def get_customer_lookup() -> CustomerLookupInterface:
    from app.commercial.infrastructure.lookups import CommercialCustomerLookup
    return CommercialCustomerLookup()


def get_quote_lookup() -> QuoteLookupInterface:
    from app.commercial.infrastructure.lookups import CommercialQuoteLookup
    return CommercialQuoteLookup()


def get_production_demand_count() -> ProductionDemandCountInterface:
    from app.production.infrastructure.demand_repository import ProductionDemandCount
    return ProductionDemandCount()


def get_authorization_policy() -> AuthorizationPolicy:
    """Return the row-level scope policy (own/team/organization).

    Routes that read scoped entities (see SCOPABLE_PERMISSIONS) depend on
    this alongside build_auth_context() to narrow list/get queries.
    """
    return ScopedAuthorizationPolicy()


def build_auth_context(db: Session, tenant: TenantContext, permission_code: str) -> AuthorizationContext:
    """Resolve the caller's effective scope for one permission and package it.

    Callers pass the result to policy.apply_query_filter()/can_access_record().
    """
    from app.core.authorization.scope_resolver import resolve_effective_scope

    scope = resolve_effective_scope(
        db, tenant.user_id, tenant.organization_id, permission_code, tenant.is_organization_root,
    )
    return AuthorizationContext(
        user_id=tenant.user_id,
        organization_id=tenant.organization_id,
        is_organization_root=tenant.is_organization_root,
        permission_code=permission_code,
        effective_scope=scope,
    )


def get_activity_logger() -> ActivityLogInterface:
    from app.foundation.application.activity_log import TenantActivityLogger
    return TenantActivityLogger()


@dataclass(frozen=True)
class CurrentUserContext:
    user: User
    profile: CurrentUserResponse
    auth_user: AuthenticatedUser
    tenant: TenantContext


def get_db() -> Generator[Session, None, None]:
    yield from get_db_session()


def get_organization_queries(
    db: Session = Depends(get_db),
) -> OrganizationProvisioningInterface:
    return FoundationOrganizationQueries(db, LocalFileStorage())


def get_user_credentials(
    db: Session = Depends(get_db),
) -> UserCredentialInterface:
    return FoundationUserCredentials(db)


def get_follow_up_queries(
    db: Session = Depends(get_db),
) -> FollowUpQueryInterface:
    from app.commercial.application.follow_up_query_provider import (
        CommercialFollowUpQueries,
    )

    return CommercialFollowUpQueries(db)


def get_customer_queries(db: Session = Depends(get_db)) -> CustomerQueryInterface:
    from app.commercial.application.customer_query_provider import CommercialCustomerQueries
    return CommercialCustomerQueries(db)


def get_workforce_queries(db: Session = Depends(get_db)) -> WorkforceQueryInterface:
    from app.workforce.application.workforce_query_provider import WorkforceQueries
    return WorkforceQueries(db)


def get_platform_email_queries(db: Session = Depends(get_db)) -> PlatformEmailQueryInterface:
    from app.platform.infrastructure.email_queries import PlatformEmailQueries
    return PlatformEmailQueries(db)


def get_current_platform_account(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> PlatformAccount:
    try:
        payload = decode_token(credentials.credentials, "access") if credentials else None
    except TokenValidationError as exc:
        record_security_event(db, "token_validation_failed", reason=exc.code)
        payload = None
    if not payload or payload.get("account_type") != "platform":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid platform authentication token.",
        )
    try:
        account = db.get(PlatformAccount, UUID(str(payload.get("sub"))))
    except (TypeError, ValueError):
        account = None
    if (
        account is None
        or account.status != PlatformAccountStatus.ACTIVE
        or account.token_version != payload.get("token_version")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid platform authentication token.",
        )
    return account


def require_platform_permission(
    permission: PlatformPermission,
) -> Callable[..., PlatformAccount]:
    def checker(
        request: Request,
        account: PlatformAccount = Depends(get_current_platform_account),
        db: Session = Depends(get_db),
    ) -> PlatformAccount:
        role = PlatformAccountRole.ROOT if account.is_root else account.role
        if not permission.value.startswith("platform:") or not has_platform_permission(role, permission):
            from app.core.audit import AuditActor, PlatformAuditService, audit_request_context
            PlatformAuditService(db).record(
                event_type="platform_permission_denied", category="authorization", outcome="denied", severity="warning",
                actor=AuditActor("platform", account.id, account.email, account.full_name),
                target_type="permission", target_id=permission.value,
                error_code="PLATFORM_PERMISSION_DENIED", request=audit_request_context(request),
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "PLATFORM_PERMISSION_DENIED",
                    "message": f"Required permission: {permission.value}",
                    "permission": permission.value,
                },
            )
        return account

    return checker


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> CurrentUserContext:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials, "access")
    except TokenValidationError as exc:
        record_security_event(db, "token_validation_failed", reason=exc.code)
        payload = None
    if (
        payload is None
        or "sub" not in payload
        or payload.get("account_type") != "tenant"
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )

    try:
        user_id = UUID(str(payload["sub"]))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        ) from exc

    service = FoundationService(db)
    user = service.get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )

    if payload.get("organization_id") != str(user.organization_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid tenant authentication scope.",
        )

    if user.status != UserStatus.ACTIVE:
        from app.core.account_access import AccountAccessError
        if user.status == UserStatus.LOCKED:
            raise AccountAccessError("ACCOUNT_LOCKED", "Your account has been locked. Contact your administrator.")
        raise AccountAccessError("ACCOUNT_INACTIVE", "Your account is inactive. Contact your administrator.")

    if payload.get("token_version") != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "SESSION_INVALIDATED", "message": "Session expired. Please log in again."},
        )

    organization = service.get_organization(user.organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Organization not found.",
        )
    if organization.status != OrganizationStatus.ACTIVE:
        from app.core.organization_access import OrganizationAccessError
        raise OrganizationAccessError(organization.status.value)

    try:
        profile = service.build_current_user_response(user)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user context.",
        ) from exc

    roles = frozenset(profile.roles)
    permissions = frozenset(profile.permissions)
    return CurrentUserContext(
        user=user,
        profile=profile,
        auth_user=AuthenticatedUser(
            user_id=user.id,
            organization_id=user.organization_id,
            email=user.email,
            roles=roles,
            permissions=permissions,
        ),
        tenant=TenantContext(
            user_id=user.id,
            organization_id=user.organization_id,
            roles=roles,
            permissions=permissions,
            is_organization_root=user.is_organization_root,
        ),
    )


def require_permission(permission_code: str):
    def dependency(
        current: CurrentUserContext = Depends(get_current_user),
    ) -> CurrentUserContext:
        root_can_access = (
            current.user.is_organization_root
            and not permission_code.startswith("platform:")
        )
        if not root_can_access and not has_permission(current.auth_user, permission_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {permission_code}",
            )
        return current

    dependency.permission_policy = ("all", (permission_code,))
    return dependency


def require_any_permission(permission_codes: list[str]):
    def dependency(
        current: CurrentUserContext = Depends(get_current_user),
    ) -> CurrentUserContext:
        root_can_access = current.user.is_organization_root and any(
            not code.startswith("platform:") for code in permission_codes
        )
        if not root_can_access and not has_any_permission(current.auth_user, permission_codes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing required permission.",
            )
        return current

    dependency.permission_policy = ("any", tuple(permission_codes))
    return dependency


def permission_checked_in_handler(*permission_codes: str):
    """Declares a route whose permission depends on the request (an action, a report, a section).

    It enforces nothing itself: the handler checks one of these codes. It makes the policy
    visible, so every route either requires a permission or names the ones it checks.
    """
    def dependency() -> None:
        return None

    dependency.permission_policy = ("in_handler", tuple(permission_codes))
    return dependency


def require_role(role_code: str):
    def dependency(
        current: CurrentUserContext = Depends(get_current_user),
    ) -> CurrentUserContext:
        if not has_role(current.auth_user, role_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role.",
            )
        return current

    return dependency


def get_current_organization_id(
    current: CurrentUserContext = Depends(get_current_user),
) -> UUID:
    return current.user.organization_id


def get_current_tenant(
    current: CurrentUserContext = Depends(get_current_user),
) -> TenantContext:
    return current.tenant


def get_current_authenticated_user(
    current: CurrentUserContext = Depends(get_current_user),
) -> AuthenticatedUser:
    return current.auth_user


def get_current_organization(
    current: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Organization:
    service = FoundationService(db)
    organization = service.get_organization(current.user.organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current organization not found.",
        )
    return organization
