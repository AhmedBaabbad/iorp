import secrets
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import EmailAlreadyExistsError
from app.core.interfaces.organization_queries import (
    OrganizationAdminData,
    OrganizationData,
    OrganizationProvisioningInterface,
    OrganizationSummary,
    ProvisionedOrganization,
    ProvisionedUser,
)
from app.core.security import hash_password, issue_token_pair, normalize_email, revoke_account_sessions, revoke_organization_sessions, verify_password
from app.core.password_policy import validate_password
from app.core.login_protection import LoginProtectionError, clear_expired_lock, ensure_not_auto_locked, record_failed_login, record_successful_login
from app.core.interfaces.user_credentials import UserCredentialInterface
from app.platform.api.schemas import (
    BootstrapInitializeRequest,
    OrganizationAdminInput,
    OrganizationInput,
)
from app.platform.domain.enums import PlatformAccountRole, PlatformAccountStatus
from app.platform.domain.policies import validate_transition
from app.platform.infrastructure.models import BootstrapState, PlatformAccount


class AlreadyInitializedError(RuntimeError):
    pass


class InvalidBootstrapTokenError(RuntimeError):
    pass


class OrganizationNotFoundError(RuntimeError):
    pass


class ArchiveReasonRequiredError(ValueError):
    code = "ARCHIVE_REASON_REQUIRED"


class OrganizationRootNotFoundError(RuntimeError):
    pass


class PlatformAccountNotFoundError(RuntimeError):
    pass


class PlatformEmailTakenError(RuntimeError):
    pass


class LastPlatformRootError(RuntimeError):
    pass


class BootstrapRootProtectedError(RuntimeError):
    pass


def _organization_data(data: OrganizationInput) -> OrganizationData:
    return OrganizationData(
        name=data.name,
        code=data.code,
        industry_type=data.industry_type,
        timezone=data.timezone,
        default_locale=data.default_locale,
        logo_base64=data.logo_base64,
    )


def _administrator_data(data: OrganizationAdminInput) -> OrganizationAdminData:
    return OrganizationAdminData(
        full_name=data.full_name,
        email=normalize_email(str(data.email)),
        phone=data.phone,
        password=data.password,
    )


class BootstrapService:
    def __init__(
        self,
        db: Session,
        organizations: OrganizationProvisioningInterface,
        user_credentials: UserCredentialInterface | None = None,
    ) -> None:
        self.db = db
        self.organizations = organizations
        self.user_credentials = user_credentials

    def status(self) -> bool:
        state = self.db.get(BootstrapState, 1)
        return bool(state and state.is_initialized)

    def initialize(
        self, data: BootstrapInitializeRequest
    ) -> tuple[PlatformAccount, ProvisionedOrganization, ProvisionedUser]:
        existing_state = self.db.get(BootstrapState, 1)
        if existing_state is not None and existing_state.is_initialized:
            raise AlreadyInitializedError
        expected = settings.bootstrap_token or ""
        if not expected or not secrets.compare_digest(data.bootstrap_token, expected):
            raise InvalidBootstrapTokenError
        if self.user_credentials and (
            self.user_credentials.email_exists(str(data.platform_root.email))
            or self.user_credentials.email_exists(str(data.organization_admin.email))
        ):
            raise EmailAlreadyExistsError
        requested_emails = {
            normalize_email(str(data.platform_root.email)),
            normalize_email(str(data.organization_admin.email)),
        }
        if len(requested_emails) != 2 or self.db.scalar(
            select(PlatformAccount.id).where(PlatformAccount.email.in_(requested_emails)).limit(1)
        ) is not None:
            raise EmailAlreadyExistsError
        provisioned_logo: str | None = None
        try:
            state = self.db.scalar(
                select(BootstrapState).where(BootstrapState.id == 1).with_for_update()
            )
            if state is None:
                state = BootstrapState(id=1)
                self.db.add(state)
                self.db.flush()
            if state.is_initialized:
                raise AlreadyInitializedError
            root = PlatformAccount(
                full_name=data.platform_root.full_name,
                email=normalize_email(str(data.platform_root.email)),
                password_hash=hash_password(data.platform_root.password),
                status=PlatformAccountStatus.ACTIVE,
                is_root=True,
                role=PlatformAccountRole.ROOT,
            )
            self.db.add(root)
            self.db.flush()
            organization, admin = self.organizations.create_organization(
                _organization_data(data.organization),
                _administrator_data(data.organization_admin),
            )
            provisioned_logo = organization.logo_path
            state.is_initialized = True
            state.initialized_at = datetime.now(timezone.utc)
            state.initialized_by_platform_account_id = root.id
            state.first_organization_id = organization.id
            self.db.commit()
            return root, organization, admin
        except Exception:
            self.db.rollback()
            if provisioned_logo:
                self.organizations.cleanup_logo(provisioned_logo)
            raise


