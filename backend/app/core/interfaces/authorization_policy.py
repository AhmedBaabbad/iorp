"""Shared contract for future row-level authorization policies."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable
from uuid import UUID


class AccessScope(str, Enum):
    """Breadth of record access granted by a future scoped permission."""

    OWN = "own"
    TEAM = "team"
    ORGANIZATION = "organization"


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    """Inputs needed by a policy after the ordinary permission check."""

    user_id: UUID
    organization_id: UUID
    is_organization_root: bool
    permission_code: str
    effective_scope: AccessScope = AccessScope.ORGANIZATION


@runtime_checkable
class AuthorizationPolicy(Protocol):
    """Extension contract for restrictions beyond binary permissions."""

    def can_access(self, context: AuthorizationContext) -> bool:
        """Return whether the resource type can be accessed at all."""
        ...

    def apply_query_filter(
        self,
        context: AuthorizationContext,
        query: Any,
        owner_field: str | None = None,
    ) -> Any:
        """Return the query with any policy-specific row filter applied."""
        ...

    def can_access_record(
        self,
        context: AuthorizationContext,
        record_owner_id: UUID | None = None,
    ) -> bool:
        """Return whether one already tenant-scoped record is accessible."""
        ...
