"""Checks other modules run before a production order closes (QUAL-001).

Production owns the order lifecycle and must not import the modules that care about it. A module
(Quality) registers a guard at the composition root; production asks for the blockers while it holds
the order lock and refuses to close when any guard reports one.

A guard is `guard(db, organization_id, order_id) -> list[Blocker]` and is read-only.
"""
from dataclasses import dataclass, field
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class Blocker:
    code: str  # e.g. "QUALITY_CHECKS_OPEN"
    count: int
    detail: dict = field(default_factory=dict)


CloseGuard = Callable[[Session, UUID, UUID], list[Blocker]]
_guards: list[CloseGuard] = []


def register_close_guard(guard: CloseGuard) -> None:
    if guard not in _guards:
        _guards.append(guard)


def close_blockers(db: Session, organization_id: UUID, order_id: UUID) -> list[Blocker]:
    return [blocker for guard in _guards for blocker in guard(db, organization_id, order_id)]
