"""The organization's audit trail (ORG-AUDIT-002): who changed what in its administration and governance.

Three separate records, each answering one question:
- audit trail (foundation_audit_log, here): who changed the administration — users, roles, permissions, the
  organization's settings, delegations, announcements — when, and the values before and after;
- security log (security_log.py): who signed in, from where, failed attempts, locks, password changes;
- activity log (activity_log.py): what happened in the daily work (customers, orders, checks, shipments…).

An audit entry is written in the transaction of the change it records (a failed write aborts the change) and is never
updated nor deleted. Passwords and tokens are never stored (sanitize_json).
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import AuditRequestContext, sanitize_json
from app.foundation.infrastructure.models import TenantAuditEntry, User

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
DELEGATION_CREATED = "delegation.created"
DELEGATION_APPROVED = "delegation.approved"
DELEGATION_REJECTED = "delegation.rejected"
DELEGATION_REVOKED = "delegation.revoked"
ANNOUNCEMENT_SENT = "announcement.sent"
ANNOUNCEMENT_WITHDRAWN = "announcement.withdrawn"


def log_tenant_audit(
    db: Session, organization_id: UUID, action: str, entity_type: str,
    entity_id: UUID | str | None = None, actor_id: UUID | None = None,
    actor_name: str | None = None, actor_email: str | None = None,
    target_display: str | None = None, details: Any = None,
    request_context: AuditRequestContext | None = None,
) -> None:
    """Records one administrative change in the caller's transaction; a failed write aborts the change."""
    try:
        if actor_id and not actor_name:
            actor_name = db.scalar(select(User.full_name).where(User.id == actor_id))
        db.add(TenantAuditEntry(organization_id=organization_id, action=action[:80], entity_type=entity_type[:50],
                                entity_id=str(entity_id)[:64] if entity_id else None, entity_name=(target_display or "")[:255] or None,
                                actor_id=actor_id, actor_name=(actor_name or actor_email or "")[:255] or None,
                                details=sanitize_json(details) if details is not None else None))
        db.flush()
    except Exception:
        db.rollback()
        raise


class FoundationAuditTrail:
    """core/interfaces/audit_trail: other modules record their governance changes here, never in foundation's tables."""

    def record(self, db, organization_id, action, entity_type, entity_id=None, entity_name=None, actor_id=None, details=None) -> None:
        log_tenant_audit(db, organization_id, action, entity_type, entity_id, actor_id, target_display=entity_name, details=details)
