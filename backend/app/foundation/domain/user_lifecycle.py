from dataclasses import dataclass
from uuid import UUID

from app.foundation.domain.enums import UserStatus


USER_VALID_TRANSITIONS = {
    UserStatus.ACTIVE: {UserStatus.INACTIVE, UserStatus.LOCKED},
    UserStatus.INACTIVE: {UserStatus.ACTIVE},
    UserStatus.LOCKED: {UserStatus.ACTIVE, UserStatus.INACTIVE},
}


class InvalidUserStateTransitionError(ValueError):
    def __init__(self, current: UserStatus, target: UserStatus) -> None:
        self.current = current
        self.target = target
        self.allowed = sorted(status.value for status in USER_VALID_TRANSITIONS.get(current, set()))
        super().__init__(f"Cannot transition user from {current.value} to {target.value}.")


def validate_user_transition(current: UserStatus, target: UserStatus) -> None:
    if target not in USER_VALID_TRANSITIONS.get(current, set()):
        raise InvalidUserStateTransitionError(current, target)


@dataclass(frozen=True)
class DeactivationImpact:
    user_id: UUID
    user_full_name: str
    open_follow_ups: int
    assigned_customers: int
    active_workforce_link: bool

    @property
    def total_blocking_items(self) -> int:
        return self.open_follow_ups + self.assigned_customers + int(self.active_workforce_link)

    @property
    def can_deactivate(self) -> bool:
        return self.total_blocking_items == 0
