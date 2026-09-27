from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class OrganizationRootCredential:
    user_id: UUID
    organization_id: UUID
    email: str


class UserCredentialInterface(Protocol):
    def email_exists(self, email: str) -> bool: ...

    def get_organization_root(
        self, organization_id: UUID
    ) -> OrganizationRootCredential | None: ...

    def reset_user_password(self, user_id: UUID, new_password_hash: str) -> None: ...
