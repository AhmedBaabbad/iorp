"""The organization's security log (ORG-AUDIT-002): who signed in, when and from which device; failed attempts, locks,
password changes, a reused (stolen) session.

- A routine success repeats many times a day: signing in again from the same device within MERGE_WINDOW adds to the
  same entry (how many times, and the last time) instead of a new one. Every failure or incident is its own entry.
- Kept as long as useful (purge(), run daily): routine entries ROUTINE_DAYS, everything else INCIDENT_DAYS.
"""
import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.audit import sanitize_json
from app.core.utils import utc_now
from app.foundation.infrastructure.models import TenantSecurityEvent as Event

logger = logging.getLogger(__name__)
TENANT_LOGIN_SUCCESS = "tenant.login_success"
TENANT_LOGIN_FAILED = "tenant.login_failed"
TENANT_TOKEN_REFRESHED = "tenant.token_refreshed"
TENANT_PASSWORD_CHANGED = "tenant.password_changed"
TENANT_ACCOUNT_LOCKED = "tenant.account_locked"
TENANT_ACCOUNT_UNLOCKED = "tenant.account_unlocked"
TENANT_AUTO_LOCKED = "tenant.auto_locked"
TENANT_AUTO_LOCK_EXPIRED = "tenant.auto_lock_expired"
TENANT_SESSIONS_ENDED = "tenant.sessions_ended"  # SEC-001: by the user, an administrator, or the session limit

ROUTINE = (TENANT_LOGIN_SUCCESS,)  # shown on request; merged; kept ROUTINE_DAYS
MERGE_WINDOW = timedelta(minutes=30)
ROUTINE_DAYS, INCIDENT_DAYS = 90, 365


def _merged(db: Session, organization_id, event_type, actor_id, ip_address, user_agent, now) -> bool:
    """The same person signing in again from the same device shortly after: counted on the existing entry."""
    if event_type not in ROUTINE or actor_id is None:
        return False
    recent = db.scalar(select(Event).where(
        Event.organization_id == organization_id, Event.event_type == event_type, Event.actor_id == actor_id,
        Event.ip_address.is_(None) if ip_address is None else Event.ip_address == ip_address,
        Event.user_agent.is_(None) if user_agent is None else Event.user_agent == user_agent,
        func.coalesce(Event.last_seen_at, Event.created_at) >= now - MERGE_WINDOW,
    ).order_by(Event.created_at.desc()).limit(1).with_for_update())
    if recent is None:
        return False
    recent.occurrences = (recent.occurrences or 1) + 1
    recent.last_seen_at = now
    return True


def log_tenant_security(db: Session, organization_id: UUID, event_type: str,
                        actor_id: UUID | None = None, actor_email: str | None = None,
                        ip_address: str | None = None, user_agent: str | None = None,
                        details: Any = None) -> None:
    ip_address, user_agent = (ip_address or "")[:45] or None, (user_agent or "")[:500] or None
    try:
        with db.begin_nested():
            now = utc_now()
            if not _merged(db, organization_id, event_type, actor_id, ip_address, user_agent, now):
                db.add(Event(organization_id=organization_id, event_type=event_type[:80], actor_id=actor_id,
                             actor_email=(actor_email or "")[:255] or None, ip_address=ip_address, user_agent=user_agent,
                             details=sanitize_json(details) if details is not None else None, created_at=now, occurrences=1))
            db.flush()
    except Exception:
        logger.exception("Tenant security log write failed")


def purge(db: Session, now: datetime | None = None) -> int:
    """Removes routine entries older than ROUTINE_DAYS and the others older than INCIDENT_DAYS."""
    now = now or utc_now()
    last = func.coalesce(Event.last_seen_at, Event.created_at)
    old = or_(and_(Event.event_type.in_(ROUTINE), last < now - timedelta(days=ROUTINE_DAYS)),
              and_(Event.event_type.notin_(ROUTINE), last < now - timedelta(days=INCIDENT_DAYS)))
    done = db.execute(delete(Event).where(old).execution_options(synchronize_session=False)).rowcount or 0
    db.commit()
    return done
