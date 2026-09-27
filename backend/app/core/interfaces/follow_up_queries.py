from typing import Protocol
from uuid import UUID


class FollowUpQueryInterface(Protocol):
    def count_open_follow_ups_for_user(
        self, user_id: UUID, organization_id: UUID
    ) -> int: ...
