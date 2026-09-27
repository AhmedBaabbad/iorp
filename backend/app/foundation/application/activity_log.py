import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.audit import sanitize_json
from app.foundation.infrastructure.models import TenantActivityLog

logger = logging.getLogger(__name__)


class TenantActivityLogger:
    def log_activity(self, db: Session, organization_id: UUID, action: str, entity_type: str,
                     entity_id: UUID | None = None, entity_name: str | None = None,
                     actor_id: UUID | None = None, actor_name: str | None = None,
                     details: Any = None) -> None:
        try:
            with db.begin_nested():
                db.add(TenantActivityLog(organization_id=organization_id, action=action[:80],
                    entity_type=entity_type[:50], entity_id=entity_id,
                    entity_name=(entity_name or "")[:255] or None, actor_id=actor_id,
                    actor_name=(actor_name or "")[:255] or None,
                    details=sanitize_json(details) if details is not None else None))
                db.flush()
        except Exception:
            logger.exception("Tenant activity log write failed")


def log_tenant_activity(db: Session, organization_id: UUID, action: str, entity_type: str,
                        entity_id: UUID | None = None, entity_name: str | None = None,
                        actor_id: UUID | None = None, actor_name: str | None = None,
                        details: Any = None) -> None:
    TenantActivityLogger().log_activity(db, organization_id, action, entity_type, entity_id,
                                        entity_name, actor_id, actor_name, details)
