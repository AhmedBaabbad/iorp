from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AuthenticatedUser:
    id: UUID
    organization_id: UUID
    email: str
    roles: tuple[str, ...] = ()
