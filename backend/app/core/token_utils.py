import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings


def generate_reset_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def get_reset_expiry_time() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=get_settings().password_reset_expiry_minutes)


def is_token_expired(expires_at: datetime) -> bool:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > expires_at
