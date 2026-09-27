from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session


class LoginProtectionError(RuntimeError):
    def __init__(self, code: str, message: str, *, locked_until: datetime | None = None) -> None:
        self.code = code
        self.message = message
        self.locked_until = locked_until
        super().__init__(message)

    @property
    def retry_after_seconds(self) -> int | None:
        if self.locked_until is None:
            return None
        return max(1, int((self.locked_until - datetime.now(timezone.utc)).total_seconds() + 0.999))


class InvalidCredentialsError(RuntimeError):
    def __init__(self, failed_attempts: int, remaining_attempts: int) -> None:
        self.failed_attempts = failed_attempts
        self.remaining_attempts = remaining_attempts
        super().__init__("Invalid credentials.")


def clear_expired_lock(db: Session, account) -> None:
    now = datetime.now(timezone.utc)
    locked_until = account.auto_locked_until
    if locked_until is not None and locked_until <= now:
        account.auto_locked_until = None
        account.failed_login_attempts = 0
        db.commit()


def ensure_not_auto_locked(account) -> None:
    now = datetime.now(timezone.utc)
    if account.auto_locked_until is not None and account.auto_locked_until > now:
        raise LoginProtectionError(
            "ACCOUNT_TEMPORARILY_LOCKED",
            "Account temporarily locked due to multiple failed login attempts.",
            locked_until=account.auto_locked_until,
        )


def record_failed_login(db: Session, account, *, threshold: int, minutes: int, root_exempt: bool) -> int:
    # Serialize failures for the same account. Without this row lock, concurrent
    # requests can overwrite one another and postpone lockout indefinitely.
    model = type(account)
    locked_account = db.scalar(
        select(model)
        .where(model.id == account.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked_account is None:
        return 0
    now = datetime.now(timezone.utc)
    locked_account.failed_login_attempts = (locked_account.failed_login_attempts or 0) + 1
    locked_account.last_failed_login_at = now
    if locked_account.failed_login_attempts >= threshold and not root_exempt:
        locked_account.auto_locked_until = now + timedelta(minutes=minutes)
    db.commit()
    if locked_account.auto_locked_until is not None and not root_exempt:
        ensure_not_auto_locked(locked_account)
    return locked_account.failed_login_attempts


def record_successful_login(db: Session, account) -> None:
    account.failed_login_attempts = 0
    account.auto_locked_until = None
    account.last_failed_login_at = None
    account.last_login_at = datetime.now(timezone.utc)
    db.commit()
