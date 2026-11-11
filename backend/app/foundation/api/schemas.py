from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Literal

from app.core.types import ISODatetime, NormalizedEmail
from app.core.password_policy import PASSWORD_MIN_LENGTH
from app.foundation.domain.enums import OrganizationStatus, UserStatus


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=64)
    status: OrganizationStatus = OrganizationStatus.ACTIVE
    industry_type: str | None = Field(default=None, max_length=120)
    timezone: str = Field(default="UTC", max_length=64)


class OrganizationRead(BaseModel):
    id: UUID
    name: str
    code: str
    status: OrganizationStatus
    industry_type: str | None
    timezone: str
    created_at: ISODatetime
    updated_at: ISODatetime

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: NormalizedEmail
    phone: str | None = Field(default=None, max_length=50)
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128)
    status: UserStatus = UserStatus.ACTIVE


class UserRead(BaseModel):
    id: UUID
    organization_id: UUID
    full_name: str
    email: EmailStr
    phone: str | None
    status: UserStatus
    is_organization_root: bool
    last_login_at: ISODatetime | None
    created_at: ISODatetime
    updated_at: ISODatetime

    model_config = ConfigDict(from_attributes=True)


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=64)
    description: str | None = None


class RoleRead(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    code: str
    description: str | None
    created_at: ISODatetime
    updated_at: ISODatetime

    model_config = ConfigDict(from_attributes=True)


class PermissionCreate(BaseModel):
    code: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    module_name: str = Field(min_length=1, max_length=80)
    action_name: str = Field(min_length=1, max_length=80)


class PermissionRead(BaseModel):
    id: UUID
    code: str
    name: str
    module_name: str
    action_name: str

    model_config = ConfigDict(from_attributes=True)


class RolePermissionAssign(BaseModel):
    role_id: UUID
    permission_id: UUID


class RolePermissionRead(BaseModel):
    id: UUID
    role_id: UUID
    permission_id: UUID

    model_config = ConfigDict(from_attributes=True)


class UserRoleAssign(BaseModel):
    user_id: UUID
    role_id: UUID


class UserRoleRead(BaseModel):
    id: UUID
    user_id: UUID
    role_id: UUID

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: NormalizedEmail
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int | None = None
    refresh_token: str | None = Field(default=None, exclude=True)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)
    new_password_confirmation: str = Field(min_length=1, max_length=128)


class AdminPasswordResetRequest(BaseModel):
    """SEC-002: an administrator never chooses nor learns a user's password: the only way is a reset link e-mailed to the
    user, who chooses their own. (Nothing to send: any field given is ignored.)"""


class CurrentUserOrganization(BaseModel):
    id: UUID
    name: str
    code: str
    has_logo: bool
    logo_url: str | None
    default_locale: Literal["ar", "en"]


class CurrentUserResponse(BaseModel):
    timezone: str | None = None
    id: UUID
    organization_id: UUID
    organization_code: str
    organization_name: str
    organization_logo_url: str | None = None
    organization_timezone: str
    full_name: str
    email: EmailStr
    phone: str | None
    preferred_locale: Literal["ar", "en"] | None
    effective_locale: Literal["ar", "en"]
    status: UserStatus
    is_organization_root: bool
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    organization: CurrentUserOrganization
    last_login_at: ISODatetime | None
    created_at: ISODatetime


class UserProfileResponse(BaseModel):
    timezone: str | None = Field(default=None, max_length=64)
    id: UUID
    full_name: str
    email: EmailStr
    phone: str | None
    preferred_locale: Literal["ar", "en"] | None
    effective_locale: Literal["ar", "en"]
    organization_id: UUID
    organization_name: str
    organization_code: str
    is_organization_root: bool
    status: UserStatus
    roles: list[str] = Field(default_factory=list)
    last_login_at: ISODatetime | None
    created_at: ISODatetime


class UserProfileUpdate(BaseModel):
    timezone: str | None = Field(default=None, max_length=64)
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    preferred_locale: str | None = Field(default=None, max_length=10)

    model_config = ConfigDict(extra="forbid")


