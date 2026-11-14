from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select
from app.main import app
from app.dependencies import get_current_user
from app.core.db import Base
from app.core.security import hash_password
from app.core.tenancy import TenantContext
from app.core.utils import utc_now
from app.foundation.infrastructure.models import User,TenantSecurityEvent
from app.foundation.application.services import FoundationService
from tests.foundation.test_users_ux import users,remove,BASE  # noqa: F401


def signed_in_and_browsed(e,activate):
    password='PresenceFlow123!'
    assert FoundationService(e.db).send_activation_link(e.target)
    activate(e.target.email,password)
    override=app.dependency_overrides.pop(get_current_user)
    try:
        response=e.client.post('/api/v1/auth/login',json={'email':e.target.email,'password':password})
        assert response.status_code==200,response.text
        headers={'Authorization':'Bearer '+response.json()['access_token']}
        for path in ('/api/v1/auth/me','/api/v1/auth/me/profile','/api/v1/auth/sessions'):
            response=e.client.get(path,headers=headers)
            assert response.status_code==200,response.text
        assert e.client.post('/api/v1/auth/logout').status_code==204
    finally:app.dependency_overrides[get_current_user]=override
    table=Base.metadata.tables['notifications_items']
    e.db.execute(table.insert().values(organization_id=e.org.id,recipient_user_id=e.target.id,
        event='synthetic.notice',category='access',severity='info',params={}))
    e.db.commit()


def test_activated_browsing_logged_out_user_with_notifications_can_be_deleted(users,activate):
    e=users;signed_in_and_browsed(e,activate)
    identifier=e.target.id;email=e.target.email
    response=e.client.get(f'{BASE}/{identifier}')
    assert response.json()['delete_block'] is None and response.json()['can_delete_permanently']
    assert 'delete_block' not in e.client.get(BASE).json()[0]
    result=remove(e);assert result.status_code==200,result.text
    e.db.expire_all();assert e.db.get(User,identifier) is None
    events=list(e.db.scalars(select(TenantSecurityEvent).where(TenantSecurityEvent.event_type.in_(
        ['tenant.login_success','tenant.password_reset_via_email','tenant.session_revoked']))))
    assert {'tenant.login_success','tenant.password_reset_via_email','tenant.session_revoked'} <= {row.event_type for row in events}
    assert all(row.actor_id is None and row.actor_email==email for row in events)
    table=Base.metadata.tables['notifications_items']
    assert e.db.scalar(select(table.c.id).where(table.c.recipient_user_id==identifier)) is None
    audit=e.db.scalar(select(TenantSecurityEvent).where(TenantSecurityEvent.event_type=='user.deleted_permanently'))
    assert audit.details['detached_rows']>=3
    assert audit.details['deleted_by_table']['notifications_items']>=1


def test_same_activity_with_customer_creation_is_business_history(users,activate):
    from app.commercial.infrastructure.models import Customer
    e=users;signed_in_and_browsed(e,activate)
    row=Customer(organization_id=e.org.id,customer_code='IMPACT',name='Work',created_by_user_id=e.target.id)
    e.db.add(row);e.db.commit()
    response=remove(e)
    assert response.status_code==409 and response.json()['code']=='USER_DELETE_HAS_HISTORY'
    assert 'customers' in response.json()['details']['tables']
    assert e.client.get(f'{BASE}/{e.target.id}').json()['delete_block']=={'code':'USER_DELETE_HAS_HISTORY','tables':['customers']}


@pytest.mark.parametrize('status',['active','inactive','locked'])
def test_activation_and_account_status_alone_never_block(users,status):
    e=users;e.target.status=status;e.target.password_hash=hash_password('AlreadyUsed123!')
    e.target.last_login_at=utc_now()-timedelta(days=10);e.target.last_seen_at=utc_now();e.db.commit()
    assert remove(e).status_code==200


