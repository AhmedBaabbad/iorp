"""Notifications (PROJECT-NOTIFY-001): the inbox of each user, the announcements written by people, and the provider that
modules reach through core/interfaces/notifications. The notifications module is the only writer of its tables; it finds
people through core/interfaces/user_directory (answered by foundation)."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select, update

from app.core.interfaces import audit_trail
from app.core.interfaces import notifications as N
from app.core.interfaces.user_directory import directory
from app.core.pagination import page_of, paginate
from app.core.utils import utc_now
from app.notifications.domain import permissions as P
from app.notifications.domain import rules as R
from app.notifications.domain.rules import NotificationError
from app.notifications.infrastructure.models import Announcement, NotificationItem

Item = NotificationItem


def _plain(value):
    """Params are kept as JSON: ids, dates and amounts as text."""
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(v) for v in value]
    if isinstance(value, (UUID, Decimal, date, datetime)):
        return str(value)
    return value


def recipients(db, organization_id, audience: N.Audience, actor_user_id=None) -> set[UUID]:
    """The active users of the organization the audience names, without the person who did it (unless asked)."""
    people = directory()
    active = people.active_users(db, organization_id)
    found = set(active) if audience.everyone else set(audience.users) & active
    if audience.permission:
        found |= people.holders(db, organization_id, audience.permission) & active
    if audience.role_id:
        found |= people.role_members(db, organization_id, audience.role_id) & active
    found -= set(audience.exclude)
    if actor_user_id and not audience.include_actor:
        found.discard(actor_user_id)
    return found


class NotificationProvider:
    """core/interfaces/notifications: adds the notices to the caller's session (committed with its change)."""

    def send(self, db, organization_id, audience, notice, actor_user_id, announcement_id=None) -> int:
        if notice.category not in N.CATEGORIES or notice.severity not in N.SEVERITIES:
            raise ValueError(f"notice {notice.event}: unknown category or severity")
        people = recipients(db, organization_id, audience, actor_user_id)
        if notice.resource_id is not None and people:
            # The same waiting notice about the same document is not repeated while still unread.
            waiting = set(db.scalars(select(Item.recipient_user_id).where(
                Item.organization_id == organization_id, Item.event == notice.event, Item.resource_id == notice.resource_id,
                Item.read_at.is_(None), Item.settled_at.is_(None), Item.recipient_user_id.in_(people))))
            people -= waiting
        if not people:
            return 0
        actor_name = directory().names(db, organization_id, [actor_user_id]).get(actor_user_id) if actor_user_id else None
        params, now = _plain(notice.params), utc_now()
        db.add_all([Item(organization_id=organization_id, recipient_user_id=user_id, event=notice.event, category=notice.category,
                         severity=notice.severity, params=params, link=notice.link, resource_type=notice.resource_type,
                         resource_id=notice.resource_id, actor_user_id=actor_user_id, actor_name=actor_name,
                         announcement_id=announcement_id, created_at=now) for user_id in people])
        return len(people)

    def settle(self, db, organization_id, resource_type, resource_id, events=None) -> int:
        query = update(Item).where(Item.organization_id == organization_id, Item.resource_type == resource_type,
                                   Item.resource_id == resource_id, Item.settled_at.is_(None))
        if events:
            query = query.where(Item.event.in_(events))
        return db.execute(query.values(settled_at=utc_now()).execution_options(synchronize_session=False)).rowcount or 0


def _live_announcement(now):
    """Notices of an announcement that was withdrawn or has expired are no longer shown."""
    return or_(Item.announcement_id.is_(None), Item.announcement_id.in_(
        select(Announcement.id).where(Announcement.withdrawn_at.is_(None),
                                      or_(Announcement.expires_at.is_(None), Announcement.expires_at > now))))


