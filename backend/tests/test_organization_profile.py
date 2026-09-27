from pathlib import Path

import pytest

from app.core.config import settings
from app.core.security import hash_password
from app.foundation.domain.enums import UserStatus
from app.foundation.infrastructure.models import Organization, User

PNG = b"\x89PNG\r\n\x1a\nlogo"
JPEG = b"\xff\xd8\xfflogo"
WEBP = b"RIFF\x04\x00\x00\x00WEBPlogo"


@pytest.fixture
def env(client, db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "bootstrap_token", "profile-token")
    monkeypatch.setattr(settings, "uploads_dir", str(tmp_path))
    response = client.post("/api/v1/system/bootstrap/initialize", json={
        "bootstrap_token": "profile-token",
        "platform_root": {"full_name": "Platform Root", "email": "platform-profile@example.com", "password": "PlatformRoot123!", "password_confirmation": "PlatformRoot123!"},
        "organization": {"name": "Profile Org", "code": "profile-org", "industry_type": "manufacturing", "timezone": "UTC", "default_locale": "en"},
        "organization_admin": {"full_name": "Profile Root", "email": "profile-root@example.com", "password": "ProfileRoot123!", "password_confirmation": "ProfileRoot123!"},
    })
    assert response.status_code == 201
    tenant = client.post("/api/v1/auth/login", json={"email": "profile-root@example.com", "password": "ProfileRoot123!"})
    platform = client.post("/api/v1/platform/login", json={"email": "platform-profile@example.com", "password": "PlatformRoot123!"})
    org = db.query(Organization).filter_by(code="PROFILE-ORG").one()
    return {"client": client, "db": db, "org": org, "tmp": tmp_path,
            "tenant": {"Authorization": f"Bearer {tenant.json()['access_token']}"},
            "platform": {"Authorization": f"Bearer {platform.json()['access_token']}"}}


def _profile(env): return env["client"].get("/api/v1/organization/profile", headers=env["tenant"])
def _patch(env, body, headers=None): return env["client"].patch("/api/v1/organization/profile", headers=headers or env["tenant"], json=body)
def _upload(env, content=PNG, name="logo.png", headers=None): return env["client"].post("/api/v1/organization/logo", headers=headers or env["tenant"], files={"file": (name, content)})


@pytest.mark.parametrize("case", ["T01", "T02", "T03", "T04"])
def test_profile_read(env, case):
    if case == "T04": assert env["client"].get("/api/v1/organization/profile").status_code == 401; return
    response = _profile(env); assert response.status_code == 200; body = response.json()
    if case == "T01": assert body["id"] == str(env["org"].id)
    if case == "T02": assert {"name","code","status","industry_type","timezone","default_locale","has_logo"} <= body.keys()
    if case == "T03": assert body["code"] == "PROFILE-ORG" and "other" not in body["name"].lower()


@pytest.mark.parametrize("case", ["T05","T06","T07","T08","T09","T10","T11","T12","T13","T14"])
def test_profile_update(env, case):
    if case == "T14":
        user=User(organization_id=env["org"].id,full_name="No Role",email="no-role@example.com",password_hash=hash_password("NoRole123!"),status=UserStatus.ACTIVE); env["db"].add(user); env["db"].commit()
        login=env["client"].post("/api/v1/auth/login",json={"email":"no-role@example.com","password":"NoRole123!"}); headers={"Authorization":f"Bearer {login.json()['access_token']}"}
        assert _patch(env,{"name":"Denied"},headers).status_code == 403; return
    bodies={"T05":{"industry_type":"advanced"},"T06":{"name":"Updated Org"},"T07":{"timezone":"Asia/Dubai"},"T08":{"timezone":"Not/AZone"},"T09":{"default_locale":"ar"},"T10":{"default_locale":"fr"},"T11":{"code":"CHANGED"},"T12":{"status":"archived","name":"Still Active"},"T13":{"organization_id":"00000000-0000-0000-0000-000000000000","name":"Scoped"}}
    response=_patch(env,bodies[case]); expected=400 if case in {"T08","T10","T11"} else 200; assert response.status_code==expected
    if case=="T06": assert response.json()["name"]=="Updated Org"
    if case=="T07": assert response.json()["timezone"]=="Asia/Dubai"
    if case=="T09": assert response.json()["default_locale"]=="ar"
    if case=="T11": assert response.json()["code"]=="ORG_CODE_IMMUTABLE"
    if case=="T12": assert response.json()["status"]=="active"
    if case=="T13": assert response.json()["id"]==str(env["org"].id)


