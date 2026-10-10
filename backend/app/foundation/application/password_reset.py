import logging

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.email.service import EmailService
from app.core.email.templates import build_tenant_reset_email
from app.core.password_policy import validate_password
from app.core.security import hash_password, normalize_email, revoke_account_sessions
from app.core.token_utils import generate_reset_token, get_reset_expiry_time, hash_token, is_token_expired
from app.core.utils import utc_now
from app.foundation.application.security_log import log_tenant_security
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, TenantPasswordResetToken, User

logger = logging.getLogger(__name__)
TENANT_PASSWORD_RESET_VIA_EMAIL = "tenant.password_reset_via_email"


class InvalidResetTokenError(ValueError): pass
class ResetTokenExpiredError(ValueError): pass
class PasswordTooWeakError(ValueError): pass


class TenantPasswordResetService:
    def __init__(self, email_service: EmailService | None = None) -> None:
        self.email_service = email_service or EmailService()

    def request_reset(self, db: Session, email: str) -> None:
        user = db.scalar(select(User).where(User.email == normalize_email(email), User.status != UserStatus.INACTIVE).with_for_update())
        if user is None:
            logger.info("Tenant password reset requested for an unknown email")
            return
        organization = db.scalar(select(Organization).where(Organization.id == user.organization_id, Organization.status == OrganizationStatus.ACTIVE))
        if organization is None:
            return
        now = utc_now()
        db.execute(update(TenantPasswordResetToken).where(TenantPasswordResetToken.user_id == user.id, TenantPasswordResetToken.used_at.is_(None)).values(used_at=now))
        raw, token_hash = generate_reset_token()
        db.add(TenantPasswordResetToken(user_id=user.id, organization_id=user.organization_id, token_hash=token_hash, expires_at=get_reset_expiry_time()))
        db.flush()
        settings = get_settings()
        reset_url = f"{settings.frontend_url.rstrip('/')}/reset-password?token={raw}"
        subject, html, text = build_tenant_reset_email(user.preferred_locale or organization.default_locale or "ar", reset_url, user.full_name, organization.name, settings.password_reset_expiry_minutes)
        db.commit()
        self.email_service.send_email(user.email, subject, html, text)

    def execute_reset(self, db: Session, raw_token: str, new_password: str) -> None:
        record = db.scalar(select(TenantPasswordResetToken).where(TenantPasswordResetToken.token_hash == hash_token(raw_token), TenantPasswordResetToken.used_at.is_(None)))
        if record is None:
            raise InvalidResetTokenError
        # Serialize on the account before locking tokens: every reset path uses
        # this order, including invalidation of all outstanding tokens.
        user = db.scalar(select(User).where(User.id == record.user_id, User.organization_id == record.organization_id, User.status != UserStatus.INACTIVE)
                         .with_for_update().execution_options(populate_existing=True))
        if user is None:
            raise InvalidResetTokenError
        record = db.scalar(select(TenantPasswordResetToken).where(TenantPasswordResetToken.id == record.id,
            TenantPasswordResetToken.used_at.is_(None)).with_for_update().execution_options(populate_existing=True))
        if record is None:
            raise InvalidResetTokenError
        if is_token_expired(record.expires_at):
            record.used_at = utc_now(); db.commit()
            raise ResetTokenExpiredError
        try:
            validate_password(new_password, new_password, user.email, 12)
        except ValueError as exc:
            raise PasswordTooWeakError(str(exc)) from exc
        now = utc_now()
        user.password_hash = hash_password(new_password); user.token_version += 1
        user.failed_login_attempts = 0; user.auto_locked_until = None; user.last_failed_login_at = None
        db.execute(update(TenantPasswordResetToken).where(TenantPasswordResetToken.user_id == user.id, TenantPasswordResetToken.used_at.is_(None)).values(used_at=now))
        revoke_account_sessions(db, "tenant", user.id, reason="password_reset_via_email")
        log_tenant_security(db, user.organization_id, TENANT_PASSWORD_RESET_VIA_EMAIL, user.id, user.email, details={"sessions_invalidated": True})
        db.commit()
