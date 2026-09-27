from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
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


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    return pwd_context.verify(plain_password, hashed_password or _DUMMY_PASSWORD_HASH)


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
    commit: bool = True,
) -> TokenPair:
    access, _, access_exp = _encode_token(subject=str(account_id), account_type=account_type, token_type="access", token_version=token_version, organization_id=organization_id, extra_claims=extra_claims)
    refresh, refresh_jti, refresh_exp = _encode_token(subject=str(account_id), account_type=account_type, token_type="refresh", token_version=token_version, organization_id=organization_id)
    db.add(AuthSession(
        jti_hash=_jti_hash(refresh_jti), family_id=family_id or uuid4(), account_type=account_type,
        account_id=account_id, organization_id=organization_id, token_version=token_version, expires_at=refresh_exp,
    ))
    access_payload = decode_token(access, "access")
    refresh_payload = decode_token(refresh, "refresh")
    _audit(db, "access_token_issued", access_payload, ip=ip, user_agent=user_agent)
    _audit(db, "refresh_token_issued", refresh_payload, ip=ip, user_agent=user_agent)
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
    pair = issue_token_pair(
        db, account_id=session.account_id, account_type=expected_account_type,
        token_version=session.token_version, organization_id=session.organization_id,
        family_id=session.family_id, ip=ip, user_agent=user_agent, commit=False,
    )
    new_payload = decode_token(pair.refresh_token, "refresh")
    session.revoked_at = now
    session.replaced_by_jti_hash = _jti_hash(str(new_payload["jti"]))
    session.revocation_reason = "rotated"
    _audit(db, "refresh_token_rotated", payload, ip=ip, user_agent=user_agent)
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
        _audit(db, "refresh_token_revoked", payload, reason=reason, ip=ip, user_agent=user_agent)
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
