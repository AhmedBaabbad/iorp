from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class TenantContext:
    user_id: UUID
    organization_id: UUID
    roles: tuple[str, ...] = ()


def ensure_same_organization(
    tenant: TenantContext,
    organization_id: UUID,
) -> None:
    if tenant.organization_id != organization_id:
        raise ValueError("Resource does not belong to the current organization.")


def is_same_organization(
    tenant: TenantContext,
    organization_id: UUID,
) -> bool:
    return tenant.organization_id == organization_id