class PlatformOrganizationService:
    def __init__(
        self,
        db: Session,
        organizations: OrganizationProvisioningInterface,
        user_credentials: UserCredentialInterface | None = None,
    ) -> None:
        self.db = db
        self.organizations = organizations
        self.user_credentials = user_credentials

    def list_organizations(self) -> list[OrganizationSummary]:
        return self.organizations.list_organizations()

    def get_organization(self, organization_id: UUID) -> OrganizationSummary:
        organization = self.organizations.get_organization(organization_id)
        if organization is None:
            raise OrganizationNotFoundError
        return organization

    def get_organization_detail(self, organization_id: UUID):
        organization = self.organizations.get_organization_detail(organization_id)
        if organization is None:
            raise OrganizationNotFoundError
        return organization

    def create_organization(
        self,
        organization_input: OrganizationInput,
        admin_input: OrganizationAdminInput,
    ) -> tuple[ProvisionedOrganization, ProvisionedUser]:
        provisioned_logo: str | None = None
        try:
            normalized_email = normalize_email(str(admin_input.email))
            if self.db.scalar(
                select(PlatformAccount.id).where(PlatformAccount.email == normalized_email).limit(1)
            ) is not None:
                raise EmailAlreadyExistsError
            result = self.organizations.create_organization(
                _organization_data(organization_input),
                _administrator_data(admin_input),
            )
            provisioned_logo = result[0].logo_path
            self.db.commit()
            return result
        except Exception:
            self.db.rollback()
            if provisioned_logo:
                self.organizations.cleanup_logo(provisioned_logo)
            raise

    def change_status(
        self, organization_id: UUID, status: str, changed_by: PlatformAccount, reason: str | None = None
    ) -> OrganizationSummary:
        current = self.organizations.get_organization(organization_id)
        if current is None:
            raise OrganizationNotFoundError
        if status == "archived" and not (reason and reason.strip()):
            raise ArchiveReasonRequiredError("A reason is required when archiving an organization")
        validate_transition(current.status, status)
        organization = self.organizations.set_organization_status(
            organization_id, status, changed_by.id, reason.strip() if reason else None
        )
        if organization is None:
            raise OrganizationNotFoundError
        if status != "active":
            revoke_organization_sessions(self.db, organization_id, reason=f"organization_{status}")
        self.db.commit()
        return organization

    def reset_root_password(
        self,
        organization_id: UUID,
        new_password: str,
        confirmation: str,
    ) -> str:
        if self.organizations.get_organization(organization_id) is None:
            raise OrganizationNotFoundError
        if self.user_credentials is None:
            raise RuntimeError("User credential provider is required")
        root = self.user_credentials.get_organization_root(organization_id)
        if root is None:
            raise OrganizationRootNotFoundError
        validate_password(new_password, confirmation, root.email, 12)
        self.user_credentials.reset_user_password(root.user_id, hash_password(new_password))
        self.db.commit()
        return root.email


class PlatformAuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def login(self, email: str, password: str, *, ip: str | None = None, user_agent: str | None = None):
        account = self.db.scalar(
            select(PlatformAccount).where(PlatformAccount.email == normalize_email(email))
        )
        if not account:
            verify_password(password, None)
            return None
        if account.status != PlatformAccountStatus.ACTIVE:
            raise LoginProtectionError("ACCOUNT_LOCKED", "Your account has been locked. Contact your administrator.")
        clear_expired_lock(self.db, account)
        ensure_not_auto_locked(account)
        if not verify_password(password, account.password_hash):
            record_failed_login(
                self.db,
                account,
                threshold=settings.platform_login_max_attempts,
                minutes=settings.platform_login_lockout_minutes,
                root_exempt=account.is_root,
            )
            return None
        record_successful_login(self.db, account)
        role = PlatformAccountRole.ROOT if account.is_root else account.role
        return issue_token_pair(
            self.db,
            account_id=account.id,
            account_type="platform",
            token_version=account.token_version,
            extra_claims={"account_id": str(account.id), "role": role.value},
            ip=ip,
            user_agent=user_agent,
        )


