VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    "provisioning": frozenset({"active"}),
    "active": frozenset({"suspended", "inactive"}),
    "suspended": frozenset({"active", "inactive"}),
    "inactive": frozenset({"active", "archived"}),
    "archived": frozenset(),
}


class InvalidStateTransitionError(RuntimeError):
    code = "INVALID_STATE_TRANSITION"

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        self.allowed = sorted(VALID_TRANSITIONS.get(current, frozenset()))
        super().__init__(f"Cannot transition from '{current}' to '{target}'")


def validate_transition(current: str, target: str) -> None:
    if target not in VALID_TRANSITIONS.get(current, frozenset()):
        raise InvalidStateTransitionError(current, target)
