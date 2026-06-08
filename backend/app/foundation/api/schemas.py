from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

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
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    organization_id: UUID
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=50)
    password: str = Field(min_length=8, max_length=128)
    status: UserStatus = UserStatus.ACTIVE


class UserRead(BaseModel):
    id: UUID
    organization_id: UUID
    full_name: str
    email: EmailStr
    phone: str | None
    status: UserStatus
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoleCreate(BaseModel):
    organization_id: UUID
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=64)
    description: str | None = None


class RoleRead(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    code: str
    description: str | None
    created_at: datetime
    updated_at: datetime

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
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUserResponse(BaseModel):
    id: UUID
    organization_id: UUID
    organization_code: str
    full_name: str
    email: EmailStr
    status: UserStatus
    roles: list[str] = Field(default_factory=list)
