from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets
from typing import Any, Literal
from uuid import UUID, uuid4

from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security_models import AuthSecurityEvent, AuthSession

AccountType = Literal["tenant", "platform"]
TokenType = Literal["access", "refresh"]


class TokenValidationError(ValueError):
    def __init__(self, code: str, message: str = "The token is invalid.") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_expires_in: int


def normalize_email(email: str) -> str:
    return email.strip().lower() if email else email


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


_DUMMY_PASSWORD_HASH = pwd_context.hash("iorp-login-enumeration-sentinel")


UNUSABLE_PASSWORD_PREFIX = "!"


def unusable_password_hash() -> str:
    """SEC-003: a new account waits for its owner to choose a password through the activation link; nothing signs in."""
    return UNUSABLE_PASSWORD_PREFIX + secrets.token_urlsafe(32)


def has_usable_password(hashed_password: str | None) -> bool:
    return bool(hashed_password) and not hashed_password.startswith(UNUSABLE_PASSWORD_PREFIX)


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    if not has_usable_password(hashed_password):
        pwd_context.verify(plain_password, _DUMMY_PASSWORD_HASH)  # the same time either way
        return False
    return pwd_context.verify(plain_password, hashed_password)


def _jti_hash(jti: str) -> str:
    return sha256(jti.encode("utf-8")).hexdigest()


def _expiry(account_type: AccountType, token_type: TokenType) -> timedelta:
    if token_type == "access":
        minutes = settings.tenant_access_token_minutes if account_type == "tenant" else settings.platform_access_token_minutes
        return timedelta(minutes=minutes)
    if account_type == "tenant":
        return timedelta(days=settings.tenant_refresh_token_days)
    return timedelta(hours=settings.platform_refresh_token_hours)


def _validate_scope(account_type: str, organization_id: str | UUID | None) -> None:
    if account_type not in {"tenant", "platform"}:
        raise TokenValidationError("INVALID_TOKEN", "Unknown account type.")
    if account_type == "tenant" and organization_id is None:
        raise TokenValidationError("INVALID_TOKEN", "Tenant token requires an organization.")
    if account_type == "platform" and organization_id is not None:
        raise TokenValidationError("INVALID_TOKEN", "Platform token cannot contain an organization.")


def _encode_token(
    *, subject: str, account_type: AccountType, token_type: TokenType,
    token_version: int, organization_id: str | UUID | None, extra_claims: dict[str, Any] | None = None,
    jti: str | None = None,
) -> tuple[str, str, datetime]:
    _validate_scope(account_type, organization_id)
    now = datetime.now(timezone.utc)
    expires_at = now + _expiry(account_type, token_type)
    token_jti = jti or str(uuid4())
    payload: dict[str, Any] = {
        "sub": subject, "account_type": account_type, "token_type": token_type,
        "jti": token_jti, "token_version": token_version,
        "iat": now, "nbf": now, "exp": expires_at,
        "iss": settings.jwt_issuer, "aud": settings.jwt_audience,
    }
    if organization_id is not None:
        payload["organization_id"] = str(organization_id)
    if extra_claims:
        reserved = {"sub", "account_type", "token_type", "jti", "token_version", "iat", "nbf", "exp", "iss", "aud", "organization_id"}
        payload.update({key: value for key, value in extra_claims.items() if key not in reserved})
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM), token_jti, expires_at


def create_access_token(subject: str, claims: dict[str, Any] | None = None) -> str:
    claims = claims or {}
    raw_type = claims.get("account_type")
    account_type: AccountType = "tenant" if raw_type in {"tenant", "user"} else "platform" if raw_type == "platform" else raw_type
    token, _, _ = _encode_token(
        subject=subject,
        account_type=account_type,
        token_type="access",
        token_version=int(claims.get("token_version", 0)),
        organization_id=claims.get("organization_id"),
        extra_claims=claims,
    )
    return token


