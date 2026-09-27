"""Platform-owned enumerations."""

from enum import Enum


class PlatformAccountStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class PlatformAccountRole(str, Enum):
    ROOT = "root"
    ADMIN = "admin"
