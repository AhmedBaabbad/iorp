from typing import Protocol
from uuid import UUID


class CustomerQueryInterface(Protocol):
    def count_assigned_customers(self, user_id: UUID, organization_id: UUID) -> int: ...
