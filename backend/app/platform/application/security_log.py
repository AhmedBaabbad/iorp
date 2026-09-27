import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.audit import sanitize_json
from app.platform.infrastructure.models import PlatformSecurityEvent

logger = logging.getLogger(__name__)
PLATFORM_LOGIN_SUCCESS = "platform.login_success"
PLATFORM_LOGIN_FAILED = "platform.login_failed"
PLATFORM_TOKEN_REFRESHED = "platform.token_refreshed"
PLATFORM_PASSWORD_CHANGED = "platform.password_changed"
PLATFORM_ACCOUNT_LOCKED = "platform.account_locked"
PLATFORM_ACCOUNT_UNLOCKED = "platform.account_unlocked"
PLATFORM_AUTO_LOCKED = "platform.auto_locked"


def log_platform_security(db: Session, event_type: str, actor_id: UUID | None = None,
                          actor_email: str | None = None, ip_address: str | None = None,
                          user_agent: str | None = None, details: Any = None) -> None:
    try:
        with db.begin_nested():
            db.add(PlatformSecurityEvent(event_type=event_type[:80], actor_id=actor_id,
                actor_email=(actor_email or "")[:255] or None, ip_address=(ip_address or "")[:45] or None,
                user_agent=(user_agent or "")[:500] or None,
                details=sanitize_json(details) if details is not None else None))
            db.flush()
    except Exception:
        logger.exception("Platform security log write failed")
