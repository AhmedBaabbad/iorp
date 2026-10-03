"""Production order status lifecycle: the single source of truth for status changes.

Pure rules, no database: which action moves which status where, who may do it, and
what it requires. OrderStatusService applies them; nothing else writes order status.

    draft ──release──► released ──start──► in_progress ──complete──► completed ──close──► closed
      │  ▲               │  │                 │   ▲
      │  └─return_to_draft┘  │            hold  │   │ resume
      └──cancel──► cancelled ◄──cancel──┘       ▼   │
                                              on_hold

Planned dates never change status; they only raise the late-start / late-finish flags.
"""
from dataclasses import dataclass
from datetime import date
from app.production.domain.enums import ProductionOrderStatus as S
from app.production.domain.permissions import ORDER_TRANSITIONS


class TransitionError(ValueError):
    def __init__(self, code: str, status: int = 409, **detail):
        super().__init__(code)
        self.code, self.status, self.detail = code, status, detail


@dataclass(frozen=True)
class Action:
    name: str
    sources: frozenset[S]
    target: S
    permission: str
    requires_reason: bool = False
    # Asks for confirmation in the UI: the action cannot be undone.
    confirm: bool = False


# Each action's permission comes from the one production map (domain/permissions.py).
T = ORDER_TRANSITIONS
ACTIONS: dict[str, Action] = {a.name: a for a in (
    Action("release", frozenset({S.DRAFT}), S.RELEASED, T["release"]),
    Action("return_to_draft", frozenset({S.RELEASED}), S.DRAFT, T["return_to_draft"]),
    Action("start", frozenset({S.RELEASED}), S.IN_PROGRESS, T["start"]),
    Action("hold", frozenset({S.IN_PROGRESS}), S.ON_HOLD, T["hold"], requires_reason=True),
    Action("resume", frozenset({S.ON_HOLD}), S.IN_PROGRESS, T["resume"]),
    Action("complete", frozenset({S.IN_PROGRESS}), S.COMPLETED, T["complete"]),
    Action("close", frozenset({S.COMPLETED}), S.CLOSED, T["close"], confirm=True),
    Action("cancel", frozenset({S.DRAFT, S.RELEASED}), S.CANCELLED, T["cancel"], requires_reason=True, confirm=True),
)}

TERMINAL = frozenset({S.CLOSED, S.CANCELLED})
# Statuses whose planned dates still matter for lateness.
NOT_STARTED = frozenset({S.DRAFT, S.RELEASED})
OPEN = frozenset({S.DRAFT, S.RELEASED, S.IN_PROGRESS, S.ON_HOLD})


def resolve(status: S | str, action_name: str, reason: str | None) -> Action:
    """The action to apply from `status`, or TransitionError explaining why not."""
    action = ACTIONS.get(action_name)
    if action is None:
        raise TransitionError("UNKNOWN_ACTION", 400, action=action_name)
    current = S(status)
    if current not in action.sources:
        raise TransitionError("TRANSITION_NOT_ALLOWED", 409, action=action_name, from_status=current.value)
    if action.requires_reason and not (reason and reason.strip()):
        raise TransitionError("REASON_REQUIRED", 400, action=action_name)
    return action


def available(status: S | str) -> list[Action]:
    current = S(status)
    return [a for a in ACTIONS.values() if current in a.sources]


def start_overdue(status: S | str, planned_start: date, today: date) -> bool:
    return S(status) in NOT_STARTED and today > planned_start


def finish_overdue(status: S | str, planned_end: date, today: date) -> bool:
    return S(status) in OPEN and today > planned_end