class InboxService:
    """One user's own notifications; nobody else's are ever read or changed here."""

    def __init__(self, db, tenant):
        self.db, self.tenant = db, tenant

    def _mine(self):
        return select(Item).where(Item.organization_id == self.tenant.organization_id, Item.recipient_user_id == self.tenant.user_id,
                                  Item.hidden_at.is_(None), _live_announcement(utc_now()))

    def _unread(self):
        return and_(Item.read_at.is_(None), Item.settled_at.is_(None))

    def _pending_ack(self):
        return and_(Item.announcement_id.isnot(None), Item.acknowledged_at.is_(None), Item.announcement_id.in_(
            select(Announcement.id).where(Announcement.requires_ack.is_(True))))

    def view(self, rows) -> list[dict]:
        ids = {r.announcement_id for r in rows if r.announcement_id}
        notes = {a.id: a for a in self.db.scalars(select(Announcement).where(Announcement.id.in_(ids)))} if ids else {}
        out = []
        for r in rows:
            a = notes.get(r.announcement_id)
            out.append(dict(id=r.id, event=r.event, category=r.category, severity=r.severity, params=r.params or {}, link=r.link,
                            actor_name=r.actor_name, created_at=r.created_at, read=r.read_at is not None, settled=r.settled_at is not None,
                            announcement=None if a is None else dict(id=a.id, title=a.title, body=a.body, requires_ack=a.requires_ack,
                                                                     acknowledged=r.acknowledged_at is not None)))
        return out

    def page(self, params, kind: str = "all"):
        query = self._mine()
        if kind == "unread":
            query = query.where(self._unread())
        elif kind == "important":
            query = query.where(Item.severity.in_((N.IMPORTANT, N.URGENT)))
        elif kind in N.CATEGORIES:
            query = query.where(Item.category == kind)
        rows, total = paginate(self.db, query.order_by(Item.created_at.desc(), Item.id.desc()), params)
        return page_of(self.view(rows), total, params)

    def summary(self) -> dict:
        """The bell: the unread count, the latest few, and the announcements still to acknowledge."""
        unread = self.db.scalar(select(func.count()).select_from(self._mine().where(self._unread()).subquery())) or 0
        latest = list(self.db.scalars(self._mine().order_by(Item.created_at.desc(), Item.id.desc()).limit(8)))
        pending = list(self.db.scalars(self._mine().where(self._pending_ack()).order_by(Item.created_at)))
        return dict(unread=int(unread), latest=self.view(latest), pending_ack=self.view(pending))

    def _own(self, item_id) -> Item:
        row = self.db.scalar(self._mine().where(Item.id == item_id))
        if row is None:
            raise NotificationError("NOTIFICATION_NOT_FOUND", 404)
        return row

    def read(self, item_id):
        row = self._own(item_id)
        row.read_at = row.read_at or utc_now()
        self.db.commit()
        return self.view([row])[0]

    def read_all(self) -> dict:
        mine = and_(Item.organization_id == self.tenant.organization_id, Item.recipient_user_id == self.tenant.user_id, Item.read_at.is_(None))
        done = self.db.execute(update(Item).where(mine).values(read_at=utc_now()).execution_options(synchronize_session=False)).rowcount
        self.db.commit()
        return dict(read=done or 0)

    def hide(self, item_id) -> dict:
        """The reader puts a notification away; an announcement waiting for their acknowledgement cannot be."""
        row = self._own(item_id)
        if row.announcement_id and row.acknowledged_at is None and self.db.scalar(
                select(Announcement.requires_ack).where(Announcement.id == row.announcement_id)):
            raise NotificationError("NOTIFICATION_NEEDS_ACK", 409)
        now = utc_now()
        row.hidden_at, row.read_at = now, row.read_at or now
        self.db.commit()
        return dict(hidden=1)

    def hide_read(self) -> dict:
        """Puts away every notification already read or dealt with (never an announcement still to acknowledge)."""
        waiting_ack = select(Announcement.id).where(Announcement.requires_ack.is_(True))
        mine = and_(Item.organization_id == self.tenant.organization_id, Item.recipient_user_id == self.tenant.user_id,
                    Item.hidden_at.is_(None), or_(Item.read_at.isnot(None), Item.settled_at.isnot(None)),
                    or_(Item.announcement_id.is_(None), Item.acknowledged_at.isnot(None), Item.announcement_id.notin_(waiting_ack)))
        done = self.db.execute(update(Item).where(mine).values(hidden_at=utc_now()).execution_options(synchronize_session=False)).rowcount
        self.db.commit()
        return dict(hidden=done or 0)

    def acknowledge(self, item_id):
        row = self._own(item_id)
        if row.announcement_id is None:
            raise NotificationError("NOT_AN_ANNOUNCEMENT")
        now = utc_now()
        row.acknowledged_at = row.acknowledged_at or now
        row.read_at = row.read_at or now
        self.db.commit()
        return self.view([row])[0]