def decode_token(token: str, expected_token_type: TokenType | None = None) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[ALGORITHM],
            audience=settings.jwt_audience, issuer=settings.jwt_issuer,
            options={"require_exp": True, "require_iat": True, "require_nbf": True, "leeway": settings.jwt_clock_skew_seconds},
        )
    except ExpiredSignatureError as exc:
        raise TokenValidationError("TOKEN_EXPIRED", "The token has expired.") from exc
    except JWTError as exc:
        raise TokenValidationError("INVALID_TOKEN") from exc
    mandatory = {"sub", "account_type", "token_type", "jti", "token_version", "iat", "nbf", "exp", "iss", "aud"}
    if mandatory.difference(payload):
        raise TokenValidationError("INVALID_TOKEN", "The token is missing required claims.")
    _validate_scope(payload["account_type"], payload.get("organization_id"))
    if payload["token_type"] not in {"access", "refresh"}:
        raise TokenValidationError("TOKEN_TYPE_INVALID")
    if expected_token_type and payload["token_type"] != expected_token_type:
        raise TokenValidationError("TOKEN_TYPE_INVALID", f"A {expected_token_type} token is required.")
    if not isinstance(payload["token_version"], int) or not payload["jti"]:
        raise TokenValidationError("INVALID_TOKEN")
    return payload


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return decode_token(token, "access")
    except TokenValidationError:
        return None


def _audit(db: Session, event_type: str, payload: dict[str, Any], *, reason: str | None = None, ip: str | None = None, user_agent: str | None = None) -> None:
    try:
        account_type = payload.get("account_type")
        actor_id = UUID(str(payload["sub"])) if payload.get("sub") else None
        details = {"reason": reason} if reason else None
        if account_type == "tenant" and payload.get("organization_id"):
            from app.foundation.application.security_log import log_tenant_security
            log_tenant_security(db, UUID(str(payload["organization_id"])), f"tenant.{event_type}",
                                actor_id, ip_address=ip, user_agent=user_agent, details=details)
        else:
            from app.platform.application.security_log import log_platform_security
            log_platform_security(db, f"platform.{event_type}", actor_id if account_type == "platform" else None,
                                  ip_address=ip, user_agent=user_agent, details=details)
    except (ValueError, TypeError):
        pass


def record_security_event(db: Session, event_type: str, payload: dict[str, Any] | None = None, *, reason: str | None = None, ip: str | None = None, user_agent: str | None = None) -> None:
    _audit(db, event_type, payload or {}, reason=reason, ip=ip, user_agent=user_agent)
    db.commit()


def issue_token_pair(
    db: Session, *, account_id: UUID, account_type: AccountType, token_version: int,
    organization_id: UUID | None = None, extra_claims: dict[str, Any] | None = None,
    family_id: UUID | None = None, ip: str | None = None, user_agent: str | None = None,
    commit: bool = True, started_at: datetime | None = None,
) -> TokenPair:
    family_id = family_id or uuid4()
    # SEC-001: the access token names its sign-in ("sid"), so ending the sign-in ends the access token at once.
    claims = {**(extra_claims or {}), "sid": str(family_id)}
    access, _, access_exp = _encode_token(subject=str(account_id), account_type=account_type, token_type="access", token_version=token_version, organization_id=organization_id, extra_claims=claims)
    refresh, refresh_jti, refresh_exp = _encode_token(subject=str(account_id), account_type=account_type, token_type="refresh", token_version=token_version, organization_id=organization_id)
    db.add(AuthSession(
        jti_hash=_jti_hash(refresh_jti), family_id=family_id, account_type=account_type,
        account_id=account_id, organization_id=organization_id, token_version=token_version, expires_at=refresh_exp,
        started_at=started_at or datetime.now(timezone.utc), ip_address=(ip or "")[:64] or None, user_agent=(user_agent or "")[:500] or None,
    ))
    # Issuing, rotating and revoking a token are routine mechanics, not security events (ORG-AUDIT-002): the security log
    # keeps what a person did or suffered — sign-in, failure, lock, password change, a stolen token reused, sessions ended.
    if commit:
        db.commit()
    else:
        db.flush()
    return TokenPair(access, refresh, max(1, int((access_exp - datetime.now(timezone.utc)).total_seconds())))


