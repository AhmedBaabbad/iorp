"""Tenant-scoped read adapters. References never mutate another module's records."""
from sqlalchemy import select, or_
from app.core.db import Base
from app.core.authorization.scope_resolver import resolve_effective_scope
from app.core.interfaces.authorization_policy import AccessScope

LINKS = {
    'order': ('commercial_orders', 'order_number', 'commercial:orders:read', '/commercial-orders/'),
    'shipment': ('shipping_shipments', 'shipment_no', 'shipping:shipments:read', '/shipments/'),
    'return': ('shipping_returns', 'return_no', 'shipping:returns:read', '/shipment-returns/'),
    'ncr': ('non_conformance_reports', 'report_number', 'quality:ncr_reports:read', '/non-conformance-reports/'),
}


def table(name):
    return Base.metadata.tables[name]


def user_names(db, org, ids):
    users = table('foundation_users')
    return dict(db.execute(select(users.c.id, users.c.full_name).where(users.c.organization_id == org, users.c.id.in_(ids))).all()) if ids else {}


def eligible_users(db, tenant, customer, search='', user_id=None):
    u, ur, rp, p, roles = [table(n) for n in ('foundation_users', 'foundation_user_roles', 'foundation_role_permissions', 'foundation_permissions', 'foundation_roles')]
    def grant(code):
        return select(ur.c.user_id).join(roles, roles.c.id == ur.c.role_id).join(rp, rp.c.role_id == roles.c.id).join(p, p.c.id == rp.c.permission_id).where(
            roles.c.organization_id == tenant.organization_id, p.c.organization_id == tenant.organization_id, p.c.code == code)
    query = select(u.c.id, u.c.full_name, u.c.is_organization_root).where(u.c.organization_id == tenant.organization_id, u.c.status == 'active', u.c.archived_at.is_(None),
        or_(u.c.is_organization_root.is_(True), u.c.id.in_(grant('commercial:complaints:read')) & u.c.id.in_(grant('commercial:complaints:update'))))
    if user_id:
        query = query.where(u.c.id == user_id)
    else:
        query = query.where(u.c.full_name.icontains(search, autoescape=True)).order_by(u.c.full_name, u.c.id).limit(100)
    rows = []
    for uid, name, root in db.execute(query):
        scope = resolve_effective_scope(db, uid, tenant.organization_id, 'commercial:complaints:read', root)
        if scope == AccessScope.ORGANIZATION or customer.sales_owner_user_id == uid:
            rows.append(dict(id=uid, name=name))
    return rows


def reference_query(org, customer_id, kind):
    """A record of this organization and this customer (each linkable table carries both columns)."""
    t = table(LINKS[kind][0])
    return select(t).where(t.c.organization_id == org, t.c.customer_id == customer_id)


def organization_zone(db, org):
    """The organization's time zone (core/numbering.py reads it once for every module)."""
    from app.core.numbering import organization_zone as zone
    return zone(db, org)


def organization_today(db, org):
    """Today at the organization's location: deadlines are local dates, not UTC."""
    from datetime import datetime
    return datetime.now(organization_zone(db, org)).date()