class AnnouncementService:
    """Announcements: written by a holder of announcements:send to named users, a role's members or everyone; followed
    (who read, who acknowledged) by their author, and by a holder of announcements:manage for every announcement."""

    def __init__(self, db, tenant, permissions):
        self.db, self.tenant, self.org = db, tenant, tenant.organization_id
        self.permissions = set(permissions or ())

    @property
    def manages(self) -> bool:
        return self.tenant.is_organization_root or P.ANNOUNCEMENTS_MANAGE in self.permissions

    def _visible(self):
        query = select(Announcement).where(Announcement.organization_id == self.org)
        return query if self.manages else query.where(Announcement.author_user_id == self.tenant.user_id)

    def _get(self, announcement_id) -> Announcement:
        row = self.db.scalar(self._visible().where(Announcement.id == announcement_id))
        if row is None:
            raise NotificationError("ANNOUNCEMENT_NOT_FOUND", 404)
        return row

    def _counts(self, ids) -> dict:
        if not ids:
            return {}
        rows = self.db.execute(select(Item.announcement_id, func.count(Item.read_at), func.count(Item.acknowledged_at))
                               .where(Item.announcement_id.in_(ids)).group_by(Item.announcement_id)).all()
        return {r[0]: (r[1], r[2]) for r in rows}

    def view(self, rows) -> list[dict]:
        counts, now = self._counts([r.id for r in rows]), utc_now()
        return [dict(id=a.id, title=a.title, body=a.body, severity=a.severity, requires_ack=a.requires_ack, audience=a.audience,
                     audience_label=a.audience_label, recipient_count=a.recipient_count, author_name=a.author_name, created_at=a.created_at,
                     expires_at=a.expires_at, withdrawn_at=a.withdrawn_at, withdrawn_by_name=a.withdrawn_by_name,
                     state="withdrawn" if a.withdrawn_at else "expired" if a.expires_at and a.expires_at <= now else "live",
                     read_count=counts.get(a.id, (0, 0))[0], acknowledged_count=counts.get(a.id, (0, 0))[1],
                     can_withdraw=a.withdrawn_at is None and (self.manages or a.author_user_id == self.tenant.user_id))
                for a in rows]

    def page(self, params, search: str | None = None, state: str | None = None):
        query, now = self._visible(), utc_now()
        if state == "live":
            query = query.where(Announcement.withdrawn_at.is_(None), or_(Announcement.expires_at.is_(None), Announcement.expires_at > now))
        elif state == "expired":
            query = query.where(Announcement.withdrawn_at.is_(None), Announcement.expires_at <= now)
        elif state == "withdrawn":
            query = query.where(Announcement.withdrawn_at.isnot(None))
        if search and search.strip():
            like = f"%{search.strip()}%"
            query = query.where(or_(Announcement.title.ilike(like), Announcement.body.ilike(like)))
        rows, total = paginate(self.db, query.order_by(Announcement.created_at.desc(), Announcement.id.desc()), params)
        return page_of(self.view(rows), total, params)

    def detail(self, announcement_id) -> dict:
        """The announcement and each recipient: when they read it and when they acknowledged it."""
        a = self._get(announcement_id)
        rows = self.db.execute(select(Item.recipient_user_id, Item.read_at, Item.acknowledged_at).where(Item.announcement_id == a.id)).all()
        names = directory().names(self.db, self.org, [r[0] for r in rows])
        receipts = sorted((dict(user_id=r[0], name=names.get(r[0], ""), read_at=r[1], acknowledged_at=r[2]) for r in rows),
                          key=lambda x: (x["read_at"] is not None, x["name"]))
        return dict(**self.view([a])[0], receipts=receipts)

    def options(self) -> dict:
        people = directory()
        users = people.active_users(self.db, self.org)
        names = people.names(self.db, self.org, users)
        return dict(users=sorted((dict(id=i, name=n) for i, n in names.items()), key=lambda u: u["name"]),
                    roles=people.roles(self.db, self.org))

    def create(self, data) -> dict:
        if data.audience not in R.AUDIENCES or data.severity not in N.SEVERITIES:
            raise NotificationError("ANNOUNCEMENT_INVALID")
        title, body = data.title.strip(), data.body.strip()
        if not title or not body:
            raise NotificationError("ANNOUNCEMENT_EMPTY")
        if data.expires_at is not None and data.expires_at <= utc_now():
            raise NotificationError("ANNOUNCEMENT_EXPIRY_PAST")
        people = directory()
        label = None
        if data.audience == R.AUDIENCE_USERS:
            if not data.user_ids:
                raise NotificationError("ANNOUNCEMENT_NO_AUDIENCE")
            audience = N.Audience(users=tuple(data.user_ids), include_actor=True)
        elif data.audience == R.AUDIENCE_ROLE:
            role = next((r for r in people.roles(self.db, self.org) if r["id"] == data.role_id), None)
            if role is None:
                raise NotificationError("ANNOUNCEMENT_NO_AUDIENCE")
            audience, label = N.Audience(role_id=role["id"], include_actor=True), role["name"]
        else:
            audience = N.Audience(everyone=True, include_actor=True)
        targets = recipients(self.db, self.org, audience, self.tenant.user_id)
        if not targets:
            raise NotificationError("ANNOUNCEMENT_NO_RECIPIENTS")
        author = people.names(self.db, self.org, [self.tenant.user_id]).get(self.tenant.user_id, "")
        row = Announcement(organization_id=self.org, author_user_id=self.tenant.user_id, author_name=author, title=title, body=body,
                           severity=data.severity, requires_ack=data.requires_ack, audience=data.audience,
                           audience_role_id=data.role_id if data.audience == R.AUDIENCE_ROLE else None, audience_label=label,
                           recipient_count=len(targets), expires_at=data.expires_at)
        self.db.add(row)
        self.db.flush()
        NotificationProvider().send(self.db, self.org, N.Audience(users=tuple(targets), include_actor=True),
                                    N.Notice(event=R.ANNOUNCEMENT_EVENT, category=N.ANNOUNCEMENT, severity=data.severity,
                                             params=dict(title=title), link="/notifications"),
                                    self.tenant.user_id, announcement_id=row.id)
        audit_trail.record(self.db, self.org, "announcement.sent", "announcement", row.id, title, self.tenant.user_id,
                           dict(severity=row.severity, requires_ack=row.requires_ack, audience=row.audience, audience_label=label,
                                recipients=row.recipient_count))
        self.db.commit()
        return self.detail(row.id)

    def withdraw(self, announcement_id) -> dict:
        a = self._get(announcement_id)
        if not (self.manages or a.author_user_id == self.tenant.user_id):
            raise NotificationError("ANNOUNCEMENT_FORBIDDEN", 403)
        if a.withdrawn_at is None:
            a.withdrawn_at = utc_now()
            a.withdrawn_by_name = directory().names(self.db, self.org, [self.tenant.user_id]).get(self.tenant.user_id)
            audit_trail.record(self.db, self.org, "announcement.withdrawn", "announcement", a.id, a.title, self.tenant.user_id)
            self.db.commit()
        return self.detail(a.id)


def purge(db, now: datetime | None = None) -> int:
    """Removes read (or dealt-with) notifications older than the retention; an announcement's notices are kept with it."""
    limit = (now or utc_now()) - timedelta(days=R.RETENTION_DAYS)
    old = and_(Item.created_at < limit, Item.announcement_id.is_(None), or_(Item.read_at.isnot(None), Item.settled_at.isnot(None)))
    done = db.execute(delete(Item).where(old).execution_options(synchronize_session=False)).rowcount or 0
    db.commit()
    return done
