"""Compatibility adapter for tenant activity logging."""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.audit import AuditRequestContext, sanitize_json
from app.foundation.infrastructure.models import TenantActivityLog

logger = logging.getLogger(__name__)

USER_CREATED = "user.created"
USER_UPDATED = "user.updated"
USER_DEACTIVATED = "user.deactivated"
USER_ACTIVATED = "user.activated"
USER_LOCKED = "user.locked"
USER_UNLOCKED = "user.unlocked"
USER_PASSWORD_CHANGED = "user.password_changed"
USER_PASSWORD_RESET = "user.password_reset"
USER_AUTO_LOCKED = "user.auto_locked"
ROLE_CREATED = "role.created"
ROLE_UPDATED = "role.updated"
ROLE_DELETED = "role.deleted"
ROLE_ASSIGNED = "role_assignment.added"
ROLE_REMOVED = "role_assignment.removed"
ROLE_PERMISSIONS_UPDATED = "role.permissions_updated"
ORG_PROFILE_UPDATED = "organization.profile_updated"
ORG_LOGO_UPLOADED = "organization.logo_uploaded"
ORG_LOGO_REMOVED = "organization.logo_removed"


def log_tenant_audit(
    db: Session, organization_id: UUID, action: str, entity_type: str,
    entity_id: UUID | str | None = None, actor_id: UUID | None = None,
    actor_name: str | None = None, actor_email: str | None = None,
    target_display: str | None = None, details: Any = None,
    request_context: AuditRequestContext | None = None,
) -> None:
    """Governance audit is mandatory and belongs to the caller's transaction.

    Unlike best-effort activity telemetry, a failed audit aborts the mutation.
    """
    try:
        db.add(TenantActivityLog(organization_id=organization_id, action=action[:80], entity_type=entity_type[:50],
            entity_id=entity_id if isinstance(entity_id, UUID) else None, entity_name=(target_display or '')[:255] or None,
            actor_id=actor_id, actor_name=(actor_name or actor_email or '')[:255] or None,
            details=sanitize_json(details) if details is not None else None))
        db.flush()
    except Exception:
        db.rollback()
        raise
