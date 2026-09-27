from functools import wraps
from inspect import signature
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.orm import Session


class ActivityLogInterface(Protocol):
    def log_activity(
        self, db: Session, organization_id: UUID, action: str, entity_type: str,
        entity_id: UUID | None = None, entity_name: str | None = None,
        actor_id: UUID | None = None, actor_name: str | None = None,
        details: Any = None,
    ) -> None: ...


class NullActivityLogger:
    def log_activity(self, *args, **kwargs) -> None:
        return None


_logger: ActivityLogInterface = NullActivityLogger()


def register_activity_logger(logger: ActivityLogInterface) -> None:
    global _logger
    _logger = logger


def get_registered_activity_logger() -> ActivityLogInterface:
    return _logger


def instrument_activity_methods(service_class, mapping: dict[str, tuple[str, str]]) -> None:
    """Attach boundary-safe activity logging to service mutation methods."""
    for method_name, (action, entity_type) in mapping.items():
        original = getattr(service_class, method_name, None)
        if original is None or getattr(original, "_activity_instrumented", False):
            continue
        method_signature = signature(original)

        @wraps(original)
        def wrapped(self, *args, __original=original, __signature=method_signature,
                    __action=action, __entity_type=entity_type, **kwargs):
            bound = __signature.bind(self, *args, **kwargs)
            result = __original(self, *args, **kwargs)
            tenant = bound.arguments.get("tenant")
            organization_id = getattr(tenant, "organization_id", None) or bound.arguments.get("organization_id")
            actor_id = getattr(tenant, "user_id", None)
            if organization_id is not None and result is not None and result is not False:
                entity = getattr(result, "id", None)
                if entity is None:
                    entity = next((value for key, value in bound.arguments.items() if key.endswith("_id") and key != "organization_id"), None)
                name = getattr(result, "name", None) or getattr(result, "code", None) or getattr(result, "full_name", None)
                try:
                    get_registered_activity_logger().log_activity(
                        self.db, organization_id, __action, __entity_type,
                        entity if isinstance(entity, UUID) else None, name, actor_id,
                    )
                    self.db.commit()
                except Exception:
                    self.db.rollback()
            return result

        wrapped._activity_instrumented = True
        setattr(service_class, method_name, wrapped)
