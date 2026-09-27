from enum import Enum

from app.platform.domain.enums import PlatformAccountRole


class PlatformPermission(str, Enum):
    ORGANIZATIONS_READ = "platform:organizations:read"
    ORGANIZATIONS_CREATE = "platform:organizations:create"
    ORGANIZATIONS_UPDATE = "platform:organizations:update"
    ORGANIZATIONS_SUSPEND = "platform:organizations:suspend"
    ORGANIZATIONS_ACTIVATE = "platform:organizations:activate"
    ADMINISTRATORS_READ = "platform:administrators:read"
    ADMINISTRATORS_CREATE = "platform:administrators:create"
    ADMINISTRATORS_UPDATE = "platform:administrators:update"
    ADMINISTRATORS_DEACTIVATE = "platform:administrators:deactivate"
    SETTINGS_READ = "platform:settings:read"
    SETTINGS_MANAGE = "platform:settings:manage"
    SYSTEM_HEALTH_READ = "platform:system_health:read"
    AUDIT_READ = "platform:audit:read"
    AUDIT_EXPORT = "platform:audit:export"
    SECURITY_LOG_READ = "platform:security_log:read"
    ACTIVITY_LOG_READ = "platform:activity_log:read"


PLATFORM_ROLE_PERMISSIONS: dict[PlatformAccountRole, frozenset[PlatformPermission]] = {
    PlatformAccountRole.ROOT: frozenset(PlatformPermission),
    PlatformAccountRole.ADMIN: frozenset(
        {
            PlatformPermission.ADMINISTRATORS_READ,
            PlatformPermission.ORGANIZATIONS_READ,
            PlatformPermission.ORGANIZATIONS_UPDATE,
            PlatformPermission.SETTINGS_READ,
            PlatformPermission.SYSTEM_HEALTH_READ,
            PlatformPermission.AUDIT_READ,
            PlatformPermission.SECURITY_LOG_READ,
            PlatformPermission.ACTIVITY_LOG_READ,
        }
    ),
}


def has_platform_permission(role: PlatformAccountRole, permission: PlatformPermission) -> bool:
    return role is PlatformAccountRole.ROOT or permission in PLATFORM_ROLE_PERMISSIONS.get(role, ())
