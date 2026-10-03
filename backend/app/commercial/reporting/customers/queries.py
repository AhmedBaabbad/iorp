"""Tenant and ownership constraints used by every customers report and lookup."""
from fastapi import HTTPException
from sqlalchemy import select
from app.core.authorization.scope_resolver import resolve_effective_scope
from app.core.interfaces.authorization_policy import AccessScope
from app.core.reporting.contracts import ReportLimitError
from app.commercial.infrastructure.models import Customer, CustomerInteraction, FollowUp


LIMIT = 5000


def bounded(rows):
    rows = list(rows)
    if len(rows) > LIMIT:
        raise ReportLimitError()
    return rows


def scoped(db, tenant):
    query = select(Customer).where(Customer.organization_id == tenant.organization_id)
    scope = resolve_effective_scope(db, tenant.user_id, tenant.organization_id,
                                    'commercial:customers:read', tenant.is_organization_root, fallback=AccessScope.OWN)
    # Team membership is not implemented. Never fall open to the whole organization.
    if not tenant.is_organization_root and scope != AccessScope.ORGANIZATION:
        query = query.where(Customer.sales_owner_user_id == tenant.user_id)
    return query


def customers(db, tenant, params, *, filter_created=False):
    query = scoped(db, tenant)
    if getattr(params, 'customer_id', None):
        query = query.where(Customer.id == params.customer_id)
    for field, column in [('status', Customer.status), ('sector', Customer.sector), ('city', Customer.city),
                          ('sales_owner_id', Customer.sales_owner_user_id)]:
        value = getattr(params, field, None)
        if value:
            query = query.where(column == value)
    rows = bounded(db.scalars(query.order_by(Customer.name, Customer.id).limit(LIMIT + 1)))
    if getattr(params, 'customer_id', None) and not rows:
        raise HTTPException(404, 'CUSTOMER_NOT_FOUND')
    return rows


def activities(db, tenant, ids):
    query = select(CustomerInteraction).join(Customer, Customer.id == CustomerInteraction.customer_id).where(
        Customer.organization_id == tenant.organization_id, Customer.id.in_(ids))
    scope = resolve_effective_scope(db, tenant.user_id, tenant.organization_id,
                                    'commercial:interactions:read', tenant.is_organization_root, fallback=AccessScope.OWN)
    if not tenant.is_organization_root and scope != AccessScope.ORGANIZATION:
        query = query.where(CustomerInteraction.created_by_user_id == tenant.user_id)
    return bounded(db.scalars(query.order_by(CustomerInteraction.interaction_date, CustomerInteraction.id).limit(LIMIT + 1)))


def followups(db, tenant, ids):
    query=select(FollowUp).join(Customer,Customer.id==FollowUp.customer_id).where(
        Customer.organization_id==tenant.organization_id,Customer.id.in_(ids))
    scope=resolve_effective_scope(db,tenant.user_id,tenant.organization_id,'commercial:follow_ups:read',
        tenant.is_organization_root,fallback=AccessScope.OWN)
    if not tenant.is_organization_root and scope!=AccessScope.ORGANIZATION:
        query=query.where(FollowUp.assigned_user_id==tenant.user_id)
    return bounded(db.scalars(query.order_by(FollowUp.created_at,FollowUp.id).limit(LIMIT+1)))
