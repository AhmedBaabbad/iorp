"""EXAMPLE ONLY -- not imported or used by IORP v0.1.

This illustrates one possible future ownership policy. Production wiring must
also preserve organization filtering and must use a validated model attribute,
not client-provided field names.
"""

from typing import Any
from uuid import UUID

from app.core.interfaces.authorization_policy import AccessScope, AuthorizationContext


class OwnRecordsPolicy:
    """Future example restricting OWN scope to records owned by the user."""

    def can_access(self, context: AuthorizationContext) -> bool:
        return True

    def apply_query_filter(
        self,
        context: AuthorizationContext,
        query: Any,
        owner_field: str | None = None,
    ) -> Any:
        if context.is_organization_root:
            return query
        if context.effective_scope == AccessScope.OWN and owner_field:
            entity = query.column_descriptions[0]["entity"]
            return query.where(getattr(entity, owner_field) == context.user_id)
        return query

    def can_access_record(
        self,
        context: AuthorizationContext,
        record_owner_id: UUID | None = None,
    ) -> bool:
        if context.is_organization_root:
            return True
        if context.effective_scope == AccessScope.OWN:
            return record_owner_id == context.user_id
        return True
