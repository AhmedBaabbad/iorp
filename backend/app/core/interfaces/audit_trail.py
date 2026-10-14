"""The organization's audit trail (ORG-AUDIT-002), reached by modules that make governance changes of their own (e.g.
announcements) without touching foundation's tables. Foundation keeps the trail; an entry belongs to the caller's
transaction."""
from typing import Any, Protocol
from uuid import UUID


class AuditTrailInterface(Protocol):
    def record(self, db, organization_id: UUID, action: str, entity_type: str, entity_id: UUID | str | None = None,
               entity_name: str | None = None, actor_id: UUID | None = None, details: Any = None) -> None: ...


class _NoAuditTrail:
    def record(self, *args, **kwargs) -> None:
        return None


_provider: AuditTrailInterface = _NoAuditTrail()


def register_audit_trail(provider: AuditTrailInterface) -> None:
    global _provider
    _provider = provider


def record(db, organization_id, action, entity_type, entity_id=None, entity_name=None, actor_id=None, details=None) -> None:
    """One governance change: what (action on entity_type), which one, by whom, and the values before and after."""
    _provider.record(db, organization_id, action, entity_type, entity_id, entity_name, actor_id, details)
