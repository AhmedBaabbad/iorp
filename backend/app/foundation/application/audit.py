"""Compatibility adapter for tenant activity logging."""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.audit import AuditRequestContext
from app.foundation.application.activity_log import log_tenant_activity

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
    """Record a tenant business activity in its dedicated append-only table."""
    try:
        log_tenant_activity(db, organization_id, action, entity_type,
                            entity_id if isinstance(entity_id, UUID) else None,
                            target_display, actor_id, actor_name or actor_email, details)
    except Exception:
        logger.exception("Tenant audit logging failed", extra={"organization_id": str(organization_id), "action": action})