class OrganizationProfileResponse(BaseModel):
    id: UUID
    name: str
    code: str
    status: OrganizationStatus
    industry_type: str | None
    timezone: str
    default_locale: Literal["ar", "en"]
    has_logo: bool
    logo_url: str | None
    created_at: ISODatetime
    updated_at: ISODatetime
    max_sessions_per_user: int = 2  # SEC-001


class OrganizationProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    industry_type: str | None = Field(default=None, max_length=120)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    default_locale: Literal["ar", "en"] | None = None
    # SEC-001: devices one user may be signed in on at once (a further sign-in ends the oldest)
    max_sessions_per_user: int | None = Field(default=None, ge=1, le=5)


class OrganizationLogoResponse(BaseModel):
    message: str
    has_logo: bool
    logo_url: str | None = None


# ── User management schemas ───────────────────────────────────────────────────

class AdminUserCreate(BaseModel):
    """SEC-003: no password — the new user receives an activation link and chooses their own."""
    full_name: str = Field(min_length=1, max_length=255)
    email: NormalizedEmail
    phone: str | None = Field(default=None, max_length=50)
    role_codes: list[str] = Field(default_factory=list)
    preferred_locale: Literal["ar", "en"] | None = None


class AdminUserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: NormalizedEmail | None = None
    phone: str | None = Field(default=None, max_length=50)
    preferred_locale: Literal["ar", "en"] | None = None

class RoleRef(BaseModel):
    id: UUID
    name: str
    code: str

    model_config = ConfigDict(from_attributes=True)


class UserListItem(BaseModel):
    archived_at: ISODatetime | None = None
    id: UUID
    full_name: str
    email: EmailStr
    phone: str | None
    preferred_locale: Literal["ar", "en"] | None
    status: UserStatus
    is_organization_root: bool
    roles: list[RoleRef] = Field(default_factory=list)
    created_at: ISODatetime
    activation_pending: bool = False  # SEC-003: the activation link not used yet

    model_config = ConfigDict(from_attributes=True)


class AdminUserResponse(BaseModel):
    archived_at: ISODatetime | None = None
    account_change_reason: str | None = None
    timezone: str | None = Field(default=None, max_length=64)
    id: UUID
    organization_id: UUID
    full_name: str
    email: EmailStr
    phone: str | None
    preferred_locale: Literal["ar", "en"] | None
    status: UserStatus
    is_organization_root: bool
    last_login_at: ISODatetime | None
    failed_login_attempts: int
    auto_locked_until: ISODatetime | None
    last_failed_login_at: ISODatetime | None
    roles: list[RoleRef] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    created_at: ISODatetime
    updated_at: ISODatetime
    activation_pending: bool = False  # SEC-003: the activation link not used yet
    invitation_sent: bool | None = None  # on creation only: whether the activation e-mail went out

    model_config = ConfigDict(from_attributes=True)


AdminUserUpdateRequest = AdminUserUpdate
UserCreateRequest = AdminUserCreate
UserDetailResponse = AdminUserResponse
UserUpdateRequest = AdminUserUpdate


class UserDeactivationImpactResponse(BaseModel):
    user_id: UUID
    user_full_name: str
    can_deactivate: bool
    dependencies: dict[str, int | bool]
    total_blocking_items: int
    message: str


# ── Role management schemas ───────────────────────────────────────────────────

class RoleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    description: str | None = None


class RoleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    code: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    description: str | None = None


class RoleListItem(BaseModel):
    id: UUID
    name: str
    code: str
    description: str | None
    is_system: bool = False
    is_protected: bool = False
    is_editable: bool = True
    permission_count: int = 0
    user_count: int = 0
    permissions_count: int = 0
    users_count: int = 0
    created_at: ISODatetime

    model_config = ConfigDict(from_attributes=True)


class RolePermissionAssignRequest(BaseModel):
    permission_id: UUID | None = None
    permission_code: str | None = Field(default=None, min_length=1, max_length=120)


class AssignPermissionRequest(BaseModel):
    permission_code: str = Field(min_length=1, max_length=120)
    scope: Literal["own", "team", "organization"] = "organization"


