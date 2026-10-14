from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.interfaces.follow_up_queries import FollowUpQueryInterface
from app.core.interfaces.customer_queries import CustomerQueryInterface
from app.core.interfaces.workforce_queries import WorkforceQueryInterface
from app.core.account_access import AccountAccessError
from app.core.interfaces.platform_email_queries import PlatformEmailQueryInterface
from app.core.exceptions import EmailAlreadyExistsError
from app.core.security import active_sessions, decode_token, describe_device, end_sessions, has_usable_password, hash_password, issue_token_pair, known_device, normalize_email, revoke_account_sessions, unusable_password_hash, verify_password
from app.core.password_policy import validate_password
from app.core.organization_access import ensure_organization_access
from app.core.config import settings
from app.core.login_protection import (
    InvalidCredentialsError,
    LoginProtectionError,
    clear_expired_lock,
    ensure_not_auto_locked,
    record_failed_login,
    record_successful_login,
)
from app.core.tenancy import TenantContext
from app.core.utils import utc_now
from app.foundation.domain.permission_catalog import ALL_PERMISSION_CODES, SCOPABLE_PERMISSIONS
from app.foundation.api.schemas import (
    CurrentUserResponse,
    CurrentUserOrganization,
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
    OrganizationCreate,
    PermissionGroupResponse,
    PermissionItem,
    PermissionCreate,
    RoleCreate,
    RoleCreateRequest,
    RolePermissionAssign,
    RoleUpdateRequest,
    UserCreate,
    UserCreateRequest,
    UserRoleAssign,
    UserUpdateRequest,
    UserProfileResponse,
    UserProfileUpdate,
)
from app.foundation.infrastructure.models import (
    Organization,
    Permission,
    Role,
    RolePermission,
    RoleAssignmentRemoval,
    User,
    UserRole,
)
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.domain.user_lifecycle import DeactivationImpact, validate_user_transition
from app.foundation.application import notices
from app.foundation.application.account_alerts import alert_email_change
from app.foundation.application.audit import (
    ROLE_ASSIGNED, ROLE_CREATED, ROLE_DELETED, ROLE_PERMISSIONS_UPDATED, ROLE_REMOVED, ROLE_UPDATED,
    USER_ACTIVATED, USER_CREATED, USER_DEACTIVATED, USER_LOCKED, USER_PASSWORD_CHANGED,
    USER_AUTO_LOCKED, USER_PASSWORD_RESET, USER_UNLOCKED, USER_UPDATED, log_tenant_audit,
)
from app.foundation.application.security_log import (
    TENANT_SESSIONS_ENDED,
    TENANT_ACCOUNT_LOCKED, TENANT_ACCOUNT_UNLOCKED, TENANT_AUTO_LOCKED,
    TENANT_LOGIN_FAILED,
    TENANT_LOGIN_SUCCESS,
    TENANT_PASSWORD_CHANGED,
    log_tenant_security,
)
from app.foundation.infrastructure.repositories import (
    OrganizationRepository,
    PermissionRepository,
    RoleRepository,
    RolePermissionRepository,
    UserRepository,
    UserRoleRepository,
)




class PasswordResetEmailError(RuntimeError):
    """SEC-002: the reset e-mail could not be sent (no mail service, or a wrong address): the administrator corrects the
    user's e-mail (both addresses are alerted) or the mail settings, then sends the link again."""

class RoleGovernanceError(Exception):
    def __init__(self, code: str, message: str, status_code: int, user_count: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.user_count = user_count


class RoleAssignmentSafetyError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 403, **details) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class UserHasOpenFollowUpsError(ValueError):
    def __init__(self, user_id: UUID, open_follow_up_count: int) -> None:
        super().__init__("User has open follow-ups that must be reassigned before deactivation.")
        self.user_id = user_id
        self.open_follow_up_count = open_follow_up_count


class UserHasOpenDependenciesError(ValueError):
    def __init__(self, impact: DeactivationImpact) -> None:
        self.impact = impact
        super().__init__(f"User has {impact.total_blocking_items} open dependencies that must be resolved before deactivation.")


class OrganizationRootProtectionError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def _cannot_delete_root() -> OrganizationRootProtectionError:
    return OrganizationRootProtectionError(
        403,
        "CANNOT_DELETE_ORGANIZATION_ROOT",
        "Organization Root account cannot be deleted",
    )


def _cannot_deactivate_root() -> OrganizationRootProtectionError:
    return OrganizationRootProtectionError(
        403,
        "CANNOT_DEACTIVATE_ORGANIZATION_ROOT",
        "Organization Root account cannot be deactivated",
    )


def _cannot_modify_root_identity() -> OrganizationRootProtectionError:
    return OrganizationRootProtectionError(
        403,
        "CANNOT_MODIFY_ROOT_IDENTITY",
        "Organization Root name and email cannot be changed",
    )


class FoundationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.organizations = OrganizationRepository(db)
        self.users = UserRepository(db)
        self.roles = RoleRepository(db)
        self.permissions = PermissionRepository(db)
        self.role_permissions = RolePermissionRepository(db)
        self.user_roles = UserRoleRepository(db)

    def create_organization(self, data: OrganizationCreate) -> Organization:
        organization = Organization(**data.model_dump())
        self.organizations.add(organization)
        self.db.commit()
        self.db.refresh(organization)
        return organization

    def get_organization(self, organization_id: UUID) -> Organization | None:
        return self.organizations.get(organization_id)

    def list_organizations(self) -> list[Organization]:
        return self.organizations.list_all()

    def create_user(
        self,
        organization_id: UUID,
        data: UserCreate,
        platform_emails: PlatformEmailQueryInterface | None = None,
    ) -> User:
        payload = data.model_dump(exclude={"password"})
        payload["email"] = normalize_email(str(data.email))
        if self.users.get_by_email_global(payload["email"]) or (
            platform_emails and platform_emails.email_exists(payload["email"])
        ):
            raise EmailAlreadyExistsError
        user = User(
            **payload,
            organization_id=organization_id,
            password_hash=hash_password(data.password),
        )
        self.users.add(user)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise EmailAlreadyExistsError from exc
        self.db.refresh(user)
        return user

    def get_user(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    def get_user_by_id_in_organization(
        self,
        user_id: UUID,
        organization_id: UUID,
    ) -> User | None:
        return self.users.get_for_organization(organization_id, user_id)

    def list_users(self, organization_id: UUID) -> list[User]:
        return self.users.list_by_organization(organization_id)

    def list_users_for_tenant(self, tenant: TenantContext) -> list[User]:
        return self.users.list_by_organization(tenant.organization_id)

    def create_role(self, organization_id: UUID, data: RoleCreate) -> Role:
        role = Role(organization_id=organization_id, **data.model_dump())
        self.roles.add(role)
        self._grant_organization_profile_read(role)
        self.db.commit()
        self.db.refresh(role)
        return role

    def get_role(self, role_id: UUID) -> Role | None:
        return self.roles.get(role_id)

    def list_roles(self, organization_id: UUID) -> list[Role]:
        return self.roles.list_by_organization(organization_id)

    def list_roles_for_tenant(self, tenant: TenantContext) -> list[Role]:
        return self.roles.list_by_organization(tenant.organization_id)

    def assign_permission_to_role(self, data: RolePermissionAssign) -> RolePermission:
        role = self.roles.get(data.role_id)
        if role is None:
            raise ValueError("Role not found.")

        permission = self.permissions.get(data.permission_id)
        if permission is None or permission.organization_id != role.organization_id:
            raise ValueError("Permission not found.")

        existing = self.role_permissions.get_by_pair(data.role_id, data.permission_id)
        if existing is not None:
            return existing

        role_permission = RolePermission(**data.model_dump())
        self.role_permissions.add(role_permission)
        self.db.commit()
        self.db.refresh(role_permission)
        return role_permission

    def assign_role_to_user(self, data: UserRoleAssign) -> UserRole:
        user = self.users.get(data.user_id)
        if user is None:
            raise ValueError("User not found.")

        role = self.roles.get(data.role_id)
        if role is None:
            raise ValueError("Role not found.")

        if user.organization_id != role.organization_id:
            raise ValueError("User and role must belong to the same organization.")

        existing = self.user_roles.get_by_pair(data.user_id, data.role_id)
        if existing is not None:
            return existing

        user_role = UserRole(**data.model_dump())
        self.user_roles.add(user_role)
        self.db.commit()
        self.db.refresh(user_role)
        return user_role

    def assign_role_to_user_for_tenant(
        self,
        tenant: TenantContext,
        data: UserRoleAssign,
    ) -> UserRole:
        user = self.users.get(data.user_id)
        if user is None:
            raise ValueError("User not found.")
        if tenant.organization_id != user.organization_id:
            raise ValueError("Resource does not belong to the current organization.")

        role = self.roles.get(data.role_id)
        if role is None:
            raise ValueError("Role not found.")
        if tenant.organization_id != role.organization_id:
            raise ValueError("Resource does not belong to the current organization.")

        return self.assign_role_to_user(data)

    def list_permissions_for_role(self, role_id: UUID) -> list[Permission]:
        return self.role_permissions.list_permissions_for_role(role_id)

    def authenticate_user(self, data: LoginRequest, *, ip: str | None = None, user_agent: str | None = None) -> User | None:
        matches = self.users.list_by_email(normalize_email(str(data.email)))
        if len(matches) != 1:
            verify_password(data.password, None)
            return None

        user = matches[0]
        organization = self.organizations.get(user.organization_id)
        if organization is None:
            return None

        if user.status == UserStatus.LOCKED:
            raise AccountAccessError("ACCOUNT_LOCKED", "Your account has been locked. Contact your administrator.")
        if user.status == UserStatus.INACTIVE:
            raise AccountAccessError("ACCOUNT_INACTIVE", "Your account is inactive. Contact your administrator.")

        ensure_organization_access(organization.status.value)

        clear_expired_lock(self.db, user)
        ensure_not_auto_locked(user)

        if not verify_password(data.password, user.password_hash):
            try:
                failed_attempts = record_failed_login(
                    self.db,
                    user,
                    threshold=settings.login_max_attempts,
                    minutes=settings.login_lockout_minutes,
                    root_exempt=user.is_organization_root,
                )
            except LoginProtectionError:
                log_tenant_security(
                    self.db, user.organization_id, TENANT_AUTO_LOCKED, user.id, user.email, ip, user_agent,
                    details={
                        "failed_login_attempts": user.failed_login_attempts,
                        "auto_locked_until": user.auto_locked_until.isoformat() if user.auto_locked_until else None,
                    },
                )
                self.db.commit()
                raise
            # Every failure is recorded with its device — the root's too, though the root is never locked out.
            log_tenant_security(self.db, user.organization_id, TENANT_LOGIN_FAILED, user.id, user.email, ip, user_agent,
                                details={"failed_login_attempts": failed_attempts})
            self.db.commit()
            if not user.is_organization_root:
                raise InvalidCredentialsError(
                    failed_attempts=failed_attempts,
                    remaining_attempts=max(0, settings.login_max_attempts - failed_attempts),
                )
            return None

        return user

    def login(self, data: LoginRequest, *, ip: str | None = None, user_agent: str | None = None) -> LoginResponse | None:
        user = self.authenticate_user(data, ip=ip, user_agent=user_agent)
        if user is None:
            return None

        record_successful_login(self.db, user)
        log_tenant_security(self.db, user.organization_id, TENANT_LOGIN_SUCCESS,
                            user.id, user.email, ip, user_agent)
        self.db.commit()

        pair = issue_token_pair(
            self.db,
            account_id=user.id,
            account_type="tenant",
            organization_id=user.organization_id,
            token_version=user.token_version,
            ip=ip,
            user_agent=user_agent,
        )
        self._after_sign_in(user, decode_token(pair.access_token, "access")["sid"], ip, user_agent)
        return LoginResponse(access_token=pair.access_token, refresh_token=pair.refresh_token, expires_in=pair.access_expires_in)

    def _after_sign_in(self, user: User, family_id: str, ip: str | None, user_agent: str | None) -> None:
        """SEC-001: the session limit (a sign-in beyond it ends the oldest ones) and a notice of a new device."""
        family = UUID(family_id)
        organization = self.organizations.get(user.organization_id)
        limit = max(1, getattr(organization, "max_sessions_per_user", None) or 2)
        live = active_sessions(self.db, "tenant", user.id)  # newest first, this one included
        oldest = [s for s in live if s["id"] != family][max(0, limit - 1):]
        if oldest:
            end_sessions(self.db, "tenant", user.id, [s["id"] for s in oldest], reason="session_limit")
            log_tenant_security(self.db, user.organization_id, TENANT_SESSIONS_ENDED, user.id, user.email, ip, user_agent,
                                details={"reason": "session_limit", "sessions": len(oldest)})
            notices.sessions_ended_by_limit(self.db, user.organization_id, user.id, len(oldest), limit)
        if known_device(self.db, "tenant", user.id, user_agent, exclude_family=family) is False:
            notices.new_device(self.db, user.organization_id, user.id, describe_device(user_agent), ip)
        self.db.commit()

    def change_password(self, user: User, data: PasswordChangeRequest) -> None:
        if not verify_password(data.current_password, user.password_hash):
            raise ValueError("Current password is incorrect")
        validate_password(
            data.new_password,
            data.new_password_confirmation,
            user.email,
            12 if user.is_organization_root else 8,
        )
        if verify_password(data.new_password, user.password_hash):
            raise ValueError("New password must be different from current password")
        user.password_hash = hash_password(data.new_password)
        user.token_version += 1
        revoke_account_sessions(self.db, "tenant", user.id, reason="password_changed")
        log_tenant_audit(self.db, user.organization_id, USER_PASSWORD_CHANGED, "user", user.id, user.id, user.full_name, user.email, user.full_name, {"password_changed": True, "sessions_invalidated": True, "method": "self_service"})
        log_tenant_security(self.db, user.organization_id, TENANT_PASSWORD_CHANGED,
                            user.id, user.email, details={"sessions_invalidated": True})
        self.db.commit()

    def reset_user_password_for_tenant(self, organization_id: UUID, user_id: UUID, actor: User | None = None) -> dict:
        """SEC-002: e-mails the user a reset link; the user chooses their own password (their sessions end when they do).
        No administrator ever chooses, sees or holds a user's password, not even for a moment. Audited."""
        user = self.get_user_by_id_in_organization(user_id, organization_id)
        if user is None:
            raise LookupError("User not found.")
        if user.is_organization_root:
            raise _cannot_deactivate_root()
        from app.foundation.application.password_reset import TenantPasswordResetService
        if not TenantPasswordResetService().request_reset(self.db, user.email, user.preferred_locale):
            raise PasswordResetEmailError()
        method = "link" if has_usable_password(user.password_hash) else "invitation"  # SEC-003: resent activation
        log_tenant_audit(self.db, organization_id, USER_PASSWORD_RESET, "user", user.id, actor.id if actor else None,
                         actor.full_name if actor else None, actor.email if actor else None, user.full_name, {"method": method})
        self.db.commit()
        return {"method": method, "email": user.email}

    def build_current_user_response(self, user: User) -> CurrentUserResponse:
        organization = self.organizations.get(user.organization_id)
        if organization is None:
            raise ValueError("User organization not found.")

        roles = self.user_roles.list_roles_for_user(user.id, user.organization_id)
        permissions = (
            {
                permission.code
                for permission in self.permissions.list_by_organization(user.organization_id)
                if not permission.code.startswith("platform:")
            }
            if user.is_organization_root
            else self.permissions.get_permissions_for_user(user.id, user.organization_id)
        )
        if not user.is_organization_root:  # PROJECT-GOV-004: approvals delegated to the user and in force today
            from app.foundation.application.delegation_service import delegated_permissions
            permissions = set(permissions) | delegated_permissions(self.db, user)
        return CurrentUserResponse(
            timezone=user.timezone,
            id=user.id,
            organization_id=user.organization_id,
            organization_code=organization.code,
            organization_name=organization.name,
            organization_timezone=organization.timezone,
            organization_logo_url=(
                "/api/v1/organization/logo"
                if organization.logo_path
                else None
            ),
            full_name=user.full_name,
            email=user.email,
            phone=user.phone,
            preferred_locale=user.preferred_locale,
            effective_locale=user.preferred_locale or organization.default_locale,
            status=user.status,
            is_organization_root=user.is_organization_root,
            roles=[role.code for role in roles],
            permissions=sorted(permissions),
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            organization=CurrentUserOrganization(
                id=organization.id,
                name=organization.name,
                code=organization.code,
                has_logo=bool(organization.logo_path),
                logo_url="/api/v1/organization/logo" if organization.logo_path else None,
                default_locale=organization.default_locale,
            ),
        )

    def get_my_profile(self, user: User) -> UserProfileResponse:
        organization = self.organizations.get(user.organization_id)
        if organization is None:
            raise ValueError("User organization not found.")
        roles = self.user_roles.list_roles_for_user(user.id, user.organization_id)
        return UserProfileResponse(
            timezone=user.timezone,
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            phone=user.phone,
            preferred_locale=user.preferred_locale,
            effective_locale=user.preferred_locale or organization.default_locale,
            organization_id=user.organization_id,
            organization_name=organization.name,
            organization_code=organization.code,
            is_organization_root=user.is_organization_root,
            status=user.status,
            roles=[role.code for role in roles],
            last_login_at=user.last_login_at,
            created_at=user.created_at,
        )

    def update_my_profile(self, user: User, data: UserProfileUpdate) -> UserProfileResponse:
        if "timezone" in data.model_fields_set and data.timezone:
            from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
            try:
                ZoneInfo(data.timezone)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise ValueError("Invalid timezone.") from exc
        before = {field: getattr(user, field) for field in ("full_name", "phone", "preferred_locale", "timezone")}
        if (
            user.is_organization_root
            and "full_name" in data.model_fields_set
            and data.full_name is not None
            and data.full_name != user.full_name
        ):
            raise _cannot_modify_root_identity()
        if data.preferred_locale not in (None, "ar", "en"):
            raise ValueError("Invalid preferred locale.")
        if "full_name" in data.model_fields_set and data.full_name is not None:
            user.full_name = data.full_name
        if "timezone" in data.model_fields_set:
            user.timezone = data.timezone or None
        if "phone" in data.model_fields_set:
            user.phone = data.phone
        if "preferred_locale" in data.model_fields_set:
            user.preferred_locale = data.preferred_locale
        changes = {field: {"before": before[field], "after": getattr(user, field)} for field in before if before[field] != getattr(user, field)}
        if changes:
            log_tenant_audit(self.db, user.organization_id, USER_UPDATED, "user", user.id, user.id, user.full_name, user.email, user.full_name, changes)
        self.db.commit()
        self.db.refresh(user)
        return self.get_my_profile(user)

    # ── User management ───────────────────────────────────────────────────────

    def create_user_for_tenant(self, organization_id: UUID, data: UserCreateRequest, platform_emails: PlatformEmailQueryInterface | None = None, actor: User | None = None) -> User:
        email = normalize_email(str(data.email))
        if self.users.get_by_email_global(email) is not None or (platform_emails and platform_emails.email_exists(email)):
            raise EmailAlreadyExistsError
        roles_to_assign = []
        for role_code in data.role_codes:
            role = self.roles.get_by_code(organization_id, role_code)
            if role is None:
                raise LookupError(f"Role not found: {role_code}")
            roles_to_assign.append(role)
        user = User(
            organization_id=organization_id,
            full_name=data.full_name,
            email=email,
            phone=data.phone,
            preferred_locale=data.preferred_locale,
            password_hash=unusable_password_hash(),  # SEC-003: the user chooses it through the activation link
            status=UserStatus.ACTIVE,
        )
        self.users.add(user)
        self.db.flush()
        for role in roles_to_assign:
            existing_role = self.user_roles.get_by_pair(user.id, role.id)
            if existing_role is None:
                self.user_roles.add(UserRole(user_id=user.id, role_id=role.id))
        log_tenant_audit(self.db, organization_id, USER_CREATED, "user", user.id, actor.id if actor else None, actor.full_name if actor else None, actor.email if actor else None, user.full_name, {"full_name": user.full_name, "email": user.email, "role_codes": data.role_codes})
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise EmailAlreadyExistsError from exc
        self.db.refresh(user)
        return user

    def send_activation_link(self, user: User) -> bool:
        """SEC-003: e-mails a new user their activation link (valid ACCOUNT_INVITATION_EXPIRY_HOURS); True when it went out."""
        from app.foundation.application.password_reset import TenantPasswordResetService
        return TenantPasswordResetService().request_reset(self.db, user.email, user.preferred_locale)

    def update_user(self, user: User, data: UserUpdateRequest, platform_emails: PlatformEmailQueryInterface | None = None, actor: User | None = None) -> User:
        # Personal information belongs to the account owner, including when an administrator
        # targets their own account. Self-service uses update_my_profile instead.
        raise ValueError("Personal details can only be changed through the account owner's profile.")

    def update_user_for_tenant(
        self,
        organization_id: UUID,
        actor_user_id: UUID,
        user_id: UUID,
        data: UserUpdateRequest,
        follow_up_queries: FollowUpQueryInterface,
        platform_emails: PlatformEmailQueryInterface | None = None,
    ) -> User:
        user = self.get_user_by_id_in_organization(user_id, organization_id)
        if user is None:
            raise LookupError("User not found.")
        actor = self.get_user_by_id_in_organization(actor_user_id, organization_id)
        return self.update_user(user, data, platform_emails, actor)

    def soft_delete_user(self, user: User) -> None:
        if user.is_organization_root:
            raise _cannot_deactivate_root()
        user.status = UserStatus.INACTIVE
        self.db.commit()

    def deactivate_user_for_tenant(
        self,
        organization_id: UUID,
        actor_user_id: UUID,
        user_id: UUID,
        follow_up_queries: FollowUpQueryInterface,
        customer_queries: CustomerQueryInterface,
        workforce_queries: WorkforceQueryInterface,
    ) -> User:
        user = self.get_user_by_id_in_organization(user_id, organization_id)
        if user is None:
            raise LookupError("User not found.")
        if user.is_organization_root:
            raise _cannot_deactivate_root()
        if user_id == actor_user_id:
            raise ValueError("You cannot change your own status.")
        impact = self.get_user_deactivation_impact(organization_id, user_id, follow_up_queries, customer_queries, workforce_queries)
        if not impact.can_deactivate:
            raise UserHasOpenDependenciesError(impact)
        validate_user_transition(user.status, UserStatus.INACTIVE)
        user.status = UserStatus.INACTIVE
        user.token_version += 1
        revoke_account_sessions(self.db, "tenant", user.id, reason="account_inactive")
        actor = self.get_user_by_id_in_organization(actor_user_id, organization_id)
        log_tenant_audit(self.db, organization_id, USER_DEACTIVATED, "user", user.id, actor_user_id, actor.full_name if actor else None, actor.email if actor else None, user.full_name, {"reason": user.account_change_reason, "status": {"before": "active", "after": "inactive"}})
        self.db.commit(); self.db.refresh(user)
        return user

    def get_user_deactivation_impact(
        self,
        organization_id: UUID,
        user_id: UUID,
        follow_up_queries: FollowUpQueryInterface,
        customer_queries: CustomerQueryInterface,
        workforce_queries: WorkforceQueryInterface,
    ) -> DeactivationImpact:
        user = self.get_user_by_id_in_organization(user_id, organization_id)
        if user is None:
            raise LookupError("User not found.")
        return DeactivationImpact(
            user_id=user.id,
            user_full_name=user.full_name,
            open_follow_ups=follow_up_queries.count_open_follow_ups_for_user(user_id, organization_id),
            assigned_customers=customer_queries.count_assigned_customers(user_id, organization_id),
            active_workforce_link=workforce_queries.has_linked_member(user_id, organization_id),
        )

    def change_user_status_for_tenant(self, organization_id: UUID, actor_user_id: UUID, user_id: UUID, target: UserStatus) -> User:
        user = self.get_user_by_id_in_organization(user_id, organization_id)
        if user is None:
            raise LookupError("User not found.")
        if user.is_organization_root:
            raise _cannot_deactivate_root()
        if user.id == actor_user_id:
            raise ValueError("You cannot change your own status.")
        previous = user.status.value
        if user.archived_at is not None:
            raise ValueError("Archived accounts cannot be reactivated. Restore the archive first.")
        validate_user_transition(user.status, target)
        user.status = target
        if target in {UserStatus.LOCKED, UserStatus.INACTIVE}:
            user.token_version += 1
            revoke_account_sessions(self.db, "tenant", user.id, reason=f"account_{target.value}")
        actor = self.get_user_by_id_in_organization(actor_user_id, organization_id)
        action = USER_LOCKED if target == UserStatus.LOCKED else USER_UNLOCKED if previous == UserStatus.LOCKED.value else USER_ACTIVATED
        log_tenant_audit(self.db, organization_id, action, "user", user.id, actor_user_id, actor.full_name if actor else None, actor.email if actor else None, user.full_name, {"reason": user.account_change_reason, "status": {"before": previous, "after": target.value}})
        if target == UserStatus.LOCKED:
            log_tenant_security(self.db, organization_id, TENANT_ACCOUNT_LOCKED, user.id, user.email,
                                details={"performed_by": str(actor_user_id)})
        elif previous == UserStatus.LOCKED.value:
            log_tenant_security(self.db, organization_id, TENANT_ACCOUNT_UNLOCKED, user.id, user.email,
                                details={"performed_by": str(actor_user_id)})
            notices.account_unlocked(self.db, organization_id, user.id, actor_user_id)
        self.db.commit(); self.db.refresh(user)
        return user

    def _ensure_user_can_be_deactivated(
        self,
        user_id: UUID,
        organization_id: UUID,
        follow_up_queries: FollowUpQueryInterface,
    ) -> None:
        count = follow_up_queries.count_open_follow_ups_for_user(
            user_id,
            organization_id,
        )
        if count > 0:
            raise UserHasOpenFollowUpsError(user_id, count)

    def set_organization_root_status(
        self,
        organization_id: UUID,
        user_id: UUID,
        is_organization_root: bool,
    ) -> User:
        """Internal system operation; intentionally not exposed by tenant schemas/routes."""
        user = self.get_user_by_id_in_organization(user_id, organization_id)
        if user is None:
            raise LookupError("User not found.")
        if not is_organization_root and user.is_organization_root:
            remaining = self.users.count_organization_roots(
                organization_id,
                exclude_user_id=user.id,
            )
            if remaining == 0:
                raise OrganizationRootProtectionError(
                    409,
                    "LAST_ORGANIZATION_ROOT",
                    "Cannot remove root status from the last Organization Root",
                )
        user.is_organization_root = is_organization_root
        if is_organization_root:
            user.status = UserStatus.ACTIVE
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_user_effective_permission_codes(self, user: User, organization_id: UUID) -> set[str]:
        if user.organization_id != organization_id:
            raise LookupError("User not found.")
        if user.is_organization_root:
            return set(ALL_PERMISSION_CODES)
        return self.permissions.get_permissions_for_user(user.id, organization_id)

    def get_role_permission_codes(self, role_id: UUID, organization_id: UUID) -> set[str]:
        return {
            permission.code
            for permission in self.role_permissions.list_permissions_for_role_in_organization(
                organization_id, role_id,
            )
        }

    def assign_role_to_user_by_ids(self, organization_id: UUID, user_id: UUID, role_id: UUID, current_user: User) -> UserRole:
        user = self.users.get_for_organization(organization_id, user_id)
        if user is None:
            raise LookupError("User not found.")
        role = self.roles.get_for_organization(organization_id, role_id)
        if role is None:
            raise LookupError("Role not found.")
        if user.id == current_user.id:
            raise RoleAssignmentSafetyError("SELF_ROLE_ASSIGNMENT", "You cannot assign roles to yourself. Ask another administrator.")
        existing = self.user_roles.get_by_pair_for_organization(organization_id, user_id, role_id)
        if existing is not None:
            raise RoleAssignmentSafetyError("ROLE_ALREADY_ASSIGNED", "User already has this role", 409)
        if not current_user.is_organization_root:
            role_permissions = self.get_role_permission_codes(role.id, organization_id)
            caller_permissions = self.get_user_effective_permission_codes(current_user, organization_id)
            escalation = sorted(role_permissions - caller_permissions)
            if role.code == "organization_admin" or escalation:
                raise RoleAssignmentSafetyError("PRIVILEGE_ESCALATION", "Cannot assign a role with permissions you do not have", escalated_permissions=escalation)
        user_role = UserRole(user_id=user_id, role_id=role_id, assigned_by=current_user.id, assigned_at=utc_now())
        self.user_roles.add(user_role)
        log_tenant_audit(self.db, organization_id, ROLE_ASSIGNED, "role_assignment", user.id, current_user.id, current_user.full_name, current_user.email, user.full_name, {"user_name": user.full_name, "role_code": role.code, "role_name": role.name})
        notices.role_assigned(self.db, organization_id, user.id, role, current_user.id)
        self.db.commit()
        self.db.refresh(user_role)
        return user_role

    def remove_role_from_user(self, organization_id: UUID, user_id: UUID, role_id: UUID, current_user: User) -> None:
        user = self.users.get_for_organization(organization_id, user_id)
        if user is None:
            raise LookupError("User not found.")
        role = self.roles.get_for_organization(organization_id, role_id)
        if role is None:
            raise LookupError("Role not found.")
        if user.is_organization_root:
            raise RoleAssignmentSafetyError("CANNOT_REMOVE_ROOT_ROLE", "Roles cannot be removed from the Organization Root account")
        if user.id == current_user.id:
            raise RoleAssignmentSafetyError("SELF_ROLE_REMOVAL", "You cannot remove roles from yourself. Ask another administrator.")
        user_role = self.user_roles.get_by_pair_for_organization(organization_id, user_id, role_id)
        if user_role is None:
            raise RoleAssignmentSafetyError("ROLE_NOT_ASSIGNED", "User does not have this role", 404)
        self.db.add(RoleAssignmentRemoval(user_id=user.id, role_id=role.id, removed_by=current_user.id, removed_at=utc_now()))
        self.db.delete(user_role)
        log_tenant_audit(self.db, organization_id, ROLE_REMOVED, "role_assignment", user.id, current_user.id, current_user.full_name, current_user.email, user.full_name, {"user_name": user.full_name, "role_code": role.code, "role_name": role.name})
        notices.role_removed(self.db, organization_id, user.id, role, current_user.id)
        self.db.commit()

    def list_user_role_assignments(self, organization_id: UUID, user_id: UUID) -> list[UserRole]:
        user = self.users.get_for_organization(organization_id, user_id)
        if user is None:
            raise LookupError("User not found.")
        return self.user_roles.list_assignments_for_user(user_id, organization_id)

    def list_assignable_roles(self, organization_id: UUID, target_user_id: UUID, current_user: User) -> tuple[list[Role], bool, int]:
        target = self.users.get_for_organization(organization_id, target_user_id)
        if target is None:
            raise LookupError("User not found.")
        if target.id == current_user.id:
            return [], True, 0
        assigned = {assignment.role_id for assignment in self.user_roles.list_assignments_for_user(target.id, organization_id)}
        available = [role for role in self.roles.list_by_organization(organization_id) if role.id not in assigned]
        if current_user.is_organization_root:
            return available, False, 0
        caller_permissions = self.get_user_effective_permission_codes(current_user, organization_id)
        assignable = [role for role in available if role.code != "organization_admin" and self.get_role_permission_codes(role.id, organization_id) <= caller_permissions]
        return assignable, False, len(available) - len(assignable)

    def get_user_roles(self, user_id: UUID, organization_id: UUID) -> list[Role]:
        return self.user_roles.list_roles_for_user(user_id, organization_id)

    def get_user_permissions(self, user_id: UUID, organization_id: UUID) -> list[Permission]:
        user = self.users.get_for_organization(organization_id, user_id)
        if (
            user is not None
            and user.organization_id == organization_id
            and user.is_organization_root
        ):
            return [
                permission
                for permission in self.permissions.list_by_organization(organization_id)
                if not permission.code.startswith("platform:")
            ]
        return self.permissions.list_for_user(user_id, organization_id)

    # ── Role management ───────────────────────────────────────────────────────

    def create_role_for_tenant(self, organization_id: UUID, data: RoleCreateRequest, actor: User | None = None) -> Role:
        code = data.code.strip().lower()
        existing = self.roles.get_by_code(organization_id, code)
        if existing is not None:
            raise ValueError("A role with this code already exists in this organization.")
        role = Role(
            organization_id=organization_id,
            name=data.name,
            code=code,
            description=data.description,
            is_system=False,
            is_protected=False,
            is_editable=True,
        )
        self.roles.add(role)
        self._grant_organization_profile_read(role)
        self.db.flush()
        log_tenant_audit(self.db, organization_id, ROLE_CREATED, "role", role.id, actor.id if actor else None, actor.full_name if actor else None, actor.email if actor else None, role.name, {"code": role.code, "name": role.name})
        self.db.commit()
        self.db.refresh(role)
        return role

    def _grant_organization_profile_read(self, role: Role) -> None:
        permission = self.permissions.get_by_code(role.organization_id, "foundation:organization:read")
        if permission is not None:
            self.role_permissions.add(
                RolePermission(role_id=role.id, permission_id=permission.id)
            )

    def update_role(self, role: Role, data: RoleUpdateRequest, actor: User | None = None) -> Role:
        before = {field: getattr(role, field) for field in ("code", "name", "description")}
        if not role.is_editable:
            raise RoleGovernanceError("ROLE_NOT_EDITABLE", "This system role cannot be edited.", 403)
        if data.code is not None and data.code != role.code:
            existing = self.roles.get_by_code(role.organization_id, data.code)
            if existing is not None and existing.id != role.id:
                raise RoleGovernanceError("ROLE_CODE_ALREADY_EXISTS", "A role with this code already exists.", 409)
            role.code = data.code
        if data.name is not None:
            role.name = data.name
        if data.description is not None:
            role.description = data.description
        changes = {field: {"before": before[field], "after": getattr(role, field)} for field in before if before[field] != getattr(role, field)}
        if changes:
            log_tenant_audit(self.db, role.organization_id, ROLE_UPDATED, "role", role.id, actor.id if actor else None, actor.full_name if actor else None, actor.email if actor else None, role.name, changes)
        self.db.commit()
        self.db.refresh(role)
        return role

    def get_role_for_tenant(self, organization_id: UUID, role_id: UUID) -> Role:
        role = self.roles.get_for_organization(organization_id, role_id)
        if role is None:
            raise LookupError("Role not found.")
        return role

    def update_role_for_tenant(
        self,
        organization_id: UUID,
        role_id: UUID,
        data: RoleUpdateRequest,
        actor: User | None = None,
    ) -> Role:
        return self.update_role(self.get_role_for_tenant(organization_id, role_id), data, actor)

    def delete_role_for_tenant(self, organization_id: UUID, role_id: UUID, actor: User | None = None) -> None:
        self.delete_role(self.get_role_for_tenant(organization_id, role_id), actor)

    def delete_role(self, role: Role, actor: User | None = None) -> None:
        if role.is_protected:
            raise RoleGovernanceError("ROLE_IS_PROTECTED", "Protected roles cannot be deleted.", 403)
        if role.is_system:
            raise RoleGovernanceError("SYSTEM_ROLE_CANNOT_BE_DELETED", "System roles cannot be deleted.", 403)
        user_count = self.user_roles.count_for_role(role.id)
        if user_count > 0:
            raise RoleGovernanceError("ROLE_HAS_ASSIGNED_USERS", "Cannot delete a role with assigned users.", 409, user_count)
        log_tenant_audit(self.db, role.organization_id, ROLE_DELETED, "role", role.id, actor.id if actor else None, actor.full_name if actor else None, actor.email if actor else None, role.name, {"code": role.code, "name": role.name})
        self.db.delete(role)
        self.db.commit()

    def assign_permission_to_role_by_ids(self, organization_id: UUID, role_id: UUID, permission_id: UUID) -> RolePermission:
        role = self.roles.get_for_organization(organization_id, role_id)
        if role is None:
            raise ValueError("Role not found.")
        permission = self.permissions.get_for_organization(organization_id, permission_id)
        if permission is None:
            raise ValueError("Permission not found.")
        existing = self.role_permissions.get_by_pair_for_organization(organization_id, role_id, permission_id)
        if existing is not None:
            return existing
        rp = RolePermission(role_id=role_id, permission_id=permission_id)
        self.role_permissions.add(rp)
        self.db.commit()
        self.db.refresh(rp)
        return rp

    def assign_permission_to_role_by_code(
        self,
        organization_id: UUID,
        role_id: UUID,
        permission_code: str,
        actor: User | None = None,
        scope: str = "organization",
    ) -> RolePermission:
        role = self.roles.get_for_organization(organization_id, role_id)
        if role is None:
            raise LookupError("Role not found.")
        if not role.is_editable:
            raise RoleGovernanceError("ROLE_NOT_EDITABLE", "This system role's permissions cannot be edited.", 403)
        permission = self.permissions.get_by_code(organization_id, permission_code)
        if permission is None:
            raise LookupError("Permission not found.")
        if scope not in ("own", "team", "organization"):
            raise RoleGovernanceError("INVALID_SCOPE", "Scope must be one of: own, team, organization.", 400)
        if scope != "organization" and permission_code not in SCOPABLE_PERMISSIONS:
            raise RoleGovernanceError("SCOPE_NOT_SUPPORTED", f"Permission '{permission_code}' does not support scoping.", 400)
        existing = self.role_permissions.get_by_pair_for_organization(organization_id, role_id, permission.id)
        if existing is not None:
            raise ValueError("Permission is already assigned to this role.")
        rp = RolePermission(role_id=role_id, permission_id=permission.id, scope=scope)
        self.role_permissions.add(rp)
        log_tenant_audit(self.db, organization_id, ROLE_PERMISSIONS_UPDATED, "role", role.id, actor.id if actor else None, actor.full_name if actor else None, actor.email if actor else None, role.name, {"permission": permission.code, "operation": "added", "scope": scope})
        notices.role_permissions_changed(self.db, organization_id, role, actor.id if actor else None)
        self.db.commit()
        self.db.refresh(rp)
        return rp

    def update_role_permission_scope_by_code(
        self,
        organization_id: UUID,
        role_id: UUID,
        permission_code: str,
        scope: str,
        actor: User | None = None,
    ) -> RolePermission:
        role = self.roles.get_for_organization(organization_id, role_id)
        if role is None:
            raise LookupError("Role not found.")
        if not role.is_editable:
            raise RoleGovernanceError("ROLE_NOT_EDITABLE", "This system role's permissions cannot be edited.", 403)
        permission = self.permissions.get_by_code(organization_id, permission_code)
        if permission is None:
            raise LookupError("Permission not found.")
        if scope not in ("own", "team", "organization"):
            raise RoleGovernanceError("INVALID_SCOPE", "Scope must be one of: own, team, organization.", 400)
        if scope != "organization" and permission_code not in SCOPABLE_PERMISSIONS:
            raise RoleGovernanceError("SCOPE_NOT_SUPPORTED", f"Permission '{permission_code}' does not support scoping.", 400)
        rp = self.role_permissions.get_by_pair_for_organization(organization_id, role_id, permission.id)
        if rp is None:
            raise LookupError("Role does not have this permission.")
        previous_scope = rp.scope
        rp.scope = scope
        log_tenant_audit(self.db, organization_id, ROLE_PERMISSIONS_UPDATED, "role", role.id, actor.id if actor else None, actor.full_name if actor else None, actor.email if actor else None, role.name, {"permission": permission.code, "operation": "scope_changed", "scope": {"before": previous_scope, "after": scope}})
        notices.role_permissions_changed(self.db, organization_id, role, actor.id if actor else None)
        self.db.commit()
        self.db.refresh(rp)
        return rp

    def remove_permission_from_role(self, organization_id: UUID, role_id: UUID, permission_id: UUID) -> None:
        role = self.roles.get_for_organization(organization_id, role_id)
        if role is None:
            raise ValueError("Role not found.")
        rp = self.role_permissions.get_by_pair_for_organization(organization_id, role_id, permission_id)
        if rp is None:
            raise ValueError("Role does not have this permission.")
        self.db.delete(rp)
        self.db.commit()

    def remove_permission_from_role_by_code(
        self,
        organization_id: UUID,
        role_id: UUID,
        permission_code: str,
        actor: User | None = None,
    ) -> None:
        role = self.roles.get_for_organization(organization_id, role_id)
        if role is None:
            raise LookupError("Role not found.")
        if not role.is_editable:
            raise RoleGovernanceError("ROLE_NOT_EDITABLE", "This system role's permissions cannot be edited.", 403)
        permission = self.permissions.get_by_code(organization_id, permission_code)
        if permission is None:
            raise LookupError("Permission not found.")
        rp = self.role_permissions.get_by_pair_for_organization(organization_id, role_id, permission.id)
        if rp is None:
            raise LookupError("Role does not have this permission.")
        self.db.delete(rp)
        log_tenant_audit(self.db, organization_id, ROLE_PERMISSIONS_UPDATED, "role", role.id, actor.id if actor else None, actor.full_name if actor else None, actor.email if actor else None, role.name, {"permission": permission.code, "operation": "removed"})
        notices.role_permissions_changed(self.db, organization_id, role, actor.id if actor else None)
        self.db.commit()

    def get_role_permissions(self, role_id: UUID) -> list[Permission]:
        return self.role_permissions.list_permissions_for_role(role_id)

    def get_role_permissions_with_scope(self, role_id: UUID) -> list[tuple[Permission, str]]:
        return self.role_permissions.list_permissions_for_role_with_scope(role_id)

    def group_permissions(
        self,
        permissions: list[Permission],
    ) -> list[PermissionGroupResponse]:
        groups: dict[str, list[PermissionItem]] = {}
        for permission in permissions:
            groups.setdefault(permission.module_name, []).append(
                PermissionItem(code=permission.code, name=permission.name, scope="organization")
            )
        return [
            PermissionGroupResponse(module=module, permissions=items)
            for module, items in sorted(groups.items())
        ]

    def group_permissions_with_scope(
        self,
        permission_scope_pairs: list[tuple[Permission, str]],
    ) -> list[PermissionGroupResponse]:
        groups: dict[str, list[PermissionItem]] = {}
        for permission, scope in permission_scope_pairs:
            groups.setdefault(permission.module_name, []).append(
                PermissionItem(
                    code=permission.code, name=permission.name, scope=scope,
                    scopable=permission.code in SCOPABLE_PERMISSIONS,
                )
            )
        return [
            PermissionGroupResponse(module=module, permissions=items)
            for module, items in sorted(groups.items())
        ]

    def count_users_for_role(self, role_id: UUID) -> int:
        return self.user_roles.count_for_role(role_id)

    # ── Permissions ───────────────────────────────────────────────────────────

    def list_permissions_for_organization(self, organization_id: UUID) -> list[Permission]:
        return self.permissions.list_by_organization(organization_id)
