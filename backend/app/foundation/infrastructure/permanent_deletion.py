"""Fail-closed reference inventory: metadata only, no other module's models.

Exemptions are owner rows, not entire tables: assigning somebody else's role
remains history, even though the user's own role bindings are disposable.
"""
from sqlalchemy import and_, case, delete, false, func, not_, or_, select, update
from sqlalchemy.dialects.postgresql import JSONB
from app.core.db import Base

SELF_OWNED = {
    'foundation_user_roles':'user_id',
    'foundation_password_reset_tokens':'user_id',
    'foundation_user_email_changes':'user_id',
    # Private inbox rows (including read/ack state), never announcements authored by the user.
    'notifications_items':'recipient_user_id',
}
SELF_SESSION_TABLE = 'core_auth_sessions'  # polymorphic account_id, no tenant-user FK
EXTRA_HISTORY = {
    'foundation_audit_log':('actor_id',),
    'notifications_items':('actor_user_id',),
}
SELF_SECURITY_EVENTS = frozenset({
    'tenant.login_success', 'tenant.login_failed', 'tenant.token_refreshed',
    'tenant.session_revoked', 'tenant.refresh_token_reuse_detected',
    'tenant.password_changed', 'tenant.password_reset_via_email',
    'tenant.auto_locked', 'tenant.auto_lock_expired',
    # Explicit personal MFA event contract. Tenant MFA is not currently exposed;
    # platform_* MFA events belong to platform accounts and are never exempted here.
    'tenant.mfa_setup_started', 'tenant.mfa_enabled', 'tenant.mfa_disabled',
    'tenant.mfa_verification_failed', 'tenant.mfa_recovery_codes_regenerated',
    'tenant.mfa_recovery_code_used',
})
# Self-service writers only. user.updated also serves administration, so it needs
# both the self entity id and a profile-only change set; roles/status are work.
SELF_AUDIT_ACTIONS = frozenset({'user.password_changed', 'user.password_reset', 'user.email_change_requested', 'user.email_changed', 'user.updated'})
# The same narrow contract applies if an emitter writes these into activity.
SELF_ACTIVITY_ACTIONS = SELF_AUDIT_ACTIONS
PROFILE_FIELDS = frozenset({'full_name', 'phone', 'preferred_locale', 'timezone'})
TARGET_KEYS = ('target_user_id', 'user_id', 'account_id', 'subject_user_id', 'target_id')
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
    'core_auth_security_events': 'securityEvents',
    'core_auth_sessions': 'accountSessions',
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
    # Deliberately explicit: a future CASCADE FK is not automatically private data.
    return dict(SELF_OWNED)


def _json(db, value):
    postgres = db.get_bind().dialect.name == 'postgresql'
    document = value.cast(JSONB) if postgres else value
    kind = func.jsonb_typeof(document) if postgres else func.json_type(document)
    def text(*keys):
        return func.jsonb_extract_path_text(document, *keys) if postgres else func.json_extract(document, '$.' + '.'.join(keys))
    metadata_kind = (func.jsonb_typeof(func.jsonb_extract_path(document, 'metadata')) if postgres
                     else func.json_type(document, '$.metadata'))
    valid = and_(or_(value.is_(None), kind.in_(['object', 'null'])),
                 or_(metadata_kind.is_(None), metadata_kind.in_(['object', 'null'])))
    return document, kind, text, valid


def _targets_self(text, user_id):
    # An explicit foreign subject, including metadata used by core.audit, blocks.
    return and_(*(or_(text(*path).is_(None), text(*path) == str(user_id))
        for key in TARGET_KEYS for path in ((key,), ('metadata', key))))


