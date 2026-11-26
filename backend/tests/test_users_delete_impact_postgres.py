"""Activated PostgreSQL accounts without work can be deleted; personal audit remains detached."""
import os
from types import SimpleNamespace
from uuid import uuid4
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from app.main import app
from app.core.db import Base,engine
from app.core.security import unusable_password_hash,hash_password
from app.core.tenancy import TenantContext
from app.dependencies import get_db,get_current_user
from app.foundation.infrastructure.models import Organization,User,TenantSecurityEvent
from app.foundation.domain.enums import OrganizationStatus,UserStatus
from app.foundation.application.services import FoundationService
from app.core.utils import utc_now

pytestmark=pytest.mark.skipif(os.environ.get('RUN_POSTGRES_TESTS')!='1',reason='Isolated PostgreSQL opt-in')


def test_activated_account_deleted_and_personal_history_detached(mailbox):
    schema='test_user_impact_'+uuid4().hex
    with engine.begin() as c:c.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    original=dict(app.dependency_overrides)
    client=None
    try:
        Base.metadata.create_all(isolated)
        with Session(isolated,expire_on_commit=False) as db:
            org=Organization(name='Synthetic',code='IMPACT',status=OrganizationStatus.ACTIVE,timezone='UTC',default_locale='en')
            db.add(org);db.flush()
            actor=User(organization_id=org.id,email='admin@example.com',full_name='Admin',password_hash=hash_password('AdminTest123!'),status=UserStatus.ACTIVE,is_organization_root=True)
            target=User(organization_id=org.id,email='signed@example.com',full_name='Signed user',password_hash=unusable_password_hash(),status=UserStatus.ACTIVE)
            db.add_all([actor,target]);db.commit()
            def database():yield db
            app.dependency_overrides[get_db]=database
            client=TestClient(app)
            assert FoundationService(db).send_activation_link(target)
            password='PresenceFlow123!'
            response=client.post('/api/v1/auth/reset-password',json={'token':mailbox[target.email],
                'new_password':password,'new_password_confirmation':password})
            assert response.status_code==200,response.text
            login=client.post('/api/v1/auth/login',json={'email':target.email,'password':password})
            assert login.status_code==200,login.text
            headers={'Authorization':'Bearer '+login.json()['access_token']}
            for path in ('/api/v1/auth/me','/api/v1/auth/me/profile','/api/v1/auth/sessions'):
                response=client.get(path,headers=headers);assert response.status_code==200,response.text
            assert client.patch('/api/v1/auth/me',json={'full_name':'Signed person','preferred_locale':'ar'},headers=headers).status_code==200
            new_password='PresenceChanged123!'
            response=client.post('/api/v1/auth/change-password',headers=headers,json={'current_password':password,'new_password':new_password,'new_password_confirmation':new_password})
            assert response.status_code==200,response.text
            login=client.post('/api/v1/auth/login',json={'email':target.email,'password':new_password})
            assert login.status_code==200,login.text
            headers={'Authorization':'Bearer '+login.json()['access_token']}
            # Tenant MFA has no endpoint/model yet: exercise the explicit personal
            # event contract without inventing a second authentication system.
            db.add(TenantSecurityEvent(organization_id=org.id,actor_id=target.id,event_type='tenant.mfa_enabled',details={'user_id':str(target.id)}))
            notifications=Base.metadata.tables['notifications_items']
            db.execute(notifications.insert().values(organization_id=org.id,recipient_user_id=target.id,
                event='synthetic.notice',category='access',severity='info',params={}))
            db.commit()
            permissions=frozenset({'foundation:users:read','foundation:users:delete'})
            current=SimpleNamespace(user=actor,auth_user=SimpleNamespace(permissions=permissions),tenant=TenantContext(actor.id,org.id,permissions=permissions))
            app.dependency_overrides[get_current_user]=lambda:current
            target_id=target.id
            before={row.id:(row.actor_id,row.actor_email) for row in db.scalars(sa.select(TenantSecurityEvent).where(TenantSecurityEvent.actor_id==target_id))}
            response=client.request('DELETE',f'/api/v1/admin/users/{target_id}/permanent',json={'reason':'No business history'})
            assert response.status_code==200,response.text
            assert db.scalar(sa.select(User.id).where(User.id==target_id)) is None
            assert db.scalar(sa.select(notifications.c.id).where(notifications.c.recipient_user_id==target_id)) is None
            db.expire_all()
            events=list(db.scalars(sa.select(TenantSecurityEvent).where(TenantSecurityEvent.id.in_(before))))
            assert len(events)==len(before)>=3 and all(row.actor_id is None and row.actor_email for row in events)
            audit=db.scalar(sa.select(TenantSecurityEvent).where(TenantSecurityEvent.event_type=='user.deleted_permanently'))
            assert audit is not None and audit.details["detached_rows"]>=3
            sessions=Base.metadata.tables['core_auth_sessions']
            assert db.scalar(sa.select(sessions.c.id).where(sessions.c.account_type=='tenant',sessions.c.account_id==target_id)) is None
            app.dependency_overrides.pop(get_current_user)
            assert client.get('/api/v1/auth/me',headers=headers).status_code==401
            assert client.post('/api/v1/auth/refresh').status_code==401
    finally:
        if client:client.close()
        app.dependency_overrides.clear();app.dependency_overrides.update(original)
        isolated.dispose()
        with engine.begin() as c:c.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))


