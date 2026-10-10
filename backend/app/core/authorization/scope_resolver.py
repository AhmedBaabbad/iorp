"""Resolves a user's effective row-level scope for one permission.

A user may hold the same permission through multiple roles at different
scopes (e.g. sales_rep grants customers:read at "own", a second role grants
it at "organization"). The effective scope is the broadest one held.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.interfaces.authorization_policy import AccessScope
from app.foundation.infrastructure.models import Permission, RolePermission, UserRole

logger = logging.getLogger(__name__)

_BROADEST_FIRST = (AccessScope.ORGANIZATION, AccessScope.TEAM, AccessScope.OWN)


def resolve_effective_scope(
    db: Session,
    user_id: UUID,
    organization_id: UUID,
    permission_code: str,
    is_organization_root: bool,
    fallback: AccessScope = AccessScope.OWN,
) -> AccessScope:
    """Determine the broadest scope the user has for a permission."""
    if is_organization_root:
        return AccessScope.ORGANIZATION

    statement = (
        select(RolePermission.scope)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(
            UserRole.user_id == user_id,
            Permission.code == permission_code,
            Permission.organization_id == organization_id,
        )
        .distinct()
    )
    scope_values = set(db.scalars(statement))

    for candidate in _BROADEST_FIRST:
        if candidate.value in scope_values:
            return candidate

    # Missing or malformed grants must not widen access to the whole organization.
    logger.warning(
        "No role-permission scope found for user %s, permission %s -- defaulting to %s",
        user_id, permission_code, fallback.value,
    )
    return fallback