class RolePermissionScopeUpdateRequest(BaseModel):
    scope: Literal["own", "team", "organization"]


class UserRoleAssignRequest(BaseModel):
    role_id: UUID


class RoleAssignerResponse(BaseModel):
    id: UUID
    full_name: str


class AssignedRoleResponse(BaseModel):
    id: UUID
    code: str
    name: str
    is_system: bool
    is_protected: bool
    assigned_by: RoleAssignerResponse | None = None
    assigned_at: ISODatetime


class UserRolesResponse(BaseModel):
    roles: list[AssignedRoleResponse]


class RoleAssignmentResponse(BaseModel):
    message: str
    user_id: UUID
    role: RoleRef
    assigned_by: RoleAssignerResponse
    assigned_at: ISODatetime


class RoleRemovalResponse(BaseModel):
    message: str
    user_id: UUID
    role_id: UUID


class AssignableRoleResponse(BaseModel):
    id: UUID
    code: str
    name: str
    is_system: bool
    is_protected: bool
    permission_count: int


class AssignableRolesResponse(BaseModel):
    assignable_roles: list[AssignableRoleResponse]
    target_user_id: UUID
    is_self: bool
    restricted_count: int = 0
    message: str | None = None


class AssignRoleRequest(BaseModel):
    role_id: UUID


# ── Permission grouping ───────────────────────────────────────────────────────

class PermissionItem(BaseModel):
    code: str
    name: str
    scope: Literal["own", "team", "organization"] = "organization"
    scopable: bool = False


class PermissionGroupResponse(BaseModel):
    module: str
    permissions: list[PermissionItem]


class PermissionCatalogItemResponse(BaseModel):
    id: UUID
    code: str
    module: str
    resource: str
    action: str
    name: str
    description: str
    name_en: str
    name_ar: str
    description_en: str
    description_ar: str
    scopable: bool = False
    owner_field: str | None = None


class PermissionModuleResponse(BaseModel):
    module: str
    module_name_en: str
    module_name_ar: str
    permissions: list[PermissionCatalogItemResponse]


class PermissionCatalogResponse(BaseModel):
    total: int
    modules: list[PermissionModuleResponse]


class RoleDetailResponse(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    code: str
    description: str | None
    is_system: bool = False
    is_protected: bool = False
    is_editable: bool = True
    permission_count: int = 0
    user_count: int = 0
    permissions: list[PermissionGroupResponse] = Field(default_factory=list)
    created_at: ISODatetime
    updated_at: ISODatetime

    model_config = ConfigDict(from_attributes=True)


class RoleDeletionImpactResponse(BaseModel):
    role_id: UUID
    user_count: int
    assigned_user_count: int
    can_delete: bool
    reason_code: str | None = None


PermissionGroup = PermissionGroupResponse
AdminPermissionItem = PermissionItem
AdminPermissionGroup = PermissionGroupResponse


class EffectiveAccessRoleSource(BaseModel):
    role_id: UUID
    role_code: str
    role_name: str
    scope: Literal["own", "team", "organization"]


class EffectiveAccessRole(BaseModel):
    id: UUID
    code: str
    name: str
    is_system: bool


class EffectivePermissionResponse(BaseModel):
    code: str
    module: str
    resource: str
    action: str
    name: str
    description: str
    effective_scope: Literal["own", "team", "organization"]
    scopable: bool
    scope_label: str
    granted_by_roles: list[EffectiveAccessRoleSource]
    is_root_bypass: bool


class MissingPermissionResponse(BaseModel):
    code: str
    module: str
    name: str


class EffectiveAccessResponse(BaseModel):
    user_id: UUID
    user_full_name: str
    user_email: str
    is_organization_root: bool
    total_permissions: int
    total_roles: int
    roles: list[EffectiveAccessRole]
    permissions_by_module: dict[str, list[EffectivePermissionResponse]]
    missing_permissions_count: int
    missing_permissions: list[MissingPermissionResponse]
    generated_at: ISODatetime