@pytest.fixture
def unused_pg_user():
    schema='test_delete_rules_'+uuid4().hex
    with engine.begin() as c:c.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    original=dict(app.dependency_overrides)
    try:
        Base.metadata.create_all(isolated)
        with Session(isolated,expire_on_commit=False) as db:
            org=Organization(name='Synthetic',code='RULES',status=OrganizationStatus.ACTIVE,timezone='UTC',default_locale='en')
            db.add(org);db.flush()
            actor=User(organization_id=org.id,email='admin-rules@example.com',full_name='Admin',password_hash='!',status=UserStatus.ACTIVE)
            target=User(organization_id=org.id,email='active-rules@example.com',full_name='Activated',password_hash=hash_password('DeleteRules123!'),status=UserStatus.ACTIVE,last_login_at=utc_now(),last_seen_at=utc_now())
            db.add_all([actor,target]);db.commit()
            def database():yield db
            permissions=frozenset({'foundation:users:read','foundation:users:delete'})
            current=SimpleNamespace(user=actor,auth_user=SimpleNamespace(permissions=permissions),tenant=TenantContext(actor.id,org.id,permissions=permissions))
            app.dependency_overrides[get_db]=database
            app.dependency_overrides[get_current_user]=lambda:current
            with TestClient(app) as client:yield SimpleNamespace(db=db,client=client,org=org,actor=actor,target=target)
    finally:
        app.dependency_overrides.clear();app.dependency_overrides.update(original)
        isolated.dispose()
        with engine.begin() as c:c.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))


@pytest.mark.parametrize('kind',['commercial_customers','commercial_quotes','workforce_members','removed_by','unknown','root','self'])
def test_postgres_business_and_unknown_history_fail_closed(unused_pg_user,kind):
    from tests.foundation.test_permanent_delete_rules import business_record
    from app.foundation.infrastructure.models import RoleAssignmentRemoval
    e=unused_pg_user;identifier=e.target.id
    if kind in ('commercial_customers','commercial_quotes','workforce_members'):business_record(e,kind)
    elif kind=='removed_by':e.db.add(RoleAssignmentRemoval(user_id=e.actor.id,role_id=uuid4(),removed_by=e.target.id))
    elif kind=='unknown':e.db.add(TenantSecurityEvent(organization_id=e.org.id,actor_id=e.target.id,event_type='tenant.unknown_future_event'))
    elif kind=='root':e.target.is_organization_root=True
    elif kind=='self':identifier=e.actor.id
    e.db.commit()
    result=e.client.request('DELETE',f'/api/v1/admin/users/{identifier}/permanent',json={'reason':'Verify closed rules'})
    assert result.status_code==409,result.text
    expected='USER_DELETE_ROOT' if kind=='root' else 'USER_DELETE_SELF' if kind=='self' else 'USER_DELETE_HAS_HISTORY'
    assert result.json()['code']==expected
    if kind in ('commercial_customers','commercial_quotes','workforce_members'):
        assert kind in result.json()['details']['table_names']


def test_postgres_removal_subject_is_preserved_without_blocking(unused_pg_user):
    from app.foundation.infrastructure.models import RoleAssignmentRemoval
    e=unused_pg_user
    removal=RoleAssignmentRemoval(user_id=e.target.id,role_id=uuid4(),removed_by=e.actor.id)
    e.db.add(removal);e.db.commit();identifier=e.target.id;removal_id=removal.id
    response=e.client.request('DELETE',f'/api/v1/admin/users/{identifier}/permanent',json={'reason':'No work history'})
    assert response.status_code==200,response.text
    e.db.expire_all()
    assert e.db.get(RoleAssignmentRemoval,removal_id).user_id==identifier
