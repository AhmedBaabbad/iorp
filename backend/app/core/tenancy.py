from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class TenantContext:
    user_id: UUID
    organization_id: UUID
    roles: tuple[str, ...] = ()
