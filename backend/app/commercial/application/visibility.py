"""Who sees which quotation, sales order and sample (RBAC-002).

A sales representative works with their own customers: a quotation, a sales order or a sample belongs to its customer,
and its customer to a sales owner. When a user's read permission is limited to their own records (scope "own"; "team"
is treated as "own" until teams exist), they see, open and act only on those of the customers they own. A broader
scope (organization) or the organization's root sees them all. Every write first reads the record through the same
filter, so a record one cannot see cannot be changed either.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.authorization.scope_resolver import resolve_effective_scope
from app.core.interfaces.authorization_policy import AccessScope
from app.core.tenancy import TenantContext

QUOTES_READ, ORDERS_READ, SAMPLES_READ = "commercial:quotes:read", "commercial:orders:read", "commercial:samples:read"


def visible_owner(db: Session, tenant: TenantContext, read_permission: str) -> UUID | None:
    """The sales owner whose customers' records the user may see, or None when the user sees the whole organization."""
    if tenant.is_organization_root:
        return None
    # Without any grant of the read permission there is no read scope to apply: the route has already checked the
    # permission the action needs (e.g. editing), as before RBAC-002.
    scope = resolve_effective_scope(db, tenant.user_id, tenant.organization_id, read_permission, False,
                                    fallback=AccessScope.ORGANIZATION)
    return None if scope == AccessScope.ORGANIZATION else tenant.user_id
