from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, EmailStr, Field, field_validator, model_validator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.platform.domain.enums import PlatformAccountRole, PlatformAccountStatus
from app.core.types import NormalizedEmail
from app.core.password_policy import PASSWORD_MIN_LENGTH, PasswordPolicyError, validate_password
from pydantic_core import PydanticCustomError

class BootstrapStatusResponse(BaseModel):
    initialized: bool


class AccountInput(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: NormalizedEmail
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128)
    password_confirmation: str

    @model_validator(mode="after")
    def passwords_match(self):
        try:
            validate_password(self.password, self.password_confirmation, str(self.email))
        except PasswordPolicyError as exc:
            raise PydanticCustomError(exc.code, str(exc)) from exc
        return self


class PlatformRootInput(AccountInput):
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128)


class OrganizationAdminInput(AccountInput):
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128)
    phone: str | None = Field(default=None, max_length=50)


class OrganizationInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(pattern=r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$", max_length=64)
    industry_type: str | None = Field(default=None, max_length=120)
    timezone: str = Field(default="Asia/Riyadh", max_length=64)
    default_locale: Literal["ar", "en"] = "ar"
    logo_base64: str | None = None

    @field_validator("code")
    @classmethod
    def uppercase_code(cls, value: str) -> str:
        return value.upper()

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Invalid IANA timezone.") from exc
        return value


class BootstrapInitializeRequest(BaseModel):
    bootstrap_token: str = Field(min_length=1, max_length=1024)
    platform_root: PlatformRootInput
    organization: OrganizationInput
    organization_admin: OrganizationAdminInput

    @model_validator(mode="after")
    def emails_differ(self):
        if str(self.platform_root.email).casefold() == str(self.organization_admin.email).casefold():
            raise ValueError("Platform and organization administrator emails must differ.")
        return self


class InitializedOrganization(BaseModel):
    id: UUID
    name: str
    code: str


class BootstrapInitializeResponse(BaseModel):
    message: str
    organization: InitializedOrganization
    platform_root_email: EmailStr
    organization_admin_email: EmailStr


class PlatformLoginRequest(BaseModel):
    email: NormalizedEmail
    password: str = Field(min_length=1, max_length=128)
    mfa_code: str = Field(default="", max_length=128)


class PlatformLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int | None = None
    refresh_token: str | None = Field(default=None, exclude=True)


class PlatformMeResponse(BaseModel):
    id: UUID
    account_type: Literal["platform"] = "platform"
    full_name: str
    email: EmailStr
    is_root: bool
    role: PlatformAccountRole
    permissions: list[str]
    mfa_enrollment_required: bool = False


class ChangePasswordRequest(BaseModel):
    current_password: str = ""
    new_password: str = Field(min_length=1, max_length=128)
    password_confirmation: Annotated[
        str,
        Field(validation_alias=AliasChoices("password_confirmation", "new_password_confirmation")),
    ] = ""



class PlatformOrganizationSummary(BaseModel):
    id: UUID
    name: str
    code: str
    status: Literal["provisioning", "active", "suspended", "inactive", "archived"]
    status_changed_at: datetime | None
    status_changed_by: UUID | None
    status_changed_by_name: str | None
    status_change_reason: str | None
    allowed_transitions: list[str]
    industry_type: str | None
    timezone: str
    default_locale: str
    user_count: int
    admin_email: EmailStr | None
    root_user_email: EmailStr | None
    has_logo: bool
    logo_url: str | None
    created_at: datetime
    updated_at: datetime


class PlatformOrganizationRootSummary(BaseModel):
    id: UUID
    full_name: str
    email: EmailStr
    status: str
    last_login_at: datetime | None
    activation_pending: bool = False  # SEC-003


class PlatformOrganizationRoleSummary(BaseModel):
    id: UUID
    code: str
    user_count: int


class PlatformOrganizationDetail(PlatformOrganizationSummary):
    root_user: PlatformOrganizationRootSummary | None
    roles: list[PlatformOrganizationRoleSummary]


class OrganizationRootInvite(BaseModel):
    """SEC-003: the organization's root, without a password: they receive an activation link and choose their own."""
    full_name: str = Field(min_length=1, max_length=255)
    email: NormalizedEmail
    phone: str | None = Field(default=None, max_length=50)


class CreatePlatformOrganizationRequest(BaseModel):
    organization: OrganizationInput
    organization_admin: OrganizationRootInvite


class ProvisionedOrganizationResponse(BaseModel):
    id: UUID
    name: str
    code: str
    status: Literal["provisioning", "active", "suspended", "inactive", "archived"]
    default_locale: str
    timezone: str
    has_logo: bool
    created_at: datetime


class ProvisionedRootUserResponse(BaseModel):
    id: UUID
    full_name: str
    email: EmailStr
    is_organization_root: bool


class CreatePlatformOrganizationResponse(BaseModel):
    message: str
    organization: ProvisionedOrganizationResponse
    root_user: ProvisionedRootUserResponse
    roles_created: list[str]
    organization_admin_email: EmailStr
    invitation_sent: bool = False  # SEC-003: whether the root's activation e-mail went out


class OrganizationStatusChangeRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class ResetOrganizationRootPasswordRequest(BaseModel):
    """SEC-002: nothing to send — the organization's root receives a reset link and chooses their own password."""


class ResetOrganizationRootPasswordResponse(BaseModel):
    message: str
    organization_id: UUID
    root_user_email: EmailStr
    sessions_invalidated: bool


class PlatformAccountCreate(BaseModel):
    """SEC-003: no password — the new administrator receives an activation link and chooses their own."""
    full_name: str = Field(min_length=1, max_length=255)
    email: NormalizedEmail
    role: PlatformAccountRole


class PlatformAccountUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: NormalizedEmail | None = None
    role: PlatformAccountRole | None = None
    status: PlatformAccountStatus | None = None


class PlatformAccountResponse(BaseModel):
    id: UUID
    full_name: str
    email: EmailStr
    role: PlatformAccountRole
    status: PlatformAccountStatus
    is_root: bool
    is_bootstrap_root: bool = False
    last_login_at: datetime | None
    password_changed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    activation_pending: bool = False  # SEC-003: the activation link not used yet
    invitation_sent: bool | None = None  # on creation only


class PlatformAccountListItem(BaseModel):
    id: UUID
    full_name: str
    email: EmailStr
    role: PlatformAccountRole
    status: PlatformAccountStatus
    is_root: bool
    is_bootstrap_root: bool = False
    last_login_at: datetime | None
    created_at: datetime
    activation_pending: bool = False


class PlatformPasswordResetRequest(BaseModel):
    """SEC-002: nothing to send — the administrator receives a reset link and chooses their own password."""
