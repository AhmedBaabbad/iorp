from datetime import timedelta
import pytest
import pyotp
from cryptography.fernet import Fernet
from app.core.config import settings
from app.core.security import decode_token
from app.platform.application import mfa
from app.platform.infrastructure.mfa_models import PlatformMFA, PlatformStepUp
from app.platform.infrastructure.models import PlatformAccount, PlatformActivityLog
from tests.test_platform_identity import _bootstrap, _headers


@pytest.fixture
def signed(client, db, monkeypatch):
    monkeypatch.setattr(settings, 'platform_mfa_keys', Fernet.generate_key().decode())
    monkeypatch.setattr(settings, 'platform_mfa_required', False)
    token = _bootstrap(client, monkeypatch)
    return token, db.query(PlatformAccount).filter_by(email='origin@example.com').one()


def enroll(client, token):
    response = client.post('/api/v1/platform/mfa/enroll', headers=_headers(token), json={'password':'OriginPlatform123!'})
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'no-store'
    return response.json()


def confirm(client, token, secret):
    return client.post('/api/v1/platform/mfa/confirm', headers=_headers(token), json={'code':pyotp.TOTP(secret).now(), 'saved_recovery_codes':True})


def login(client, code=''):
    return client.post('/api/v1/platform/login', json={'email':'origin@example.com', 'password':'OriginPlatform123!', 'mfa_code':code})


def test_enrollment_encrypted_replay_recovery_and_invalidation(client, db, signed):
    token, account = signed
    data = enroll(client, token)
    row = db.get(PlatformMFA, account.id)
    assert data['secret'] not in row.secret and not row.enabled
    assert data['recovery_codes'][0] not in row.recovery_hashes
    assert confirm(client, token, data['secret']).status_code == 200
    assert client.get('/api/v1/platform/me', headers=_headers(token)).status_code == 401
    assert login(client).status_code == 403
    assert login(client, pyotp.TOTP(data['secret']).now()).status_code == 400
    assert login(client, data['recovery_codes'][0]).status_code == 200
    assert login(client, data['recovery_codes'][0]).status_code == 400
    db.expire_all()
    assert len(db.get(PlatformMFA, account.id).recovery_hashes) == 9
    logs = str([r.details for r in db.query(PlatformActivityLog).all()])
    assert data['secret'] not in logs and data['recovery_codes'][0] not in logs


def test_invalid_enrollment_code_does_not_enable(client, db, signed):
    token, account = signed
    enroll(client, token)
    r=client.post('/api/v1/platform/mfa/confirm', headers=_headers(token), json={'code':'invalid', 'saved_recovery_codes':True})
    assert r.status_code == 400
    db.expire_all(); assert not db.get(PlatformMFA, account.id).enabled


def proof(client, token, method, path, body=None, code=''):
    r=client.post('/api/v1/platform/mfa/step-up', headers=_headers(token), json={'password':'OriginPlatform123!', 'code':code,'method':method,'path':path,'body':body})
    assert r.status_code == 200, r.text
    return {**_headers(token), 'X-Platform-Step-Up': r.json()['authorization']}


def test_step_up_binds_body_and_is_single_use(client, db, signed):
    token, account = signed
    path=f'/platform/administrators/{account.id}'
    body={'full_name':'Verified name'}
    assert client.patch('/api/v1'+path, headers=_headers(token), json=body).status_code == 403
    headers=proof(client, token, 'PATCH', path, body)
    assert client.patch('/api/v1'+path, headers=headers, json={'full_name':'Tampered'}).status_code == 403
    assert client.patch('/api/v1'+path, headers=headers, json=body).status_code == 200
    assert client.patch('/api/v1'+path, headers=headers, json=body).status_code == 403
    db.expire_all(); assert db.get(PlatformAccount, account.id).full_name == 'Verified name'


def test_expired_step_up_rejected(client, db, signed):
    token, account=signed
    path=f'/platform/administrators/{account.id}'; body={'full_name':'Expired'}
    headers=proof(client, token, 'PATCH', path, body)
    db.query(PlatformStepUp).one().expires_at = mfa.now()-timedelta(seconds=1);db.commit()
    assert client.patch('/api/v1'+path, headers=headers, json=body).status_code == 403
    assert db.get(PlatformAccount,account.id).full_name != 'Expired'


def test_rollout_gate_allows_only_enrollment(client, monkeypatch, signed):
    token, account=signed
    monkeypatch.setattr(settings,'platform_mfa_required',True)
    assert client.get('/api/v1/platform/me', headers=_headers(token)).json()['mfa_enrollment_required']
    assert client.get('/api/v1/platform/organizations',headers=_headers(token)).status_code == 403
    assert client.get('/api/v1/platform/mfa',headers=_headers(token)).status_code == 200
    enroll(client,token)


