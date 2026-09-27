from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: UUID
    organization_id: UUID
    email: str
    roles: frozenset[str] = frozenset()
    permissions: frozenset[str] = frozenset()