def test_administrative_lock_of_other_user_stays_blocking(users):
    e=users
    victim=User(organization_id=e.org.id,email='victim@example.com',full_name='Victim',password_hash='!',status='active')
    e.db.add(victim);e.db.commit()
    operator=e.current.user
    e.current.auth_user.permissions.add('foundation:users:lock')
    e.current.user=e.target;e.current.tenant=TenantContext(e.target.id,e.org.id,permissions=frozenset(e.current.auth_user.permissions))
    response=e.client.post(f'{BASE}/{victim.id}/lock',json={'reason':'Admin lock'})
    assert response.status_code==200,response.text
    e.current.user=operator;e.current.tenant=TenantContext(operator.id,e.org.id,permissions=frozenset(e.current.auth_user.permissions))
    response=remove(e)
    assert response.status_code==409 and 'auditLog' in response.json()['details']['tables']


def test_familiar_security_event_targeting_somebody_else_is_not_detached(users):
    e=users
    row=TenantSecurityEvent(organization_id=e.org.id,event_type='tenant.login_success',actor_id=e.target.id,
        actor_email=e.target.email,details={'target_user_id':str(uuid4())})
    e.db.add(row);e.db.commit()
    assert remove(e).status_code==409
    e.db.refresh(row);assert row.actor_id==e.target.id


def test_delete_block_permission_and_fast_guards(users,monkeypatch):
    e=users
    e.current.auth_user.permissions.discard('foundation:users:delete')
    assert 'delete_block' not in e.client.get(f'{BASE}/{e.target.id}').json()
    e.current.auth_user.permissions.add('foundation:users:delete')
    def unexpected(*_):raise AssertionError('History query must not run for root/self')
    monkeypatch.setattr('app.foundation.application.permanent_deletion.reference_tables',unexpected)
    from app.foundation.application.permanent_deletion import deletion_block
    assert deletion_block(e.db,e.actor,e.actor.id)['code']=='USER_DELETE_SELF'
    e.target.is_organization_root=True
    assert deletion_block(e.db,e.target,e.actor.id)['code']=='USER_DELETE_ROOT'


def test_all_current_reference_types_have_arabic_and_english_labels():
    import json
    from pathlib import Path
    from app.foundation.infrastructure.permanent_deletion import TABLE_KEYS,EXTRA_HISTORY
    referenced={table.name for table in Base.metadata.tables.values()
        if any(fk.target_fullname=='foundation_users.id' for fk in table.foreign_keys)}|set(EXTRA_HISTORY)
    assert referenced<=TABLE_KEYS.keys()
    root=Path(__file__).resolve().parents[3]
    for locale in ('ar','en'):
        data=json.loads((root/f'frontend/src/i18n/locales/{locale}/administration.json').read_text(encoding='utf-8'))
        assert set(TABLE_KEYS.values())<=data['users']['permanentDelete']['tableTypes'].keys()


def test_failed_audit_rolls_back_detachment_and_owned_deletion(users):
    from sqlalchemy import event
    from sqlalchemy.exc import IntegrityError
    e=users
    row=TenantSecurityEvent(organization_id=e.org.id,event_type='tenant.login_success',actor_id=e.target.id)
    e.db.add(row);e.db.commit()
    table=Base.metadata.tables['notifications_items']
    notice=e.db.execute(table.insert().values(organization_id=e.org.id,recipient_user_id=e.target.id,
        event='synthetic.notice',category='access',severity='info',params={})).inserted_primary_key[0]
    e.db.commit()
    def fail(mapper,connection,record):
        if record.event_type=='user.deleted_permanently':raise IntegrityError('synthetic',{},Exception('audit failed'))
    event.listen(TenantSecurityEvent,'before_insert',fail)
    try:
        response=remove(e)
        assert response.status_code==409 and response.json()['code']=='USER_DELETE_HAS_HISTORY'
    finally:event.remove(TenantSecurityEvent,'before_insert',fail)
    e.db.refresh(row)
    assert row.actor_id==e.target.id and row.actor_email is None
    assert e.db.scalar(select(table.c.id).where(table.c.id==notice))==notice
