from typing import Protocol
from uuid import UUID


class WorkforceQueryInterface(Protocol):
    def has_linked_member(self, user_id: UUID, organization_id: UUID) -> bool: ...
    def linked_member_id(self, user_id: UUID, organization_id: UUID) -> UUID | None: ...
