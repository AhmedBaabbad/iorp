"""Notifications (PROJECT-NOTIFY-001): what a module calls to tell people that something concerns them.

The notifications module keeps every notification and is the only writer of its tables; a module never reads or writes
them. A module says *what happened* (a Notice) and *to whom* (an Audience) in the same transaction as its own change, so
a notification exists exactly when the change is committed. Sending never fails the module's change: a problem is logged
and the change goes on.

- An event is named "<module>.<subject>.<what>" (e.g. "procurement.purchase_order.approved"). Its words, in Arabic and
  English, live in the screens (notifications.events.<event>), filled with the notice's params, so every user reads it
  in their own language. The person who did it is recorded by the notifications module (the actor's name).
- A work notice names its document (resource_type, resource_id). When the work is done, the module calls settle(): the
  waiting notices about it are marked as dealt with and no longer counted as unread.
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

log = logging.getLogger(__name__)

# What a notification is about; the screens group and colour them by it.
ACCESS, SECURITY, DELEGATION, WORK, ANNOUNCEMENT = "access", "security", "delegation", "work", "announcement"
CATEGORIES = (ACCESS, SECURITY, DELEGATION, WORK, ANNOUNCEMENT)
INFO, IMPORTANT, URGENT = "info", "important", "urgent"
SEVERITIES = (INFO, IMPORTANT, URGENT)


@dataclass(frozen=True)
class Audience:
    """Who receives it: named users, the holders of a permission (through a role, as the organization's root, or by a
    delegation in force), the members of a role, or everyone. Only active users of the organization receive anything;
    the person who did it is left out unless include_actor."""
    users: tuple[UUID, ...] = ()
    permission: str | None = None
    role_id: UUID | None = None
    everyone: bool = False
    exclude: tuple[UUID, ...] = ()
    include_actor: bool = False

    @classmethod
    def to(cls, *users: UUID | None, **kwargs) -> "Audience":
        return cls(users=tuple(u for u in users if u), **kwargs)

    @classmethod
    def holders(cls, permission: str, **kwargs) -> "Audience":
        return cls(permission=permission, **kwargs)


@dataclass(frozen=True)
class Notice:
    event: str
    category: str = WORK
    params: dict[str, Any] = field(default_factory=dict)
    link: str | None = None
    severity: str = INFO
    resource_type: str | None = None
    resource_id: UUID | None = None


class NotificationsInterface(Protocol):
    def send(self, db, organization_id: UUID, audience: Audience, notice: Notice, actor_user_id: UUID | None) -> int: ...

    def settle(self, db, organization_id: UUID, resource_type: str, resource_id: UUID, events: tuple[str, ...] | None) -> int: ...


class _NoNotifications:
    def send(self, *args, **kwargs) -> int:
        return 0

    def settle(self, *args, **kwargs) -> int:
        return 0


_provider: NotificationsInterface = _NoNotifications()


def register_notifications(provider: NotificationsInterface) -> None:
    global _provider
    _provider = provider


def notify(db, organization_id: UUID, audience: Audience, notice: Notice, actor_user_id: UUID | None = None) -> int:
    """Adds the notice for its audience to the session (committed with the caller's change). Returns how many people
    receive it; never raises."""
    try:
        return _provider.send(db, organization_id, audience, notice, actor_user_id)
    except Exception:  # a notification must never undo the decision it reports
        log.exception("notification %s not sent", notice.event)
        return 0


def settle(db, organization_id: UUID, resource_type: str, resource_id: UUID, events: tuple[str, ...] | None = None) -> int:
    """The work about a document is done: its waiting notices (all, or these events) are dealt with. Never raises."""
    try:
        return _provider.settle(db, organization_id, resource_type, resource_id, events)
    except Exception:
        log.exception("notifications about %s %s not settled", resource_type, resource_id)
        return 0
