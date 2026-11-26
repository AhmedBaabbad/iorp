from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.db import Base
from app.core.security import hash_password
from app.core.utils import utc_now
from app.foundation.infrastructure.models import Role, UserRole, RoleAssignmentRemoval, TenantSecurityEvent, TenantAuditEntry, TenantActivityLog
from app.foundation.infrastructure.permanent_deletion import SELF_SECURITY_EVENTS, SELF_AUDIT_ACTIONS
from tests.foundation.test_users_ux import users, remove, BASE  # noqa: F401


def test_active_personal_account_detaches_all_logs(users):
    e=users
    e.target.password_hash=hash_password('DeleteFlow123!')
    saved_password_hash=e.target.password_hash
    e.target.last_login_at=e.target.last_seen_at=utc_now()
    security=[TenantSecurityEvent(organization_id=e.org.id,actor_id=e.target.id,event_type=kind,details={'user_id':str(e.target.id)})
              for kind in SELF_SECURITY_EVENTS]
    audit=[TenantAuditEntry(organization_id=e.org.id,actor_id=e.target.id,action=action,entity_type='user',entity_id=str(e.target.id),
        details={'phone':{'before':None,'after':'123'}} if action=='user.updated' else {}) for action in SELF_AUDIT_ACTIONS]
    activity=TenantActivityLog(organization_id=e.org.id,actor_id=e.target.id,action='user.updated',entity_type='user',entity_id=e.target.id,
                               details={'preferred_locale':{'before':'en','after':'ar'}})
    e.db.add_all([*security,*audit,activity]);e.db.commit()
    identifier=e.target.id
    security_ids=[row.id for row in security];audit_ids=[row.id for row in audit];activity_id=activity.id
    response=remove(e)
    assert response.status_code==200,response.text
    e.db.expire_all()
    assert all(row.actor_id is None and row.actor_email for row in e.db.scalars(select(TenantSecurityEvent).where(TenantSecurityEvent.id.in_(security_ids))))
    assert all(row.actor_id is None and row.actor_name for row in e.db.scalars(select(TenantAuditEntry).where(TenantAuditEntry.id.in_(audit_ids))))
    assert e.db.get(TenantActivityLog,activity_id).actor_id is None
    assert e.db.get(TenantActivityLog,activity_id).actor_name
    event=e.db.scalar(select(TenantSecurityEvent).where(TenantSecurityEvent.event_type=='user.deleted_permanently'))
    assert event.details['user_id']==str(identifier) and event.details['deleted_by']==str(e.actor.id)
    assert event.details['detached_by_table']=={'foundation_security_events':len(security),'foundation_audit_log':len(audit),'foundation_activity_log':1}
    assert saved_password_hash not in str(event.details)
    assert 'password_hash' not in event.details and 'refresh_token' not in event.details


def test_role_removed_from_subject_stays_but_actor_removal_of_others_blocks(users):
    e=users
    roles=[Role(organization_id=e.org.id,code=code,name=code,description='',is_system=False,is_protected=False) for code in ('manager','viewer')]
    e.db.add_all(roles);e.db.flush()
    removal=RoleAssignmentRemoval(user_id=e.target.id,role_id=roles[0].id,removed_by=e.actor.id)
    e.db.add_all([removal,UserRole(user_id=e.target.id,role_id=roles[1].id,assigned_by=e.actor.id)])
    e.db.commit();removal_id=removal.id;target=e.target.id
    assert remove(e).status_code==200
    e.db.expire_all();saved=e.db.get(RoleAssignmentRemoval,removal_id)
    assert saved.user_id==target and saved.removed_by==e.actor.id


def test_removed_by_on_someone_else_is_history(users):
    e=users
    row=RoleAssignmentRemoval(user_id=e.actor.id,role_id=uuid4(),removed_by=e.target.id)
    e.db.add(row);e.db.commit()
    result=remove(e)
    assert result.status_code==409 and 'foundation_role_assignment_removals' in result.json()['details']['table_names']
    e.db.refresh(row);assert row.removed_by==e.target.id


@pytest.mark.parametrize('table,values',[
    ('foundation_audit_log',dict(action='user.updated',entity_type='user',details={'status':{'before':'active','after':'locked'}})),
    ('foundation_audit_log',dict(action='user.future_event',entity_type='user',details={})),
    ('foundation_activity_log',dict(action='customer.created',entity_type='user',details={})),
    ('foundation_security_events',dict(event_type='tenant.future_event',details={})),
    ('foundation_security_events',dict(event_type='tenant.login_success',details={'metadata':{'target_user_id':str(uuid4())}})),
    ('foundation_security_events',dict(event_type='tenant.login_success',details={'metadata':[]})),
])
def test_unknown_or_administrative_history_fails_closed(users,table,values):
    e=users
    row=Base.metadata.tables[table]
    data=dict(organization_id=e.org.id,actor_id=e.target.id,**values)
    if 'entity_id' in row.c:data['entity_id']=str(e.target.id) if table=='foundation_audit_log' else e.target.id
    e.db.execute(row.insert().values(**data));e.db.commit()
    result=remove(e)
    assert result.status_code==409 and table in result.json()['details']['table_names']


def test_profile_event_targeting_another_user_is_not_personal(users):
    e=users
    e.db.add(TenantAuditEntry(organization_id=e.org.id,actor_id=e.target.id,action='user.updated',entity_type='user',entity_id=str(e.actor.id),details={'full_name':{'after':'Changed'}}))
    e.db.commit()
    assert remove(e).status_code==409


