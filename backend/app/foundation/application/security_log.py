import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.audit import sanitize_json
from app.foundation.infrastructure.models import TenantSecurityEvent

logger = logging.getLogger(__name__)
TENANT_LOGIN_SUCCESS = "tenant.login_success"
TENANT_LOGIN_FAILED = "tenant.login_failed"
TENANT_TOKEN_REFRESHED = "tenant.token_refreshed"
TENANT_PASSWORD_CHANGED = "tenant.password_changed"
TENANT_ACCOUNT_LOCKED = "tenant.account_locked"
TENANT_ACCOUNT_UNLOCKED = "tenant.account_unlocked"
TENANT_AUTO_LOCKED = "tenant.auto_locked"
TENANT_AUTO_LOCK_EXPIRED = "tenant.auto_lock_expired"


def log_tenant_security(db: Session, organization_id: UUID, event_type: str,
                        actor_id: UUID | None = None, actor_email: str | None = None,
                        ip_address: str | None = None, user_agent: str | None = None,
                        details: Any = None) -> None:
    try:
        with db.begin_nested():
            db.add(TenantSecurityEvent(organization_id=organization_id, event_type=event_type[:80],
                actor_id=actor_id, actor_email=(actor_email or "")[:255] or None,
                ip_address=(ip_address or "")[:45] or None, user_agent=(user_agent or "")[:500] or None,
                details=sanitize_json(details) if details is not None else None))
            db.flush()
    except Exception:
        logger.exception("Tenant security log write failed")
