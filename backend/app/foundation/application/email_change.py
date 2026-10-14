"""Owner-only email changes; both mailboxes prove possession before identity changes."""
import secrets
import hmac
from datetime import timedelta
from html import escape
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from app.core.email.service import EmailService
from app.core.security import verify_password, revoke_account_sessions
from app.core.token_utils import hash_token, is_token_expired
from app.core.utils import utc_now
from app.foundation.infrastructure.models import User, UserEmailChange, TenantPasswordResetToken
from app.foundation.application.audit import log_tenant_audit
from app.foundation.domain.enums import UserStatus


class EmailChangeError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def locked_user(db, current):
    user = db.scalar(select(User).where(User.id == current.id, User.organization_id == current.organization_id).with_for_update().execution_options(populate_existing=True))
    if user is None or user.status != UserStatus.ACTIVE or user.archived_at is not None:
        raise EmailChangeError("ACCOUNT_UNAVAILABLE")
    return user


def request_change(db, current, email, password, platform_emails, locale):
    user = locked_user(db, current)
    if user.is_organization_root:
        raise EmailChangeError("ROOT_IDENTITY_PROTECTED")
    if not verify_password(password, user.password_hash):
        raise EmailChangeError("CURRENT_PASSWORD_INCORRECT")
    email = email.strip().lower()
    if email == user.email:
        raise EmailChangeError("EMAIL_UNCHANGED")
    if db.scalar(select(User.id).where(User.email == email)) or platform_emails.email_exists(email):
        raise EmailChangeError("EMAIL_UNAVAILABLE")
    pending = db.get(UserEmailChange, user.id)
    if pending:
        db.delete(pending)
        db.flush()
    old_code, new_code = secrets.token_hex(16), secrets.token_hex(16)
    db.add(UserEmailChange(user_id=user.id, organization_id=user.organization_id, old_email=user.email, new_email=email,
        old_hash=hash_token(old_code), new_hash=hash_token(new_code), expires_at=utc_now()+timedelta(minutes=15), token_version=user.token_version))
    db.flush()
    mail = EmailService()
    for address, code in ((user.email, old_code), (email, new_code)):
        subject = "تأكيد تغيير بريد الحساب — IORP" if locale == "ar" else "Confirm account email change — IORP"
        body = ("أدخل رمز التحقق التالي في ملفك الشخصي. صلاحيته 15 دقيقة. إذا لم تطلب التغيير فلا تشارك الرمز: " if locale == "ar" else "Enter this verification code in your profile within 15 minutes. If you did not request this change, do not share the code: ") + code
        if not mail.send_email(address, subject, '<p dir="'+('rtl' if locale == 'ar' else 'ltr')+'">'+escape(body)+'</p>', body):
            db.rollback()
            raise EmailChangeError("EMAIL_DELIVERY_FAILED")
    log_tenant_audit(db, user.organization_id, "user.email_change_requested", "user", user.id, user.id, user.full_name, user.email)
    db.commit()


def confirm_change(db, current, old_code, new_code, platform_emails):
    user = locked_user(db, current)
    pending = db.get(UserEmailChange, user.id)
    if not pending or pending.organization_id != user.organization_id or pending.old_email != user.email or pending.token_version != user.token_version or is_token_expired(pending.expires_at):
        raise EmailChangeError("EMAIL_CHANGE_EXPIRED")
    if not hmac.compare_digest(pending.old_hash, hash_token(old_code)) or not hmac.compare_digest(pending.new_hash, hash_token(new_code)):
        raise EmailChangeError("EMAIL_CHANGE_CODES_INVALID")
    if db.scalar(select(User.id).where(User.email == pending.new_email)) or platform_emails.email_exists(pending.new_email):
        raise EmailChangeError("EMAIL_UNAVAILABLE")
    old_email = user.email
    user.email = pending.new_email
    user.token_version += 1
    revoke_account_sessions(db, "tenant", user.id, reason="email_changed")
    db.execute(update(TenantPasswordResetToken).where(TenantPasswordResetToken.user_id == user.id, TenantPasswordResetToken.used_at.is_(None)).values(used_at=utc_now()))
    log_tenant_audit(db, user.organization_id, "user.email_changed", "user", user.id, user.id, user.full_name, old_email, user.full_name, {"email": {"before": old_email, "after": user.email}})
    db.delete(pending)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise EmailChangeError("EMAIL_UNAVAILABLE") from exc