def _profile_changes(db, details):
    document, kind, _text, _valid = _json(db, details)
    postgres = db.get_bind().dialect.name == 'postgresql'
    empty = func.jsonb_build_object() if postgres else '{}'
    safe = case((kind == 'object', document), else_=empty)
    entries = (func.jsonb_each(safe) if postgres else func.json_each(safe)).table_valued('key', 'value')
    return and_(kind == 'object', not_(select(1).select_from(entries).where(entries.c.key.not_in(PROFILE_FIELDS)).exists()))


def personal_security_condition(db, user_id, organization_id):
    """Total SQL boolean shared by the probe and detachment; no Python row scans."""
    table = Base.metadata.tables['foundation_security_events']
    _document, _kind, text, valid = _json(db, table.c.details)
    personal = or_(table.c.event_type.in_(SELF_SECURITY_EVENTS),
        and_(table.c.event_type == 'tenant.sessions_ended', text('reason').in_(['ended_by_user', 'session_limit'])))
    # These writers put the SUBJECT in actor_id. The actual administrator is
    # retained in performed_by/audit/inbox history; being their target is not work.
    admin_subject = or_(
        and_(table.c.event_type.in_(['tenant.account_locked', 'tenant.account_unlocked']),
             text('performed_by').is_not(None), text('performed_by') != str(user_id)),
        and_(table.c.event_type == 'tenant.sessions_ended', text('reason') == 'ended_by_admin',
             or_(text('performed_by').is_not(None), text('by').is_not(None))))
    return func.coalesce(and_(table.c.organization_id == organization_id, valid,
        or_(personal, admin_subject), _targets_self(text, user_id)), false())


def personal_log_condition(db, table, user_id, organization_id):
    _document, _kind, text, valid = _json(db, table.c.details)
    actions = SELF_AUDIT_ACTIONS if table.name == 'foundation_audit_log' else SELF_ACTIVITY_ACTIONS
    return func.coalesce(and_(table.c.organization_id == organization_id,
        table.c.action.in_(actions), table.c.entity_type == 'user',
        table.c.entity_id == str(user_id) if table.name == 'foundation_audit_log' else table.c.entity_id == user_id,
        valid, _targets_self(text, user_id),
        or_(table.c.action != 'user.updated', _profile_changes(db, table.c.details))), false())


def personal_core_security_condition(db, table, user_id, organization_id):
    _document, _kind, text, valid = _json(db, table.c['metadata'])
    return func.coalesce(and_(table.c.organization_id == organization_id,
        table.c.account_type == 'tenant', table.c.actor_type == 'tenant',
        table.c.event_type.in_(SELF_SECURITY_EVENTS), valid, _targets_self(text, user_id),
        or_(table.c.target_id.is_(None), table.c.target_id == str(user_id)),
        or_(table.c.target_type.is_(None), table.c.target_type.in_(['user', 'tenant_user', 'account']))), false())


