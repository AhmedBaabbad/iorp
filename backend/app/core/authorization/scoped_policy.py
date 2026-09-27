"""v0.2 authorization policy: applies ownership filtering based on scope.

Replaces DefaultOrganizationPolicy as the wiring for get_authorization_policy().
Organization filtering itself remains the repository's job (via
organization_id/tenant-scoped queries); this policy only ever narrows an
already tenant-scoped query further -- it never widens it.
"""

import logging
from typing import Any
from uuid import UUID

from app.core.interfaces.authorization_policy import AccessScope, AuthorizationContext

logger = logging.getLogger(__name__)


class ScopedAuthorizationPolicy:
    """Applies own/team/organization row-level filtering after the ordinary
    permission check has already passed.

    - organization: no filter (see all org records) -- current v0.1 behavior.
    - own: filter to rows whose owner_field equals the current user.
    - team: not implemented in v0.1 -- fails open to organization (logged).
    """

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

        if context.effective_scope == AccessScope.ORGANIZATION:
            return query

        if context.effective_scope == AccessScope.TEAM:
            logger.warning(
                "Team scope not implemented, falling back to organization for user %s (%s)",
                context.user_id, context.permission_code,
            )
            return query

        if context.effective_scope == AccessScope.OWN:
            if not owner_field:
                # Entity has no ownership concept -- nothing to narrow by.
                return query
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

        if context.effective_scope == AccessScope.ORGANIZATION:
            return True

        if context.effective_scope == AccessScope.TEAM:
            logger.warning(
                "Team scope not implemented, falling back to organization for user %s (%s)",
                context.user_id, context.permission_code,
            )
            return True

        if context.effective_scope == AccessScope.OWN:
            if record_owner_id is None:
                # No owner recorded on this row -- nothing to restrict against.
                return True
            return record_owner_id == context.user_id

        return True
