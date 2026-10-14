from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.security import hash_password, verify_password
from app.core.token_utils import hash_token
from app.core.utils import utc_now
from app.foundation.application.password_reset import InvalidResetTokenError as TenantInvalidToken, TenantPasswordResetService
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, TenantPasswordResetToken, User
from app.platform.application.password_reset import InvalidResetTokenError as PlatformInvalidToken, PlatformPasswordResetService
from app.platform.domain.enums import PlatformAccountRole, PlatformAccountStatus
from app.platform.infrastructure.models import PlatformAccount, PlatformPasswordResetToken


class Mailbox:
    def __init__(self): self.messages = []
    def send_email(self, *args): self.messages.append(args); return True


@pytest.mark.parametrize('locale,expected,absent',[
    ('ar','شركة ريحانة الأفق للصناعة','Rehanah Al-Ofoq Industrial Company'),
    ('en','Rehanah Al-Ofoq Industrial Company','شركة ريحانة الأفق للصناعة'),
])
def test_email_company_name_matches_language(db,locale,expected,absent):
    from app.foundation.infrastructure.branding_models import OrganizationBranding
    org,user,_=_seed(db)
    db.add(OrganizationBranding(organization_id=org.id,legal_name_ar='شركة ريحانة الأفق للصناعة',
        legal_name_en='Rehanah Al-Ofoq Industrial Company'))
    db.commit()
    mailbox=Mailbox()
    TenantPasswordResetService(mailbox).request_reset(db,user.email,locale)
    _,subject,html,text=mailbox.messages[0]
    assert expected in subject and expected in html and expected in text
    assert absent not in subject and absent not in html and absent not in text
    if locale=='en':
        assert subject=='Password Reset — Rehanah Al-Ofoq Industrial Company — IORP'


def test_email_branding_missing_language_falls_back_without_other_tenant_name(db):
    from app.foundation.infrastructure.branding_models import OrganizationBranding
    org,user,_=_seed(db)
    other=Organization(name='Other tenant',code='RESET-OTHER')
    db.add(other);db.flush()
    db.add(OrganizationBranding(organization_id=other.id,legal_name_en='Other Private Company'))
    db.commit()
    mailbox=Mailbox()
    TenantPasswordResetService(mailbox).request_reset(db,user.email,'en')
    assert mailbox.messages[0][1]=='Password Reset — Reset Org — IORP'


def _seed(db):
    org = Organization(name="Reset Org", code="RESET", status=OrganizationStatus.ACTIVE, default_locale="en", timezone="UTC")
    db.add(org); db.flush()
    user = User(organization_id=org.id, full_name="Tenant User", email="tenant.reset@example.com", password_hash=hash_password("OldPassword1!"), status=UserStatus.ACTIVE)
    account = PlatformAccount(full_name="Platform User", email="platform.reset@example.com", password_hash=hash_password("OldPassword1!"), status=PlatformAccountStatus.ACTIVE, role=PlatformAccountRole.ADMIN)
    db.add_all([user, account]); db.commit()
    return org, user, account


def test_tenant_token_is_hashed_one_time_and_invalidates_sessions(db, monkeypatch):
    _, user, _ = _seed(db); mailbox = Mailbox(); raw = "tenant-raw-token-with-more-than-32-bytes"
    monkeypatch.setattr("app.foundation.application.password_reset.generate_reset_token", lambda: (raw, hash_token(raw)))
    service = TenantPasswordResetService(mailbox); service.request_reset(db, user.email)
    record = db.scalar(select(TenantPasswordResetToken))
    assert record.token_hash == hash_token(raw) and raw not in record.token_hash and len(mailbox.messages) == 1
    old_version = user.token_version; service.execute_reset(db, raw, "StrongReset123!")
    assert verify_password("StrongReset123!", user.password_hash) and user.token_version == old_version + 1 and record.used_at is not None
    with pytest.raises(TenantInvalidToken): service.execute_reset(db, raw, "AnotherStrong123!")


def test_new_request_invalidates_previous_and_platform_is_separate(db, monkeypatch):
    _, user, account = _seed(db); mailbox = Mailbox(); tokens = iter(["a" * 40, "b" * 40])
    monkeypatch.setattr("app.foundation.application.password_reset.generate_reset_token", lambda: ((raw := next(tokens)), hash_token(raw)))
    service = TenantPasswordResetService(mailbox); service.request_reset(db, user.email); service.request_reset(db, user.email)
    rows = list(db.scalars(select(TenantPasswordResetToken).order_by(TenantPasswordResetToken.created_at)))
    assert rows[0].used_at is not None and rows[1].used_at is None
    platform_raw = "p" * 40
    monkeypatch.setattr("app.platform.application.password_reset.generate_reset_token", lambda: (platform_raw, hash_token(platform_raw)))
    PlatformPasswordResetService(mailbox).request_reset(db, account.email)
    assert db.scalar(select(PlatformPasswordResetToken)).account_id == account.id
    with pytest.raises(PlatformInvalidToken): PlatformPasswordResetService(mailbox).execute_reset(db, "b" * 40, "StrongReset123!")


def test_expired_and_unknown_email_api_behavior(client, db):
    _, user, _ = _seed(db)
    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "unknown@example.com"})
    known = client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    assert unknown.status_code == known.status_code == 200 and unknown.json() == known.json()
    expired_raw = "expired-token-value-that-is-long-enough"
    db.add(TenantPasswordResetToken(user_id=user.id, organization_id=user.organization_id, token_hash=hash_token(expired_raw), expires_at=utc_now() - timedelta(minutes=1))); db.commit()
    response = client.post("/api/v1/auth/reset-password", json={"token": expired_raw, "new_password": "StrongReset123!", "new_password_confirmation": "StrongReset123!"})
    assert response.status_code == 400 and response.json()["code"] == "RESET_TOKEN_EXPIRED"


@pytest.mark.parametrize('platform',[False,True])
def test_requested_locale_used_and_failed_delivery_invalidates_token(db,platform):
    _,user,account=_seed(db)
    mailbox=Mailbox()
    service=PlatformPasswordResetService(mailbox) if platform else TenantPasswordResetService(mailbox)
    email=account.email if platform else user.email
    service.request_reset(db,email,'en')
    assert 'Password Reset' in mailbox.messages[-1][1]
    mailbox.send_email=lambda *args:False
    service.request_reset(db,email,'ar')
    model=PlatformPasswordResetToken if platform else TenantPasswordResetToken
    assert all(r.used_at is not None for r in db.scalars(select(model)))


def test_suspended_organization_cannot_use_old_reset_link(db,monkeypatch):
    org,user,_=_seed(db)
    raw='suspended-organization-token-32-characters'
    monkeypatch.setattr('app.foundation.application.password_reset.generate_reset_token',lambda:(raw,hash_token(raw)))
    service=TenantPasswordResetService(Mailbox())
    service.request_reset(db,user.email)
    org.status=OrganizationStatus.SUSPENDED
    db.commit()
    with pytest.raises(TenantInvalidToken):service.execute_reset(db,raw,'StrongReset123!')
