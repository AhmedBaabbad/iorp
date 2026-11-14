"""Actual PostgreSQL FK deletion after real activation/login/browsing/logout."""
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

pytestmark=pytest.mark.skipif(os.environ.get('RUN_POSTGRES_TESTS')!='1',reason='Isolated PostgreSQL opt-in')


def test_real_fk_delete_of_account_only_history(mailbox):
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
            assert client.post('/api/v1/auth/logout').status_code==204
            notifications=Base.metadata.tables['notifications_items']
            db.execute(notifications.insert().values(organization_id=org.id,recipient_user_id=target.id,
                event='synthetic.notice',category='access',severity='info',params={}))
            db.commit()
            permissions=frozenset({'foundation:users:read','foundation:users:delete'})
            current=SimpleNamespace(user=actor,auth_user=SimpleNamespace(permissions=permissions),tenant=TenantContext(actor.id,org.id,permissions=permissions))
            app.dependency_overrides[get_current_user]=lambda:current
            response=client.request('DELETE',f'/api/v1/admin/users/{target.id}/permanent',json={'reason':'No business history'})
            assert response.status_code==200,response.text
            assert db.scalar(sa.select(User.id).where(User.id==target.id)) is None
            assert db.scalar(sa.select(notifications.c.id).where(notifications.c.recipient_user_id==target.id)) is None
            events=list(db.scalars(sa.select(TenantSecurityEvent).where(TenantSecurityEvent.actor_email==target.email)))
            assert len(events)>=3 and all(row.actor_id is None for row in events)
            audit=db.scalar(sa.select(TenantSecurityEvent).where(TenantSecurityEvent.event_type=='user.deleted_permanently'))
            assert audit.actor_id==actor.id and audit.details['detached_rows']>=3 and audit.details['deleted_rows']>=3
    finally:
        if client:client.close()
        app.dependency_overrides.clear();app.dependency_overrides.update(original)
        isolated.dispose()
        with engine.begin() as c:c.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
