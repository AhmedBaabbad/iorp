from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class OrganizationData:
    name: str
    code: str
    industry_type: str | None
    timezone: str
    default_locale: str
    logo_base64: str | None


@dataclass(frozen=True)
class OrganizationAdminData:
    full_name: str
    email: str
    phone: str | None
    password: str


@dataclass(frozen=True)
class ProvisionedOrganization:
    id: UUID
    name: str
    code: str
    logo_path: str | None = None
    role_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProvisionedUser:
    id: UUID
    email: str


class LogoStorageInterface(Protocol):
    def validate_logo(self, encoded: str) -> None: ...

    def save_logo(self, encoded: str, organization_id: UUID) -> str: ...

    def delete(self, relative_path: str) -> None: ...


@dataclass(frozen=True)
class OrganizationSummary:
    id: UUID
    name: str
    code: str
    status: str
    status_changed_at: datetime | None
    status_changed_by: UUID | None
    status_change_reason: str | None
    industry_type: str | None
    timezone: str
    default_locale: str
    user_count: int
    admin_email: str | None
    root_user_email: str | None
    has_logo: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class OrganizationRootSummary:
    id: UUID
    full_name: str
    email: str
    status: str
    last_login_at: datetime | None


@dataclass(frozen=True)
class OrganizationRoleSummary:
    id: UUID
    code: str
    user_count: int


@dataclass(frozen=True)
class OrganizationDetail:
    summary: OrganizationSummary
    root_user: OrganizationRootSummary | None
    roles: list[OrganizationRoleSummary]


class OrganizationProvisioningInterface(Protocol):
    def create_organization(
        self,
        organization: OrganizationData,
        administrator: OrganizationAdminData,
    ) -> tuple[ProvisionedOrganization, ProvisionedUser]: ...

    def cleanup_logo(self, relative_path: str) -> None: ...

    def list_organizations(self) -> list[OrganizationSummary]: ...

    def get_organization(self, organization_id: UUID) -> OrganizationSummary | None: ...

    def get_organization_detail(self, organization_id: UUID) -> OrganizationDetail | None: ...

    def get_logo_path(self, organization_id: UUID) -> str | None: ...

    def set_organization_status(
        self, organization_id: UUID, status: str, changed_by: UUID, reason: str | None
    ) -> OrganizationSummary | None: ...
