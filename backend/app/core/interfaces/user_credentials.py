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

    def send_password_reset_link(self, user_id: UUID) -> bool:
        """SEC-002: e-mails the user a reset link (they choose their own password); True when it went out. Nobody else ever
        sets a user's password — not the platform operator either."""
        ...