def rotate_refresh_token(db: Session, raw_token: str, expected_account_type: AccountType, *, ip: str | None = None, user_agent: str | None = None) -> tuple[dict[str, Any], TokenPair]:
    payload = decode_token(raw_token, "refresh")
    if payload["account_type"] != expected_account_type:
        raise TokenValidationError("TOKEN_TYPE_INVALID")
    hashed = _jti_hash(str(payload["jti"]))
    session = db.scalar(select(AuthSession).where(AuthSession.jti_hash == hashed).with_for_update())
    if session is None:
        raise TokenValidationError("TOKEN_REVOKED")
    if (
        session.account_type != payload.get("account_type")
        or str(session.account_id) != str(payload.get("sub"))
        or (str(session.organization_id) if session.organization_id else None) != payload.get("organization_id")
        or session.token_version != payload.get("token_version")
    ):
        raise TokenValidationError("INVALID_TOKEN")
    if session.revoked_at is not None:
        if session.replaced_by_jti_hash:
            now = datetime.now(timezone.utc)
            db.execute(update(AuthSession).where(AuthSession.family_id == session.family_id, AuthSession.revoked_at.is_(None)).values(revoked_at=now, revocation_reason="reuse_detected"))
            _audit(db, "refresh_token_reuse_detected", payload, reason="rotated_token_reused", ip=ip, user_agent=user_agent)
            db.commit()
            raise TokenValidationError("TOKEN_REUSED")
        raise TokenValidationError("TOKEN_REVOKED")
    now = datetime.now(timezone.utc)
    if session.expires_at <= now:
        raise TokenValidationError("TOKEN_EXPIRED")
    started = session.started_at or session.created_at
    if started is not None and started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    if expected_account_type == "tenant" and started and now - started >= timedelta(hours=settings.tenant_session_max_hours):
        # SEC-001: the sign-in reached its absolute lifetime; the user signs in again (even if active all along).
        db.execute(update(AuthSession).where(AuthSession.family_id == session.family_id, AuthSession.revoked_at.is_(None))
                   .values(revoked_at=now, revocation_reason="max_age"))
        db.commit()
        raise TokenValidationError("SESSION_MAX_AGE")
    pair = issue_token_pair(
        db, account_id=session.account_id, account_type=expected_account_type,
        token_version=session.token_version, organization_id=session.organization_id,
        family_id=session.family_id, ip=ip, user_agent=user_agent, commit=False,
        started_at=started,
    )
    new_payload = decode_token(pair.refresh_token, "refresh")
    session.revoked_at = now
    session.replaced_by_jti_hash = _jti_hash(str(new_payload["jti"]))
    session.revocation_reason = "rotated"
    db.commit()
    return payload, pair


def revoke_refresh_token(db: Session, raw_token: str, expected_account_type: AccountType, *, reason: str = "logout", ip: str | None = None, user_agent: str | None = None) -> None:
    payload = decode_token(raw_token, "refresh")
    if payload["account_type"] != expected_account_type:
        raise TokenValidationError("TOKEN_TYPE_INVALID")
    session = db.scalar(select(AuthSession).where(AuthSession.jti_hash == _jti_hash(str(payload["jti"]))).with_for_update())
    if session and session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        session.revocation_reason = reason
        _audit(db, "session_revoked", payload, reason=reason, ip=ip, user_agent=user_agent)
        db.commit()


def revoke_account_sessions(db: Session, account_type: AccountType, account_id: UUID, *, reason: str) -> int:
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(AuthSession)
        .where(AuthSession.account_type == account_type, AuthSession.account_id == account_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now, revocation_reason=reason)
    )
    _audit(db, "all_sessions_revoked", {"account_type": account_type, "sub": str(account_id)}, reason=reason)
    return int(result.rowcount or 0)


