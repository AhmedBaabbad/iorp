from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4
import pytest
from sqlalchemy import event,select
from sqlalchemy.exc import IntegrityError
from app.main import app
from app.dependencies import get_current_user
from app.core.tenancy import TenantContext
from app.core.security import unusable_password_hash,hash_password
from app.core.utils import utc_now
from app.foundation.infrastructure.models import User,TenantSecurityEvent,UserRole,Role
from app.foundation.application.presence import touch_presence,is_online
from app.foundation.application.permanent_deletion import delete_permanently,UserDeletionConflict
from app.core.db import Base

BASE='/api/v1/admin/users'


@pytest.fixture
def users(client,db,test_user,test_org):
    permissions={'foundation:users:read','foundation:users:write','foundation:users:delete','foundation:users:deactivate'}
    current=SimpleNamespace(user=test_user,auth_user=SimpleNamespace(permissions=permissions),
        tenant=TenantContext(test_user.id,test_org.id,permissions=frozenset(permissions)))
    app.dependency_overrides[get_current_user]=lambda:current
    target=User(organization_id=test_org.id,email='mistake@example.com',full_name='Created by mistake',
        password_hash=unusable_password_hash(),status='active')
    db.add(target);db.commit()
    yield SimpleNamespace(client=client,db=db,actor=test_user,org=test_org,target=target,current=current)
    app.dependency_overrides.pop(get_current_user,None)


def remove(e,identifier=None):
    return e.client.request('DELETE',f'{BASE}/{identifier or e.target.id}/permanent',json={'reason':'Created by mistake'})


def test_presence_throttle_does_not_touch_updated_at_or_versions(db,test_user):
    seen=[]
    def capture(conn,cursor,statement,*_):
        if statement.lstrip().upper().startswith('UPDATE FOUNDATION_USERS'):seen.append(statement)
    before=test_user.updated_at;version=test_user.token_version;now=utc_now()
    event.listen(db.bind,'before_cursor_execute',capture)
    try:
        assert touch_presence(db,test_user,now)
        assert not touch_presence(db,test_user,now+timedelta(seconds=59))
        assert len(seen)==1
        assert touch_presence(db,test_user,now+timedelta(seconds=60))
    finally:event.remove(db.bind,'before_cursor_execute',capture)
    db.refresh(test_user)
    assert test_user.updated_at==before and test_user.token_version==version
    assert is_online(test_user,now+timedelta(minutes=5))
    assert not is_online(test_user,now+timedelta(minutes=7))
    test_user.status='inactive'
    assert not is_online(test_user,now+timedelta(minutes=2))


def test_pending_deletion_cleans_only_owned_rows_and_audits_actor(users):
    e=users
    role=Role(organization_id=e.org.id,code='synthetic',name='Synthetic',description='',is_system=False,is_protected=False)
    e.db.add(role);e.db.flush();e.db.add(UserRole(user_id=e.target.id,role_id=role.id,assigned_by=e.actor.id));e.db.commit()
    token=Base.metadata.tables['foundation_password_reset_tokens']
    pending=Base.metadata.tables['foundation_user_email_changes']
    sessions=Base.metadata.tables['core_auth_sessions']
    e.db.execute(token.insert().values(user_id=e.target.id,organization_id=e.org.id,token_hash='unused-token',expires_at=utc_now()+timedelta(hours=1)))
    e.db.execute(pending.insert().values(user_id=e.target.id,organization_id=e.org.id,old_email=e.target.email,new_email='correction@example.com',old_hash='old',new_hash='new',expires_at=utc_now()+timedelta(hours=1),token_version=0))
    e.db.execute(sessions.insert().values(jti_hash='synthetic-session',family_id=uuid4(),account_type='tenant',account_id=e.target.id,organization_id=e.org.id,token_version=0,expires_at=utc_now()+timedelta(hours=1)))
    e.db.commit()
    # Being the subject in JSON is not actor history.
    e.db.add(TenantSecurityEvent(organization_id=e.org.id,event_type='user.created',actor_id=e.actor.id,details={'target_user_id':str(e.target.id)}));e.db.commit()
    identifier=e.target.id
    assert e.client.get(f'{BASE}/{identifier}').json()['can_delete_permanently']
    response=remove(e);assert response.status_code==200,response.text
    assert e.db.get(User,identifier) is None
    assert e.db.scalar(select(UserRole).where(UserRole.user_id==identifier)) is None
    for table,column in ((token,'user_id'),(pending,'user_id'),(sessions,'account_id')):
        assert e.db.scalar(select(table.c[column]).where(table.c[column]==identifier)) is None
    audit=e.db.scalar(select(TenantSecurityEvent).where(TenantSecurityEvent.event_type=='user.deleted_permanently'))
    assert audit.actor_id==e.actor.id and {key:audit.details[key] for key in ('email','full_name','reason')}=={'email':'mistake@example.com','full_name':'Created by mistake','reason':'Created by mistake'}
    assert audit.details['deleted_rows']==5 and audit.details['detached_rows']==0


@pytest.mark.parametrize('state,code',[('root','USER_DELETE_ROOT'),('self','USER_DELETE_SELF')])
def test_deletion_guards(users,state,code):
    e=users
    if state=='root':e.target.is_organization_root=True
    if state=='password':e.target.password_hash=hash_password('Password123!')
    if state=='login':e.target.last_login_at=utc_now()
    if state=='seen':e.target.last_seen_at=utc_now()
    e.db.commit()
    response=remove(e,e.actor.id if state=='self' else None)
    assert response.status_code==409 and response.json()['code']==code