@pytest.mark.parametrize("case", ["T15","T16","T17","T18","T19","T20","T21"])
def test_logo_upload(env, case):
    if case=="T21":
        user=User(organization_id=env["org"].id,full_name="No Brand",email="no-brand@example.com",password_hash=hash_password("NoBrand123!"),status=UserStatus.ACTIVE); env["db"].add(user); env["db"].commit(); login=env["client"].post("/api/v1/auth/login",json={"email":"no-brand@example.com","password":"NoBrand123!"})
        assert _upload(env,headers={"Authorization":f"Bearer {login.json()['access_token']}"}).status_code==403; return
    content,name={"T15":(PNG,"x.png"),"T16":(JPEG,"x.jpg"),"T17":(WEBP,"x.webp"),"T18":(b"\x89PNG\r\n\x1a\n"+b"x"*(2*1024*1024),"x.png"),"T19":(b"not-an-image","x.png"),"T20":(PNG,"../../escape.png")}[case]
    response=_upload(env,content,name); assert response.status_code==(400 if case in {"T18","T19"} else 200)
    if case=="T20": env["db"].refresh(env["org"]); assert Path(env["org"].logo_path).parts[:2]==("organizations",str(env["org"].id))


@pytest.mark.parametrize("case", ["T22","T23"])
def test_logo_replace(env, case):
    _upload(env,PNG); env["db"].refresh(env["org"]); old=env["org"].logo_path; assert (env["tmp"]/old).exists()
    assert _upload(env,JPEG,"new.jpg").status_code==200; env["db"].refresh(env["org"])
    if case=="T22": assert not (env["tmp"]/old).exists()
    if case=="T23": assert env["org"].logo_path!=old and env["org"].logo_path.endswith(".jpg")


@pytest.mark.parametrize("case", ["T24","T25","T26"])
def test_logo_remove(env, case):
    if case=="T25": assert env["client"].delete("/api/v1/organization/logo",headers=env["tenant"]).status_code in {200,404}; return
    _upload(env); env["db"].refresh(env["org"]); path=env["tmp"]/env["org"].logo_path
    headers=env["tenant"]
    if case=="T26":
        user=User(organization_id=env["org"].id,full_name="No Brand",email="remove-denied@example.com",password_hash=hash_password("NoBrand123!"),status=UserStatus.ACTIVE); env["db"].add(user); env["db"].commit(); login=env["client"].post("/api/v1/auth/login",json={"email":"remove-denied@example.com","password":"NoBrand123!"}); headers={"Authorization":f"Bearer {login.json()['access_token']}"}
    response=env["client"].delete("/api/v1/organization/logo",headers=headers); assert response.status_code==(403 if case=="T26" else 200)
    if case=="T24": env["db"].refresh(env["org"]); assert env["org"].logo_path is None and not path.exists()


@pytest.mark.parametrize("case", ["T27","T28","T29"])
def test_logo_serve(env, case):
    if case=="T28": assert env["client"].get("/api/v1/organization/logo",headers=env["tenant"]).status_code==404; return
    _upload(env,PNG); response=env["client"].get("/api/v1/organization/logo",headers=env["tenant"]); assert response.status_code==200 and response.headers["content-type"]=="image/png"
    if case=="T29": assert response.content==PNG and str(env["org"].id) in env["org"].logo_path


@pytest.mark.parametrize("case", ["T30","T31"])
def test_auth_me_organization(env, case):
    response=env["client"].get("/api/v1/auth/me",headers=env["tenant"]); assert response.status_code==200; organization=response.json()["organization"]
    if case=="T30": assert organization["name"]==env["org"].name and organization["has_logo"] is False
    if case=="T31": assert organization["id"]==str(env["org"].id) and organization["code"]==env["org"].code


@pytest.mark.parametrize("case", ["T32","T33","T34","T35","T36"])
def test_isolation_and_platform(env, case):
    if case in {"T32","T33"}: assert _patch(env,{"name":"Only Own"}).json()["id"]==str(env["org"].id); assert _profile(env).json()["name"]=="Only Own"; return
    if case=="T34": _upload(env); env["db"].refresh(env["org"]); assert str(env["org"].id) in env["org"].logo_path; return
    detail=env["client"].get(f"/api/v1/platform/organizations/{env['org'].id}",headers=env["platform"]); assert detail.status_code==200
    if case=="T35": assert {"name","industry_type","timezone","default_locale","has_logo","logo_url"}<=detail.json().keys()
    if case=="T36": _upload(env); response=env["client"].get(f"/api/v1/platform/organizations/{env['org'].id}/logo",headers=env["platform"]); assert response.status_code==200 and response.content==PNG
