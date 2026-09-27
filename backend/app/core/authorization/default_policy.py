"""The organization-wide authorization behavior used by IORP v0.1."""

from typing import Any
from uuid import UUID

from app.core.interfaces.authorization_policy import AuthorizationContext


class DefaultOrganizationPolicy:
    """Pass-through policy preserving organization-wide access in v0.1.

    Permission and tenant checks remain upstream. This policy performs no
    queries, applies no filters, and adds no ownership restriction.
    """

    def can_access(self, context: AuthorizationContext) -> bool:
        return True

    def apply_query_filter(
        self,
        context: AuthorizationContext,
        query: Any,
        owner_field: str | None = None,
    ) -> Any:
        return query

    def can_access_record(
        self,
        context: AuthorizationContext,
        record_owner_id: UUID | None = None,
    ) -> bool:
        return True
