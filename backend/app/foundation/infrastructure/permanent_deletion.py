"""Fail-closed reference inventory: metadata only, no other module's models.

Exemptions are owner rows, not entire tables: assigning somebody else's role
remains history, even though the user's own role bindings are disposable.
"""
from sqlalchemy import and_, delete, false, func, not_, or_, select, update
from sqlalchemy.dialects.postgresql import JSONB
from app.core.db import Base

SELF_OWNED = {
    'foundation_user_roles':'user_id',
    'foundation_password_reset_tokens':'user_id',
    'foundation_user_email_changes':'user_id',
}
SELF_SESSION_TABLE = 'core_auth_sessions'  # polymorphic account_id, no tenant-user FK
EXTRA_HISTORY = {
    'foundation_audit_log':('actor_id',),
    'foundation_role_assignment_removals':('user_id',),
    'notifications_items':('actor_user_id',),
}
SELF_SECURITY_EVENTS = frozenset({
    'tenant.login_success', 'tenant.login_failed', 'tenant.token_refreshed',
    'tenant.session_revoked', 'tenant.refresh_token_reuse_detected',
    'tenant.password_changed', 'tenant.password_reset_via_email',
    'tenant.auto_locked', 'tenant.auto_lock_expired',
})
TABLE_KEYS = {
    'commercial_customers': 'customers', 'commercial_quotes': 'quotes',
    'commercial_orders': 'orders', 'foundation_security_events': 'securityEvents',
    'foundation_audit_log': 'auditLog', 'foundation_activity_log': 'activityLog',
    'foundation_user_roles': 'roleAssignments',
    'foundation_role_assignment_removals': 'roleHistory',
    'foundation_approval_delegations': 'delegations',
    'foundation_approval_records': 'approvals', 'notifications_items': 'notifications',
    'notifications_announcements': 'announcements',
    'foundation_password_reset_tokens': 'accountTokens',
    'foundation_user_email_changes': 'emailChanges',
}

TABLE_KEYS.update({'commercial_complaint_attachments': 'complaints',
 'commercial_complaint_events': 'complaints',
 'commercial_complaint_links': 'complaints',
 'commercial_complaints': 'complaints',
 'commercial_customer_contacts': 'customerContacts',
 'commercial_customer_interactions': 'interactions',
 'commercial_customer_sites': 'deliverySites',
 'commercial_follow_ups': 'followUps',
 'commercial_quote_settings': 'organizationSettings',
 'commercial_quote_terms_snapshots': 'quotes',
 'commercial_sample_evaluations': 'samples',
 'commercial_samples': 'samples',
 'commercial_status_history': 'commercialHistory',
 'foundation_organization_branding': 'organizationSettings',
 'masterdata_products': 'products',
 'masterdata_settings': 'organizationSettings',
 'non_conformance_reports': 'nonConformanceReports',
 'procurement_events': 'procurementHistory',
 'procurement_purchase_orders': 'purchaseOrders',
 'procurement_receipts': 'receipts',
 'procurement_supplier_contacts': 'supplierContacts',
 'procurement_suppliers': 'suppliers',
 'production_allocations': 'productionAllocations',
 'production_demands': 'productionDemands',
 'production_downtime_events': 'productionDowntime',
 'production_order_status_history': 'productionHistory',
 'production_orders': 'productionOrders',
 'production_result_entries': 'productionResults',
 'production_runs': 'productionRuns',
 'production_waste_records': 'productionWaste',
 'quality_certificates': 'qualityCertificates',
 'quality_check_measurements': 'qualityMeasurements',
 'quality_checks': 'qualityChecks',
 'quality_defects': 'qualityDefects',
 'quality_ncr_actions': 'correctiveActions',
 'quality_ncr_attachments': 'attachments',
 'quality_rejections': 'qualityRejections',
 'quality_specifications': 'qualitySpecifications',
 'quality_status_history': 'qualityHistory',
 'shipping_attachments': 'attachments',
 'shipping_carriers': 'carriers',
 'shipping_drivers': 'drivers',
 'shipping_returns': 'returns',
 'shipping_shipment_events': 'shipmentHistory',
 'shipping_shipments': 'shipments',
 'shipping_vehicles': 'vehicles',
 'workforce_members': 'workforce'})