class PlatformAccountService:
    def __init__(self, db: Session, user_credentials: UserCredentialInterface) -> None:
        self.db = db
        self.user_credentials = user_credentials

    def list_accounts(self) -> list[PlatformAccount]:
        return list(self.db.scalars(select(PlatformAccount).order_by(PlatformAccount.created_at)))

    def get_account(self, account_id: UUID) -> PlatformAccount:
        account = self.db.get(PlatformAccount, account_id)
        if account is None:
            raise PlatformAccountNotFoundError
        return account

    def is_bootstrap_root(self, account_id: UUID) -> bool:
        state = self.db.get(BootstrapState, 1)
        return bool(state and state.initialized_by_platform_account_id == account_id)

    def _email_available(self, email: str, exclude_id: UUID | None = None) -> str:
        normalized = normalize_email(email)
        query = select(PlatformAccount.id).where(PlatformAccount.email == normalized)
        if exclude_id is not None:
            query = query.where(PlatformAccount.id != exclude_id)
        if self.db.scalar(query.limit(1)) is not None or self.user_credentials.email_exists(normalized):
            raise PlatformEmailTakenError
        return normalized

    def _protect_last_root(self, account: PlatformAccount) -> None:
        role = PlatformAccountRole.ROOT if account.is_root else account.role
        if role is not PlatformAccountRole.ROOT or account.status is not PlatformAccountStatus.ACTIVE:
            return
        active_roots = self.db.scalar(
            select(func.count(PlatformAccount.id)).where(
                PlatformAccount.status == PlatformAccountStatus.ACTIVE,
                (PlatformAccount.role == PlatformAccountRole.ROOT) | (PlatformAccount.is_root.is_(True)),
            )
        ) or 0
        if active_roots <= 1:
            raise LastPlatformRootError

    def create_account(self, full_name: str, email: str, password: str, confirmation: str, role: PlatformAccountRole) -> PlatformAccount:
        normalized = self._email_available(email)
        validate_password(password, confirmation, normalized, 12)
        account = PlatformAccount(
            full_name=full_name.strip(), email=normalized, password_hash=hash_password(password),
            status=PlatformAccountStatus.ACTIVE, role=role, is_root=role is PlatformAccountRole.ROOT,
            token_version=0,
        )
        self.db.add(account)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise PlatformEmailTakenError from exc
        self.db.refresh(account)
        return account

    def update_account(self, account_id: UUID, *, full_name: str | None = None, email: str | None = None, role: PlatformAccountRole | None = None, status: PlatformAccountStatus | None = None) -> PlatformAccount:
        account = self.get_account(account_id)
        current_role = PlatformAccountRole.ROOT if account.is_root else account.role
        if role is PlatformAccountRole.ADMIN and current_role is PlatformAccountRole.ROOT:
            self._protect_last_root(account)
        if status is PlatformAccountStatus.INACTIVE:
            self._protect_last_root(account)
        if full_name is not None:
            account.full_name = full_name.strip()
        if email is not None:
            account.email = self._email_available(email, account.id)
        if role is not None:
            account.role = role
            account.is_root = role is PlatformAccountRole.ROOT
        if status is not None and status is not account.status:
            account.status = status
            if status is PlatformAccountStatus.INACTIVE:
                account.token_version += 1
                revoke_account_sessions(self.db, "platform", account.id, reason="account_inactive")
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise PlatformEmailTakenError from exc
        self.db.refresh(account)
        return account

    def deactivate_account(self, account_id: UUID) -> PlatformAccount:
        account = self.get_account(account_id)
        if self.is_bootstrap_root(account.id):
            raise BootstrapRootProtectedError
        self._protect_last_root(account)
        if account.status is not PlatformAccountStatus.INACTIVE:
            account.status = PlatformAccountStatus.INACTIVE
            account.token_version += 1
            revoke_account_sessions(self.db, "platform", account.id, reason="account_inactive")
            self.db.commit()
            self.db.refresh(account)
        return account

    def reset_password(self, account_id: UUID, password: str, confirmation: str) -> PlatformAccount:
        account = self.get_account(account_id)
        validate_password(password, confirmation, account.email, 12)
        account.password_hash = hash_password(password)
        account.password_changed_at = datetime.now(timezone.utc)
        account.token_version += 1
        revoke_account_sessions(self.db, "platform", account.id, reason="password_reset")
        self.db.commit()
        self.db.refresh(account)
        return account
