"""Read-only employee data for other modules; workforce owns the records."""
from typing import Protocol


class WorkforceDirectory(Protocol):
    def member(self, db, org, member_id, *, active_only=False, lock=False) -> dict | None: ...
    def members(self, db, org, search="") -> list[dict]: ...


_provider: WorkforceDirectory | None = None


def register_workforce_directory(provider: WorkforceDirectory):
    global _provider
    _provider = provider


def directory() -> WorkforceDirectory:
    if _provider is None:
        raise RuntimeError("Workforce directory unavailable")
    return _provider
