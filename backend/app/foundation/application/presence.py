"""Tenant presence. Refresh and platform authentication never call this module."""
from datetime import timedelta, timezone
from sqlalchemy import or_, update
from sqlalchemy.orm.attributes import set_committed_value
from app.core.utils import utc_now
from app.foundation.domain.enums import UserStatus
from app.foundation.infrastructure.models import User

PRESENCE_WINDOW = timedelta(minutes=5)
PRESENCE_THROTTLE = timedelta(seconds=60)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def is_online(user, now=None):
    now=now or utc_now()
    seen=aware(user.last_seen_at)
    return bool(user.status == UserStatus.ACTIVE and seen and now-PRESENCE_WINDOW <= seen <= now)


def touch_presence(db, user, now=None):
    now=now or utc_now()
    if user.last_seen_at and aware(user.last_seen_at) > now-PRESENCE_THROTTLE:
        return False
    # Explicit updated_at suppresses the column's automatic onupdate default.
    with db.no_autoflush:
        changed=db.execute(update(User.__table__).where(User.id==user.id, User.organization_id==user.organization_id,
            or_(User.last_seen_at.is_(None),User.last_seen_at<=now-PRESENCE_THROTTLE))
            .values(last_seen_at=now,updated_at=User.updated_at)).rowcount
        db.commit()
    if changed:set_committed_value(user,'last_seen_at',now)
    return bool(changed)
