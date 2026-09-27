from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.types import ISODatetime
from app.workforce.domain.enums import EmploymentType, WorkforceMemberStatus, WorkerType


class WorkforceMemberCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    worker_type: WorkerType
    employment_type: EmploymentType
    display_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    primary_skill: str | None = Field(default=None, max_length=255)
    notes: str | None = None

    model_config = ConfigDict(extra="forbid")


class WorkforceMemberUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    worker_type: WorkerType | None = None
    employment_type: EmploymentType | None = None
    status: WorkforceMemberStatus | None = None
    primary_skill: str | None = Field(default=None, max_length=255)
    notes: str | None = None

    model_config = ConfigDict(extra="forbid")


class LinkedUser(BaseModel):
    id: UUID
    full_name: str
    email: str
    status: str
    roles: list[str]

    model_config = ConfigDict(from_attributes=True)


class WorkforceMemberResponse(BaseModel):
    id: UUID
    organization_id: UUID
    employee_code: str
    full_name: str
    display_name: str | None
    phone: str | None
    email: str | None
    worker_type: WorkerType
    employment_type: EmploymentType
    status: WorkforceMemberStatus
    is_system_user: bool
    user_id: UUID | None
    linked_user: LinkedUser | None = None
    primary_skill: str | None
    notes: str | None
    created_at: ISODatetime
    updated_at: ISODatetime

    model_config = ConfigDict(from_attributes=True)


class WorkforceMemberListItem(BaseModel):
    id: UUID
    employee_code: str
    full_name: str
    worker_type: WorkerType
    employment_type: EmploymentType
    status: WorkforceMemberStatus
    is_system_user: bool
    user_id: UUID | None
    phone: str | None

    model_config = ConfigDict(from_attributes=True)


class LinkUserRequest(BaseModel):
    user_id: UUID


class WorkforceMemberDeletionImpact(BaseModel):
    is_blocked: bool


class WorkforceMemberDeleteResult(BaseModel):
    id: UUID
    deleted: bool
