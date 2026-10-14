from tests.test_user_profile import profile_env, USER_PASSWORD
from app.foundation.infrastructure.models import User, UserEmailChange, TenantPasswordResetToken
from app.core.email.service import EmailService
from app.core.utils import utc_now
from datetime import timedelta
import re
import pytest

@pytest.mark.parametrize("field,value", [("full_name","Someone"),("email","new@example.com"),("phone","123"),("preferred_locale","ar")])
def test_administrator_cannot_change_personal_data(profile_env, field, value):
    e=profile_env
    user=e["db"].get(User,e["user_id"])
    before=getattr(user,field)
    response=e["client"].patch(f"/api/v1/admin/users/{user.id}",headers=e["root_headers"],json={field:value})
    assert response.status_code == 400
    e["db"].refresh(user)
    assert getattr(user,field)==before

def test_timezone_validated_and_owned(profile_env):
    e=profile_env
    assert e["client"].patch("/api/v1/auth/me",headers=e["user_headers"],json={"timezone":"Mars/Unknown"}).status_code==400
    r=e["client"].patch("/api/v1/auth/me",headers=e["user_headers"],json={"timezone":"Asia/Riyadh"})
    assert r.status_code==200 and r.json()["timezone"]=="Asia/Riyadh"
    assert e["client"].get("/api/v1/auth/me",headers=e["user_headers"]).json()["timezone"]=="Asia/Riyadh"

def test_reason_required_and_archive_preserves_identity(profile_env):
    e=profile_env; c=e["client"]; h=e["root_headers"]; path=f"/api/v1/admin/users/{e['user_id']}"
    assert c.post(path+"/lock",headers=h).status_code==422
    assert c.post(path+"/archive",headers=h,json={"reason":"Leaving work"}).status_code==409
    assert c.request("DELETE",path,headers=h,json={"reason":"Leaving work"}).status_code==200
    r=c.post(path+"/archive",headers=h,json={"reason":"Employment ended"})
    assert r.status_code==200 and r.json()["archived_at"]
    assert e["db"].get(User,e["user_id"]) is not None
    assert c.post(path+"/activate",headers=h,json={"reason":"Return to work"}).status_code==400
    r=c.post(path+"/restore",headers=h,json={"reason":"Return to work"})
    assert r.status_code==200 and r.json()["status"]=="inactive" and r.json()["archived_at"] is None
    assert c.post(path+"/activate",headers=h,json={"reason":"Approved return"}).status_code==200

def request_email(e, monkeypatch):
    sent=[]
    monkeypatch.setattr(EmailService,"send_email",lambda self,address,subject,html,text=None: sent.append((address,text)) or True)
    r=e["client"].post("/api/v1/auth/me/email-change",headers=e["user_headers"],json={"email":"changed@example.com","current_password":USER_PASSWORD})
    assert r.status_code==200
    assert len(sent)==2
    return [re.search(r"[a-f0-9]{32}$", text).group() for address,text in sent]

def test_email_dual_verification_revokes_session_and_tokens(profile_env,monkeypatch):
    e=profile_env; old,new=request_email(e,monkeypatch)
    user=e["db"].get(User,e["user_id"])
    assert user.email=="profile-user@example.com"
    r=e["client"].post("/api/v1/auth/me/email-change/confirm",headers=e["user_headers"],json={"old_code":"0"*32,"new_code":new})
    assert r.status_code==400
    r=e["client"].post("/api/v1/auth/me/email-change/confirm",headers=e["user_headers"],json={"old_code":old,"new_code":new})
    assert r.status_code==200
    e["db"].refresh(user)
    assert user.email=="changed@example.com"
    assert e["db"].get(UserEmailChange,user.id) is None
    assert e["client"].get("/api/v1/auth/me",headers=e["user_headers"]).status_code==401
    assert e["db"].query(TenantPasswordResetToken).filter_by(user_id=user.id,used_at=None).count()==0

def test_expired_email_request_rejected(profile_env,monkeypatch):
    e=profile_env; old,new=request_email(e,monkeypatch)
    row=e["db"].get(UserEmailChange,e["user_id"]);row.expires_at=utc_now()-timedelta(seconds=1);e["db"].commit()
    assert e["client"].post("/api/v1/auth/me/email-change/confirm",headers=e["user_headers"],json={"old_code":old,"new_code":new}).status_code==400

def test_email_bad_password_and_failed_delivery_leave_identity_unchanged(profile_env,monkeypatch):
    e=profile_env; path="/api/v1/auth/me/email-change"
    assert e["client"].post(path,headers=e["user_headers"],json={"email":"changed@example.com","current_password":"wrong"}).status_code==400
    monkeypatch.setattr(EmailService,"send_email",lambda *a,**k:False)
    assert e["client"].post(path,headers=e["user_headers"],json={"email":"changed@example.com","current_password":USER_PASSWORD}).status_code==400
    e["db"].expire_all()
    assert e["db"].get(UserEmailChange,e["user_id"]) is None
    assert e["db"].get(User,e["user_id"]).email=="profile-user@example.com"


def test_email_request_errors_identify_cause(profile_env):
    e=profile_env
    endpoint="/api/v1/auth/me/email-change"
    r=e["client"].post(endpoint,headers=e["user_headers"],json={"email":"new@example.com","current_password":"wrong"})
    assert r.status_code==400 and r.json()["code"]=="CURRENT_PASSWORD_INCORRECT"
    r=e["client"].post(endpoint,headers=e["user_headers"],json={"email":"profile-user@example.com","current_password":USER_PASSWORD})
    assert r.status_code==400 and r.json()["code"]=="EMAIL_UNCHANGED"
    r=e["client"].post(endpoint,headers=e["root_headers"],json={"email":"new@example.com","current_password":"unused"})
    assert r.status_code==400 and r.json()["code"]=="ROOT_IDENTITY_PROTECTED"
