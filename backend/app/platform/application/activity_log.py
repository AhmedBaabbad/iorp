import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.audit import sanitize_json
from app.platform.infrastructure.models import PlatformActivityLog

logger = logging.getLogger(__name__)


def log_platform_activity(db: Session, action: str, entity_type: str,
                          entity_id: UUID | None = None, entity_name: str | None = None,
                          actor_id: UUID | None = None, actor_name: str | None = None,
                          details: Any = None) -> None:
    try:
        with db.begin_nested():
            db.add(PlatformActivityLog(action=action[:80], entity_type=entity_type[:50],
                entity_id=entity_id, entity_name=(entity_name or "")[:255] or None,
                actor_id=actor_id, actor_name=(actor_name or "")[:255] or None,
                details=sanitize_json(details) if details is not None else None))
            db.flush()
    except Exception:
        logger.exception("Platform activity log write failed")
