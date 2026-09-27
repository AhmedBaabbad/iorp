from enum import Enum


class OrganizationStatus(str, Enum):
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    LOCKED = "locked"
