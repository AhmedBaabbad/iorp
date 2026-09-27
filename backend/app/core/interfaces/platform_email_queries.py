from typing import Protocol
from uuid import UUID


class PlatformEmailQueryInterface(Protocol):
    def email_exists(self, email: str, exclude_account_id: UUID | None = None) -> bool: ...