def reference_tables(db, user_id, organization_id, limit=5, raw=False):
    found=[]
    owners=self_owned_tables()
    for table in sorted(Base.metadata.tables.values(), key=lambda t:t.name):
        columns={fk.parent.name for fk in table.foreign_keys if fk.target_fullname=='foundation_users.id'}
        columns.update(EXTRA_HISTORY.get(table.name, ()))
        condition=or_(*(table.c[column]==user_id for column in sorted(columns))) if columns else None
        if table.name == 'core_auth_sessions':
            # A polymorphic foreign-tenant session is corruption, not disposable ownership.
            condition=and_(table.c.account_type=='tenant', table.c.account_id==user_id,
                           or_(table.c.organization_id.is_(None), table.c.organization_id!=organization_id))
        elif table.name == 'core_auth_security_events':
            condition=and_(table.c.account_id==user_id,
                or_(table.c.account_type.is_(None), table.c.account_type!='platform', table.c.actor_type=='tenant'),
                not_(personal_core_security_condition(db, table, user_id, organization_id)))
        elif table.name == 'foundation_security_events':
            _document, _kind, text, _valid = _json(db, table.c.details)
            # Explicit attribution of an administrator's action must also block
            # when this table's actor_id actually denotes the other user (subject).
            condition=or_(and_(condition, not_(personal_security_condition(db,user_id,organization_id))),
                and_(text('performed_by')==str(user_id), or_(table.c.actor_id.is_(None), table.c.actor_id!=user_id)))
        elif table.name in ('foundation_audit_log', 'foundation_activity_log'):
            condition=and_(condition, not_(personal_log_condition(db,table,user_id,organization_id)))
        elif table.name == 'foundation_role_assignment_removals':
            # user_id has no FK: preserve the administrator's audit about this
            # subject. Only removed_by on someone else's removal is the user's work.
            condition=and_(table.c.removed_by==user_id, table.c.user_id!=user_id)
        if condition is None: continue
        owner=owners.get(table.name)
        if owner:
            not_owned=or_(table.c[owner].is_(None), table.c[owner]!=user_id)
            if 'organization_id' in table.c:
                not_owned=or_(not_owned,table.c.organization_id.is_(None),table.c.organization_id!=organization_id)
            condition=and_(condition,not_owned)
        # No global organization filter: corrupt cross-tenant references block.
        if db.scalar(select(1).select_from(table).where(condition).limit(1)) is not None:
            key=table.name if raw else TABLE_KEYS.get(table.name,table.name)
            if key not in found: found.append(key)
            if limit is not None and len(found)==limit: break
    return found


def detach_personal_security(db,user):
    table=Base.metadata.tables['foundation_security_events']
    count=db.execute(update(table).where(table.c.actor_id==user.id,
        personal_security_condition(db,user.id,user.organization_id))
        .values(actor_id=None,actor_email=func.coalesce(func.nullif(table.c.actor_email,''),user.email))).rowcount
    return {'foundation_security_events':count} if count else {}


def detach_personal_history(db, user):
    counts=detach_personal_security(db,user)
    for name in ('foundation_audit_log','foundation_activity_log'):
        table=Base.metadata.tables[name]
        count=db.execute(update(table).where(table.c.actor_id==user.id,
            personal_log_condition(db,table,user.id,user.organization_id))
            .values(actor_id=None,actor_name=func.coalesce(func.nullif(table.c.actor_name,''),user.full_name or user.email))).rowcount
        if count: counts[name]=count
    # Self-removals retain their subject/role audit and lose only the nullable actor FK.
    table=Base.metadata.tables['foundation_role_assignment_removals']
    count=db.execute(update(table).where(table.c.removed_by==user.id,table.c.user_id==user.id).values(removed_by=None)).rowcount
    if count: counts[table.name]=count
    table=Base.metadata.tables['core_auth_security_events']
    count=db.execute(update(table).where(table.c.account_id==user.id,
        personal_core_security_condition(db,table,user.id,user.organization_id))
        .values(account_id=None,actor_email_snapshot=func.coalesce(func.nullif(table.c.actor_email_snapshot,''),user.email),
                actor_name_snapshot=func.coalesce(func.nullif(table.c.actor_name_snapshot,''),user.full_name or user.email))).rowcount
    if count: counts[table.name]=count
    return counts


def delete_owned_rows(db,user_id,organization_id):
    counts={}
    for name,owner in self_owned_tables().items():
        table=Base.metadata.tables[name]
        scope=table.c[owner]==user_id
        if 'organization_id' in table.c: scope=and_(scope,table.c.organization_id==organization_id)
        counts[name]=db.execute(delete(table).where(scope)).rowcount
    # Deleting every rotation/family row invalidates refresh AND access tokens:
    # rotate_refresh_token requires the row; access validation requires user + session_active.
    table=Base.metadata.tables[SELF_SESSION_TABLE]
    counts[SELF_SESSION_TABLE]=db.execute(delete(table).where(table.c.account_type=='tenant',table.c.account_id==user_id,
        table.c.organization_id==organization_id)).rowcount
    return {table:count for table,count in counts.items() if count}
