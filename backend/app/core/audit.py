from dataclasses import dataclass
import json
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session
from fastapi import Request

from app.core.security_models import AuthSecurityEvent
from app.core.rate_limit import get_client_ip

_SENSITIVE_PARTS = (
    "password", "secret", "token", "authorization", "cookie", "credential", "api_key", "apikey",
)
MAX_REASON = 120
MAX_JSON_CHARS = 16_000


def is_sensitive_key(key: object) -> bool:
    normalized = str(key).lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_PARTS)


def sanitize_audit_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 8:
        return "[truncated]"
    if isinstance(value, dict):
        return {
            str(key)[:128]: "***REDACTED***" if is_sensitive_key(key) else sanitize_audit_value(item, depth=depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [sanitize_audit_value(item, depth=depth + 1) for item in list(value)[:100]]
    if isinstance(value, UUID):
        return str(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:2000]


def sanitize_json(value: Any) -> Any:
    sanitized = sanitize_audit_value(value)
    encoded = json.dumps(sanitized, ensure_ascii=False, default=str)
    if len(encoded) <= MAX_JSON_CHARS:
        return sanitized
    return {"truncated": True, "preview": encoded[:MAX_JSON_CHARS]}


@dataclass(frozen=True)
class AuditActor:
    actor_type: str
    actor_id: UUID | None = None
    email: str | None = None
    name: str | None = None


@dataclass(frozen=True)
class AuditRequestContext:
    request_id: str | None = None
    correlation_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None


def audit_request_context(request: Request) -> AuditRequestContext:
    return AuditRequestContext(
        request_id=getattr(request.state, "request_id", None),
        correlation_id=getattr(request.state, "correlation_id", None),
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


class PlatformAuditService:
    """Deprecated compatibility dispatcher; never writes the legacy table."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self, *, event_type: str, category: str, actor: AuditActor,
        outcome: str = "success", severity: str = "info",
        target_type: str | None = None, target_id: str | UUID | None = None,
        target_display: str | None = None, organization_id: UUID | None = None,
        reason: str | None = None, changes: Any = None, metadata: Any = None,
        error_code: str | None = None, request: AuditRequestContext | None = None,
    ) -> Any:
        context = request or AuditRequestContext()
        action_map = {
            "organization_created": "organization.created", "organization_suspended": "organization.suspended",
            "organization_activated": "organization.activated", "organization_deactivated": "organization.deactivated",
            "organization_archived": "organization.archived", "organization_root_password_reset": "organization.root_password_reset",
            "platform_account_created": "platform_account.created", "platform_account_updated": "platform_account.updated",
            "platform_account_deactivated": "platform_account.deactivated", "platform_account_password_reset": "platform_account.password_reset",
        }
        event_type = action_map.get(event_type, event_type)
        details = {"outcome": outcome, "severity": severity, "reason": reason,
                   "changes": changes, "metadata": metadata, "error_code": error_code}
        is_security = category in {"authentication", "security"}
        if actor.actor_type == "tenant" and organization_id is not None:
            if is_security:
                from app.foundation.application.security_log import log_tenant_security
                log_tenant_security(self.db, organization_id, event_type, actor.actor_id,
                                    actor.email, context.ip_address, context.user_agent, details)
            else:
                from app.foundation.application.activity_log import log_tenant_activity
                entity_uuid = target_id if isinstance(target_id, UUID) else None
                log_tenant_activity(self.db, organization_id, event_type, target_type or "event",
                                    entity_uuid, target_display, actor.actor_id, actor.name, details)
        elif is_security:
            from app.platform.application.security_log import log_platform_security
            log_platform_security(self.db, event_type, actor.actor_id if actor.actor_type == "platform" else None,
                                  actor.email, context.ip_address, context.user_agent, details)
        else:
            from app.platform.application.activity_log import log_platform_activity
            entity_uuid = target_id if isinstance(target_id, UUID) else None
            log_platform_activity(self.db, event_type, target_type or "event", entity_uuid,
                                  target_display, actor.actor_id if actor.actor_type == "platform" else None,
                                  actor.name, details)
        return None
