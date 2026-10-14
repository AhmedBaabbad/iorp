"""Notification permissions (PROJECT-NOTIFY-001): the single source of every notifications permission code.

Every user reads their own notifications with no permission. Announcements are messages written by a person:
  announcements:send    write an announcement to named users, a role's members or the whole organization, and follow
                        who has read and acknowledged the ones they sent
  announcements:manage  follow and withdraw every announcement of the organization
Pure: no imports from other modules.
"""

MODULE = "notifications"

RESOURCES: dict[str, tuple[str, ...]] = {
    "announcements": ("send", "manage"),
}


def code(resource: str, action: str) -> str:
    assert action in RESOURCES[resource], f"{resource}:{action} is not a notifications permission"
    return f"{MODULE}:{resource}:{action}"


ALL: tuple[str, ...] = tuple(code(resource, action) for resource, actions in RESOURCES.items() for action in actions)
ANNOUNCEMENTS_SEND, ANNOUNCEMENTS_MANAGE = (code("announcements", a) for a in RESOURCES["announcements"])

LABELS: dict[str, tuple[str, str]] = {
    ANNOUNCEMENTS_SEND: ("Send Announcements", "إرسال الإعلانات والرسائل"),
    ANNOUNCEMENTS_MANAGE: ("Manage All Announcements", "إدارة كل الإعلانات"),
}