def self_owned_tables():
    owners = dict(SELF_OWNED)
    for table in Base.metadata.tables.values():
        for fk in table.foreign_keys:
            if (fk.target_fullname == 'foundation_users.id' and (fk.ondelete or '').upper() == 'CASCADE'
                    and fk.parent.name in {'user_id', 'recipient_user_id', 'account_id', 'owner_user_id'}):
                owners[table.name] = fk.parent.name
    return owners


def personal_security_condition(db, user_id, organization_id):
    """A total SQL boolean shared by the blocking probe and bulk detachment.

    PostgreSQL uses JSONB ->> operators; SQLite's JSON1 path is test-equivalent.
    Null details mean no target; arrays/scalars and unknown events fail closed.
    """
    table = Base.metadata.tables['foundation_security_events']
    details = table.c.details
    postgres = db.get_bind().dialect.name == 'postgresql'
    document = details.cast(JSONB) if postgres else details
    kind = func.jsonb_typeof(document) if postgres else func.json_type(document)
    def text(key):
        return document.op('->>')(key) if postgres else func.json_extract(document, '$.' + key)
    targets = [or_(text(key).is_(None), text(key) == str(user_id)) for key in
               ('target_user_id', 'user_id', 'account_id', 'subject_user_id', 'target_id')]
    personal_event = or_(table.c.event_type.in_(SELF_SECURITY_EVENTS),
        and_(table.c.event_type == 'tenant.sessions_ended',
             text('reason').in_(['ended_by_user', 'session_limit'])))
    return func.coalesce(and_(table.c.organization_id == organization_id,
        or_(details.is_(None), kind.in_(['object', 'null'])), personal_event, *targets), false())


def reference_tables(db,user_id,organization_id,limit=5):
    found=[]
    owners=self_owned_tables()
    for table in sorted(Base.metadata.tables.values(),key=lambda t:t.name):
        columns={fk.parent.name for fk in table.foreign_keys if fk.target_fullname=='foundation_users.id'}
        columns.update(EXTRA_HISTORY.get(table.name,()))
        if columns:
            condition=or_(*(table.c[column]==user_id for column in sorted(columns)))
        else:continue
        owner=owners.get(table.name)
        if owner:
            not_owned=or_(table.c[owner].is_(None),table.c[owner]!=user_id)
            if 'organization_id' in table.c:
                not_owned=or_(not_owned,table.c.organization_id.is_(None),table.c.organization_id!=organization_id)
            condition=and_(condition,not_owned)
        # No organization filter: even a corrupt cross-tenant reference must block deletion.
        if table.name=='foundation_security_events':
            condition=and_(condition,not_(personal_security_condition(db,user_id,organization_id)))
            blocking=db.scalar(select(1).select_from(table).where(condition).limit(1)) is not None
        else:blocking=db.scalar(select(1).select_from(table).where(condition).limit(1)) is not None
        if blocking:
            key=TABLE_KEYS.get(table.name,table.name)
            if key not in found:found.append(key)
            if len(found)==limit:break
    return found


def detach_personal_security(db,user):
    table=Base.metadata.tables['foundation_security_events']
    count=db.execute(update(table).where(table.c.actor_id==user.id,
        personal_security_condition(db,user.id,user.organization_id))
        .values(actor_id=None,actor_email=func.coalesce(table.c.actor_email,user.email))).rowcount
    return {'foundation_security_events':count} if count else {}


def delete_owned_rows(db,user_id,organization_id):
    counts={}
    for name,owner in self_owned_tables().items():
        table=Base.metadata.tables[name]
        scope=table.c[owner]==user_id
        if 'organization_id' in table.c:scope=and_(scope,table.c.organization_id==organization_id)
        counts[name]=db.execute(delete(table).where(scope)).rowcount
    table=Base.metadata.tables[SELF_SESSION_TABLE]
    counts[SELF_SESSION_TABLE]=db.execute(delete(table).where(table.c.account_type=='tenant',table.c.account_id==user_id,
        table.c.organization_id==organization_id)).rowcount
    return {table:count for table,count in counts.items() if count}