def test_any_module_fk_and_security_actor_block_deletion(users):
    from app.commercial.infrastructure.models import Customer
    e=users
    row=Customer(organization_id=e.org.id,customer_code='C-HISTORY',name='Synthetic',created_by_user_id=e.target.id)
    e.db.add(row);e.db.commit()
    response=remove(e)
    assert response.status_code==409 and response.json()['code']=='USER_DELETE_HAS_HISTORY'
    assert 'customers' in response.json()['details']['tables']
    assert not e.client.get(f'{BASE}/{e.target.id}').json()['can_delete_permanently']
    assert e.db.get(Customer,row.id) is not None


def test_security_actor_blocks_without_deleting_history(users):
    e=users
    row=TenantSecurityEvent(organization_id=e.org.id,event_type='synthetic.actor',actor_id=e.target.id)
    e.db.add(row);e.db.commit()
    response=remove(e)
    assert response.status_code==409 and 'securityEvents' in response.json()['details']['tables']
    assert e.db.get(TenantSecurityEvent,row.id) is not None


def test_assigning_someone_elses_role_is_history_not_disposable_ownership(users):
    e=users
    role=Role(organization_id=e.org.id,code='another',name='Another',description='',is_system=False,is_protected=False)
    e.db.add(role);e.db.flush()
    assignment=UserRole(user_id=e.actor.id,role_id=role.id,assigned_by=e.target.id)
    e.db.add(assignment);e.db.commit()
    response=remove(e)
    assert response.status_code==409 and 'roleAssignments' in response.json()['details']['tables']
    assert e.db.get(UserRole,assignment.id) is not None


def test_other_tenant_and_missing_permission(users):
    from app.foundation.infrastructure.models import Organization
    e=users
    other_org=Organization(name='Foreign',code='FOREIGN',status='active',timezone='UTC',default_locale='en')
    e.db.add(other_org);e.db.flush()
    target=User(organization_id=other_org.id,email='foreign@example.com',full_name='Foreign',password_hash=unusable_password_hash(),status='active')
    e.db.add(target);e.db.commit()
    assert remove(e,target.id).status_code==404
    token=Base.metadata.tables['foundation_password_reset_tokens']
    e.db.execute(token.insert().values(user_id=e.target.id,organization_id=other_org.id,token_hash='foreign-malformed',expires_at=utc_now()+timedelta(hours=1)))
    e.db.commit()
    malformed=remove(e)
    assert malformed.status_code==409 and 'accountTokens' in malformed.json()['details']['tables']
    assert e.db.scalar(select(token.c.user_id).where(token.c.organization_id==other_org.id))==e.target.id
    e.current.auth_user.permissions.discard('foundation:users:delete')
    assert remove(e).status_code==403
    assert e.db.get(User,target.id) is not None


def test_presence_only_visible_to_user_readers(users):
    e=users
    detail=e.client.get(f'{BASE}/{e.target.id}').json()
    assert 'last_seen_at' in detail and detail['is_online'] is False
    e.current.auth_user.permissions.discard('foundation:users:read')
    e.current.auth_user.permissions.add('foundation:users:lock')
    response=e.client.post(f'{BASE}/{e.target.id}/lock',json={'reason':'Privacy test'})
    assert response.status_code==200,response.text
    assert 'last_seen_at' not in response.json() and 'is_online' not in response.json()
    assert e.client.get(BASE).status_code==403


def test_integrity_race_rolls_back_owned_rows_and_user(users,monkeypatch):
    e=users
    def fail(*_):raise IntegrityError('synthetic concurrent FK',{},Exception('reference'))
    event.listen(TenantSecurityEvent,'before_insert',fail)
    try:
        with pytest.raises(UserDeletionConflict,match='USER_DELETE_HAS_HISTORY'):
            delete_permanently(e.db,e.org.id,e.target.id,e.actor,'Synthetic race')
    finally:event.remove(TenantSecurityEvent,'before_insert',fail)
    assert e.db.get(User,e.target.id) is not None


def test_real_authentication_touches_once_and_login_sets_presence(client,db,test_user):
    login=client.post('/api/v1/auth/login',json={'email':test_user.email,'password':'Test1234!'})
    assert login.status_code==200,login.text
    db.refresh(test_user);assert test_user.last_seen_at is not None
    headers={'Authorization':'Bearer '+login.json()['access_token']}
    test_user.last_seen_at=None;db.commit()
    statements=[]
    def capture(conn,cursor,statement,*_):
        if statement.lstrip().upper().startswith('UPDATE FOUNDATION_USERS'):statements.append(statement)
    event.listen(db.bind,'before_cursor_execute',capture)
    try:
        for _ in range(2):
            response=client.get('/api/v1/auth/me',headers=headers)
            assert response.status_code==200,response.text
            assert 'last_seen_at' not in response.json() and 'is_online' not in response.json()
    finally:event.remove(db.bind,'before_cursor_execute',capture)
    assert len(statements)==1
    before=test_user.last_seen_at
    refreshed=client.post('/api/v1/auth/refresh')
    assert refreshed.status_code==200,refreshed.text
    db.refresh(test_user);assert test_user.last_seen_at==before
    from app.core.security import create_access_token
    test_user.last_seen_at=None;db.commit()
    platform_token=create_access_token(str(test_user.id),{'account_type':'platform','token_version':0})
    assert client.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+platform_token}).status_code==401
    db.refresh(test_user);assert test_user.last_seen_at is None