def test_operator_recovery_requires_confirmation_and_revokes(client, db, signed):
    from app.cli.recover_platform_mfa import recover
    token,account=signed; enroll(client,token)
    with pytest.raises(ValueError): recover(db,account.id,'wrong@example.test','Verified incident 123')
    assert db.get(PlatformMFA,account.id)
    recover(db,account.id,account.email,'Verified incident 123')
    assert db.get(PlatformMFA,account.id) is None
    assert client.get('/api/v1/platform/me',headers=_headers(token)).status_code == 401
    assert db.query(PlatformActivityLog).filter_by(action='platform_mfa_operator_recovery').count()==1


def test_unenrolled_login_compatible_and_headers(client,signed):
    assert login(client).status_code == 200
    r=client.get('/api/v1/platform/me',headers=_headers(signed[0]))
    assert r.status_code==200 and r.headers['x-content-type-options']=='nosniff'


def test_step_up_does_not_cross_sessions(client, db, signed):
    token, account = signed
    path=f'/platform/administrators/{account.id}'; body={'full_name':'Other session'}
    headers=proof(client,token,'PATCH',path,body)
    newer=login(client).json()['access_token']
    headers['Authorization']='Bearer '+newer
    assert client.patch('/api/v1'+path,headers=headers,json=body).status_code==403


def test_recovery_replacement_requires_factor_and_invalidates(client, db, signed):
    token, account = signed
    data=enroll(client,token); assert confirm(client,token,data['secret']).status_code==200
    token=login(client,data['recovery_codes'][0]).json()['access_token']
    assert client.post('/api/v1/platform/mfa/recovery',headers=_headers(token)).status_code==403
    headers=proof(client,token,'POST','/platform/mfa/recovery',code=data['recovery_codes'][1])
    result=client.post('/api/v1/platform/mfa/recovery',headers=headers)
    assert result.status_code==200 and len(result.json()['recovery_codes'])==10
    assert client.get('/api/v1/platform/me',headers=_headers(token)).status_code==401
    assert login(client,data['recovery_codes'][2]).status_code==400


def test_audit_failure_rolls_back_enrollment_confirmation(client, db, signed, monkeypatch):
    from app.core.audit import PlatformAuditService
    token,account=signed; data=enroll(client,token)
    def broken(self, **kw): raise RuntimeError('test audit failure')
    monkeypatch.setattr(PlatformAuditService,'record',broken)
    with pytest.raises(RuntimeError): confirm(client,token,data['secret'])
    db.rollback();db.expire_all()
    assert not db.get(PlatformMFA,account.id).enabled
    assert db.get(PlatformAccount,account.id).token_version==0


def test_verification_failures_are_bounded(client, db, signed):
    token,account=signed;enroll(client,token)
    for _ in range(5):
        assert client.post('/api/v1/platform/mfa/confirm',headers=_headers(token),json={'code':'invalid','saved_recovery_codes':True}).status_code==400
    assert client.post('/api/v1/platform/mfa/confirm',headers=_headers(token),json={'code':'invalid','saved_recovery_codes':True}).status_code==429


def test_missing_encryption_key_fails_closed(client, db, signed, monkeypatch):
    monkeypatch.setattr(settings,'platform_mfa_keys','')
    r=client.post('/api/v1/platform/mfa/enroll',headers=_headers(signed[0]),json={'password':'OriginPlatform123!'})
    assert r.status_code==503
    assert db.get(PlatformMFA,signed[1].id) is None


def test_validation_never_echoes_sensitive_input(client,signed):
    secret='private'*40
    r=client.post('/api/v1/platform/mfa/enroll',headers=_headers(signed[0]),json={'password':secret})
    assert r.status_code==422 and secret not in r.text


def test_unverified_session_cannot_bypass_enabled_factor_even_with_current_version(client,db,signed):
    from app.core.security import issue_token_pair
    token,account=signed; data=enroll(client,token);assert confirm(client,token,data['secret']).status_code==200
    unverified=issue_token_pair(db,account_id=account.id,account_type='platform',token_version=account.token_version)
    assert client.get('/api/v1/platform/me',headers=_headers(unverified.access_token)).status_code==401
    client.cookies.clear();client.cookies.set('iorp_refresh',unverified.refresh_token,path='/api/v1/platform')
    assert client.post('/api/v1/platform/refresh').status_code==401
    token=login(client,data['recovery_codes'][0]).json()['access_token']
    refreshed=client.post('/api/v1/platform/refresh')
    assert refreshed.status_code==200
    assert client.get('/api/v1/platform/me',headers=_headers(refreshed.json()['access_token'])).status_code==200


@pytest.mark.parametrize('path,method,body', [('', 'GET', None),('/enroll','POST',{'password':'test'}),
    ('/confirm','POST',{'code':'123456','saved_recovery_codes':True}),('/step-up','POST',{'password':'test','method':'POST','path':'/platform/mfa/disable'}),
    ('/disable','POST',None),('/recovery','POST',None)])
def test_mfa_endpoints_reject_anonymous_and_tenant_accounts(client,test_user,path,method,body):
    endpoint='/api/v1/platform/mfa'+path
    assert client.request(method,endpoint,json=body).status_code==401
    tenant=client.post('/api/v1/auth/login',json={'email':'test@example.com','password':'Test1234!'}).json()['access_token']
    assert client.request(method,endpoint,json=body,headers=_headers(tenant)).status_code==401