def test_administrator_actions_on_subject_are_not_subject_work(users):
    e=users
    e.db.add(TenantAuditEntry(organization_id=e.org.id,actor_id=e.actor.id,action='user.locked',entity_type='user',entity_id=str(e.target.id),details={}))
    records=[TenantSecurityEvent(organization_id=e.org.id,actor_id=e.target.id,event_type=kind,details={'performed_by':str(e.actor.id)})
             for kind in ('tenant.account_locked','tenant.account_unlocked')]
    records.append(TenantSecurityEvent(organization_id=e.org.id,actor_id=e.target.id,event_type='tenant.sessions_ended',details={'reason':'ended_by_admin','by':e.actor.full_name}))
    e.db.add_all(records);e.db.commit();ids=[row.id for row in records]
    assert remove(e).status_code==200
    e.db.expire_all()
    assert all(row.actor_id is None for row in e.db.scalars(select(TenantSecurityEvent).where(TenantSecurityEvent.id.in_(ids))))


def test_performed_by_is_history_even_when_actor_column_is_the_subject(users):
    e=users
    e.db.add(TenantSecurityEvent(organization_id=e.org.id,actor_id=e.actor.id,event_type='tenant.account_locked',details={'performed_by':str(e.target.id)}))
    e.db.commit()
    assert remove(e).status_code==409


@pytest.mark.parametrize('kind',['tenant.mfa_enabled','tenant.unknown_future_event'])
def test_polymorphic_core_security_is_detached_only_for_allowlisted_self_event(users,kind):
    e=users;table=Base.metadata.tables['core_auth_security_events']
    identifier=e.db.execute(table.insert().values(event_type=kind,account_type='tenant',actor_type='tenant',account_id=e.target.id,
        organization_id=e.org.id,target_type='user',target_id=str(e.target.id),metadata={'user_id':str(e.target.id)})).inserted_primary_key[0]
    e.db.commit();result=remove(e)
    if kind=='tenant.mfa_enabled':
        assert result.status_code==200,result.text
        row=e.db.execute(select(table).where(table.c.id==identifier)).one()
        assert row.account_id is None and row.actor_email_snapshot and row.actor_name_snapshot
    else:assert result.status_code==409 and 'core_auth_security_events' in result.json()['details']['table_names']


@pytest.mark.parametrize('account_type,actor_type,blocked',[(None,'tenant',True),('future','system',True),('platform','tenant',True),('platform','platform',False)])
def test_polymorphic_unknown_scope_fails_closed_without_touching_platform_accounts(users,account_type,actor_type,blocked):
    e=users;table=Base.metadata.tables['core_auth_security_events'];target=e.target.id
    identifier=e.db.execute(table.insert().values(event_type='tenant.mfa_enabled',account_type=account_type,actor_type=actor_type,
        account_id=target,organization_id=e.org.id)).inserted_primary_key[0]
    e.db.commit();result=remove(e)
    assert result.status_code==(409 if blocked else 200),result.text
    assert e.db.scalar(select(table.c.account_id).where(table.c.id==identifier))==target


def business_record(e,kind):
    from app.commercial.infrastructure.models import Customer, Quote
    from app.workforce.infrastructure.models import WorkforceMember
    from app.workforce.domain.enums import WorkerType, EmploymentType
    if kind=='workforce_members':
        row=WorkforceMember(organization_id=e.org.id,employee_code='LINKED',full_name='Linked worker',
            worker_type=WorkerType.HELPER,employment_type=EmploymentType.EMPLOYEE,user_id=e.target.id)
    else:
        customer=Customer(organization_id=e.org.id,customer_code='BUSINESS',name='Business',
            created_by_user_id=e.target.id if kind=='commercial_customers' else e.actor.id)
        e.db.add(customer);e.db.flush()
        row=customer if kind=='commercial_customers' else Quote(organization_id=e.org.id,customer_id=customer.id,
            quote_number='BUSINESS',issue_date=utc_now(),valid_until=utc_now(),currency='SAR',
            subtotal_amount=0,discount_amount=0,tax_amount=0,total_amount=0,created_by_user_id=e.target.id)
    e.db.add(row);e.db.commit()
    return row


@pytest.mark.parametrize('kind',['commercial_customers','commercial_quotes','workforce_members'])
def test_business_provenance_and_workforce_link_block_with_table_name(users,kind):
    e=users;business_record(e,kind)
    response=remove(e)
    assert response.status_code==409 and response.json()['code']=='USER_DELETE_HAS_HISTORY'
    assert kind in response.json()['details']['table_names']


def test_existing_access_and_all_rotated_refresh_sessions_stop_after_deletion(users):
    from app.main import app
    from app.dependencies import get_current_user
    from app.core.security import issue_token_pair,rotate_refresh_token
    from app.core.config import settings
    e=users;e.target.password_hash=hash_password('DeleteFlow123!');e.db.commit()
    pair=issue_token_pair(e.db,account_id=e.target.id,account_type='tenant',organization_id=e.org.id,token_version=e.target.token_version)
    _,current=rotate_refresh_token(e.db,pair.refresh_token,'tenant')
    table=Base.metadata.tables['core_auth_sessions'];identifier=e.target.id
    assert len(e.db.execute(select(table.c.id).where(table.c.account_id==identifier)).all())>=2
    assert remove(e).status_code==200
    assert e.db.scalar(select(table.c.id).where(table.c.account_id==identifier)) is None
    admin=app.dependency_overrides.pop(get_current_user)
    try:
        assert e.client.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+current.access_token}).status_code==401
        e.client.cookies.set(settings.refresh_cookie_name,current.refresh_token)
        assert e.client.post('/api/v1/auth/refresh').status_code==401
    finally:app.dependency_overrides[get_current_user]=admin