def revoke_organization_sessions(db: Session, organization_id: UUID, *, reason: str) -> int:
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(AuthSession)
        .where(AuthSession.account_type == "tenant", AuthSession.organization_id == organization_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now, revocation_reason=reason)
    )
    return int(result.rowcount or 0)


# ── SEC-001: sign-ins (sessions) as people see them ──────────────────────────────────────────────────────────────────────
def session_active(db: Session, family_id: str | UUID) -> bool:
    """The sign-in still holds a live token (not ended, not expired)."""
    try:
        family = UUID(str(family_id))
    except ValueError:
        return False
    return db.scalar(select(AuthSession.id).where(AuthSession.family_id == family, AuthSession.revoked_at.is_(None),
                                                  AuthSession.expires_at > datetime.now(timezone.utc)).limit(1)) is not None


def active_sessions(db: Session, account_type: AccountType, account_id: UUID) -> list[dict[str, Any]]:
    """The account's live sign-ins, newest first: when each began, its device, and its last renewal."""
    now = datetime.now(timezone.utc)
    rows = db.scalars(select(AuthSession).where(AuthSession.account_type == account_type, AuthSession.account_id == account_id)
                      .order_by(AuthSession.created_at)).all()
    families: dict[UUID, dict[str, Any]] = {}
    for row in rows:
        entry = families.setdefault(row.family_id, dict(id=row.family_id, started_at=row.started_at or row.created_at, ip_address=row.ip_address,
                                                        user_agent=row.user_agent, last_active_at=row.created_at, live=False))
        entry["last_active_at"] = max(entry["last_active_at"], row.created_at)
        entry["ip_address"], entry["user_agent"] = row.ip_address or entry["ip_address"], row.user_agent or entry["user_agent"]
        if row.revoked_at is None and row.expires_at > now:
            entry["live"] = True
    return sorted((f for f in families.values() if f["live"]), key=lambda f: f["started_at"], reverse=True)


def end_sessions(db: Session, account_type: AccountType, account_id: UUID, family_ids, *, reason: str) -> int:
    """Ends these sign-ins of the account (their access tokens stop at once, SEC-001); the caller commits."""
    ids = [UUID(str(f)) for f in family_ids]
    if not ids:
        return 0
    result = db.execute(update(AuthSession).where(AuthSession.account_type == account_type, AuthSession.account_id == account_id,
                                                  AuthSession.family_id.in_(ids), AuthSession.revoked_at.is_(None))
                        .values(revoked_at=datetime.now(timezone.utc), revocation_reason=reason))
    return int(result.rowcount or 0)


def known_device(db: Session, account_type: AccountType, account_id: UUID, user_agent: str | None, exclude_family: UUID | None = None) -> bool | None:
    """Has the account signed in from this browser before? None when it never signed in before at all."""
    query = select(AuthSession.user_agent).where(AuthSession.account_type == account_type, AuthSession.account_id == account_id)
    if exclude_family is not None:
        query = query.where(AuthSession.family_id != exclude_family)
    seen = set(db.scalars(query.distinct()))
    if not seen:
        return None
    return (user_agent or None) in seen


def describe_device(user_agent: str | None) -> str:
    """"Chrome · Windows" from a browser's user agent (shown to people; never trusted for security decisions)."""
    ua = user_agent or ""
    browser = next((name for name, mark in (("Edge", "Edg/"), ("Opera", "OPR/"), ("Samsung Internet", "SamsungBrowser"), ("Chrome", "Chrome/"),
                                            ("Firefox", "Firefox/"), ("Safari", "Safari/")) if mark in ua), "")
    system = next((name for name, mark in (("Android", "Android"), ("iPhone", "iPhone"), ("iPad", "iPad"), ("Windows", "Windows"),
                                           ("macOS", "Mac OS X"), ("Linux", "Linux")) if mark in ua), "")
    return " · ".join(p for p in (browser, system) if p) or (ua[:60] if ua else "—")
