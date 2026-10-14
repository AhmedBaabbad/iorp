import logging

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.email.service import EmailService
from app.core.email.templates import build_platform_reset_email
from app.core.password_policy import validate_password
from app.core.security import has_usable_password, hash_password, normalize_email, revoke_account_sessions
from app.core.token_utils import generate_reset_token, get_reset_expiry_time, hash_token, is_token_expired, link_lifetime_minutes
from app.core.utils import utc_now
from app.platform.application.security_log import log_platform_security
from app.platform.domain.enums import PlatformAccountStatus
from app.platform.infrastructure.models import PlatformAccount, PlatformPasswordResetToken

logger = logging.getLogger(__name__)
PLATFORM_PASSWORD_RESET_VIA_EMAIL = "platform.password_reset_via_email"


class InvalidResetTokenError(ValueError): pass
class ResetTokenExpiredError(ValueError): pass
class PasswordTooWeakError(ValueError): pass


class PlatformPasswordResetService:
    def __init__(self, email_service: EmailService | None = None) -> None:
        self.email_service = email_service or EmailService()

    def request_reset(self, db: Session, email: str, locale: str | None = None) -> bool:
        """E-mails a reset link; True when it went out (the public form never tells; SEC-002 tells the administrator)."""
        account = db.scalar(select(PlatformAccount).where(PlatformAccount.email == normalize_email(email), PlatformAccount.status != PlatformAccountStatus.INACTIVE).with_for_update())
        if account is None:
            logger.info("Platform password reset requested for an unknown email")
            return False
        db.execute(update(PlatformPasswordResetToken).where(PlatformPasswordResetToken.account_id == account.id, PlatformPasswordResetToken.used_at.is_(None)).values(used_at=utc_now()))
        invitation = not has_usable_password(account.password_hash)  # SEC-003: a new account is activated the same way
        lifetime = link_lifetime_minutes(invitation)
        raw, token_hash = generate_reset_token()
        db.add(PlatformPasswordResetToken(account_id=account.id, token_hash=token_hash, expires_at=get_reset_expiry_time(lifetime)))
        db.flush()
        settings = get_settings()
        reset_url = f"{settings.platform_frontend_url.rstrip('/')}/platform/reset-password?token={raw}" + ("&invite=1" if invitation else "")
        subject, html, text = build_platform_reset_email(locale or "ar", reset_url, account.full_name, lifetime, invitation)
        db.commit()
        if not self.email_service.send_email(account.email, subject, html, text):
            db.execute(update(PlatformPasswordResetToken).where(PlatformPasswordResetToken.token_hash == token_hash).values(used_at=utc_now()))
            db.commit()
            return False
        return True

    def execute_reset(self, db: Session, raw_token: str, new_password: str) -> None:
        record = db.scalar(select(PlatformPasswordResetToken).where(PlatformPasswordResetToken.token_hash == hash_token(raw_token), PlatformPasswordResetToken.used_at.is_(None)))
        if record is None:
            raise InvalidResetTokenError
        account = db.scalar(select(PlatformAccount).where(PlatformAccount.id == record.account_id, PlatformAccount.status != PlatformAccountStatus.INACTIVE)
                            .with_for_update().execution_options(populate_existing=True))
        if account is None:
            raise InvalidResetTokenError
        record = db.scalar(select(PlatformPasswordResetToken).where(PlatformPasswordResetToken.id == record.id,
            PlatformPasswordResetToken.used_at.is_(None)).with_for_update().execution_options(populate_existing=True))
        if record is None:
            raise InvalidResetTokenError
        if is_token_expired(record.expires_at):
            record.used_at = utc_now(); db.commit()
            raise ResetTokenExpiredError
        try:
            validate_password(new_password, new_password, account.email, 12)
        except ValueError as exc:
            raise PasswordTooWeakError(str(exc)) from exc
        account.password_hash = hash_password(new_password); account.token_version += 1
        account.failed_login_attempts = 0; account.auto_locked_until = None; account.last_failed_login_at = None; account.password_changed_at = utc_now()
        db.execute(update(PlatformPasswordResetToken).where(PlatformPasswordResetToken.account_id == account.id, PlatformPasswordResetToken.used_at.is_(None)).values(used_at=utc_now()))
        revoke_account_sessions(db, "platform", account.id, reason="password_reset_via_email")
        log_platform_security(db, PLATFORM_PASSWORD_RESET_VIA_EMAIL, account.id, account.email, details={"sessions_invalidated": True})
        db.commit()
