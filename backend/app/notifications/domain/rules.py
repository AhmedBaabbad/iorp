"""Notification rules (PROJECT-NOTIFY-001). Pure: no imports from other modules.

- A notification belongs to one user; nobody else reads it.
- An announcement reaches named users, a role's members or the whole organization (active users only, at sending).
- An announcement that requires acknowledgement stays in front of its reader until they confirm they have read it; the
  confirmations are kept as evidence while the announcement is kept.
- Read notifications are removed after RETENTION_DAYS; an announcement's confirmations are not.
"""
from app.core.interfaces.notifications import CATEGORIES, SEVERITIES  # noqa: F401  (one vocabulary for every module)

AUDIENCE_USERS, AUDIENCE_ROLE, AUDIENCE_EVERYONE = "users", "role", "everyone"
AUDIENCES = (AUDIENCE_USERS, AUDIENCE_ROLE, AUDIENCE_EVERYONE)
ANNOUNCEMENT_EVENT = "notifications.announcement.published"
RETENTION_DAYS = 90
TITLE_MAX, BODY_MAX = 200, 5000
FILTERS = ("all", "unread", "important", *CATEGORIES)


class NotificationError(ValueError):
    def __init__(self, code: str, status_code: int = 400):
        super().__init__(code)
        self.code, self.status_code = code, status_code
