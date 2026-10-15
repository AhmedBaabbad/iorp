from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.auth_cookies import clear_refresh_cookie, request_metadata, set_refresh_cookie
from app.core.login_protection import LoginProtectionError
from app.core.rate_limit import LoginRateLimitError, check_rate_limit
from fastapi.responses import JSONResponse
from app.core.security import TokenValidationError, decode_token, revoke_account_sessions, revoke_refresh_token, rotate_refresh_token, hash_password, verify_password
from app.core.password_policy import validate_password
from app.dependencies import get_current_platform_account, get_db
from app.platform.api.schemas import (
    ChangePasswordRequest,
    PlatformLoginRequest,
    PlatformLoginResponse,
    PlatformMeResponse,
)
from app.platform.application.services import PlatformAuthService
from app.platform.application.security_log import (
    PLATFORM_LOGIN_FAILED, PLATFORM_LOGIN_SUCCESS, PLATFORM_PASSWORD_CHANGED,
    PLATFORM_TOKEN_REFRESHED, log_platform_security,
)
from app.platform.infrastructure.models import PlatformAccount
from app.platform.domain.enums import PlatformAccountRole
from app.platform.domain.permissions import PLATFORM_ROLE_PERMISSIONS

router = APIRouter(prefix="/platform", tags=["platform"])


@router.post("/login", response_model=PlatformLoginResponse)
def platform_login(
    payload: PlatformLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    try:
        check_rate_limit(request, "platform_login", limit=settings.platform_login_rate_limit)
    except LoginRateLimitError as exc:
        return JSONResponse(status_code=429, headers={"Retry-After": str(exc.retry_after_seconds)}, content={"code": "RATE_LIMIT_EXCEEDED", "message": "Too many login attempts. Please try again later.", "retry_after_seconds": exc.retry_after_seconds})
    try:
        ip, user_agent = request_metadata(request)
        pair = PlatformAuthService(db).login(str(payload.email), payload.password, ip=ip, user_agent=user_agent, mfa_code=payload.mfa_code)
    except LoginProtectionError as exc:
        content = {"code": exc.code, "message": exc.message}
        if exc.locked_until is not None:
            content.update({"locked_until": exc.locked_until.isoformat(), "retry_after_seconds": exc.retry_after_seconds})
        return JSONResponse(status_code=403, content=content)
    if pair is None:
        log_platform_security(db, PLATFORM_LOGIN_FAILED, ip_address=ip, user_agent=user_agent,
                              details={"reason": "invalid_credentials"})
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    claims = decode_token(pair.access_token, "access")
    account = db.get(PlatformAccount, UUID(str(claims["sub"])))
    if account:
        log_platform_security(db, PLATFORM_LOGIN_SUCCESS, account.id, account.email, ip, user_agent)
        db.commit()
    set_refresh_cookie(response, pair.refresh_token, account_type="platform")
    return PlatformLoginResponse(access_token=pair.access_token, expires_in=pair.access_expires_in)


@router.post("/refresh", response_model=PlatformLoginResponse)
def platform_refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    try:
        check_rate_limit(request, "platform_refresh", limit=settings.refresh_rate_limit)
    except LoginRateLimitError as exc:
        return JSONResponse(status_code=429, headers={"Retry-After": str(exc.retry_after_seconds)}, content={"code": "RATE_LIMIT_EXCEEDED", "message": "Too many requests."})
    raw = request.cookies.get(settings.refresh_cookie_name)
    if not raw:
        return JSONResponse(status_code=401, content={"code": "INVALID_TOKEN", "message": "The session is no longer valid."})
    try:
        claims = decode_token(raw, "refresh")
        if claims["account_type"] != "platform":
            raise TokenValidationError("TOKEN_TYPE_INVALID")
        account = db.get(PlatformAccount, UUID(str(claims["sub"])))
        if account is None or account.status.value != "active":
            raise TokenValidationError("ACCOUNT_INACTIVE")
        if account.token_version != claims["token_version"]:
            raise TokenValidationError("SESSION_INVALIDATED")
        from app.platform.infrastructure.mfa_models import PlatformMFA
        from app.platform.application.mfa import digest
        factor = db.get(PlatformMFA, account.id)
        if factor and factor.enabled and claims.get('mfa') != digest(factor.secret):
            raise TokenValidationError('MFA_SESSION_REQUIRED')
        ip, user_agent = request_metadata(request)
        _, pair = rotate_refresh_token(db, raw, "platform", ip=ip, user_agent=user_agent)
        log_platform_security(db, PLATFORM_TOKEN_REFRESHED, account.id, account.email, ip, user_agent)
        db.commit()
    except (TokenValidationError, ValueError, TypeError) as exc:
        clear_refresh_cookie(response, account_type="platform")
        error = exc if isinstance(exc, TokenValidationError) else TokenValidationError("INVALID_TOKEN")
        return JSONResponse(status_code=401, content={"code": error.code, "message": "The session is no longer valid."})
    set_refresh_cookie(response, pair.refresh_token, account_type="platform")
    return PlatformLoginResponse(access_token=pair.access_token, expires_in=pair.access_expires_in)


@router.post("/logout", status_code=204)
def platform_logout(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get(settings.refresh_cookie_name)
    if raw:
        try:
            ip, user_agent = request_metadata(request)
            revoke_refresh_token(db, raw, "platform", ip=ip, user_agent=user_agent)
        except TokenValidationError:
            pass
    clear_refresh_cookie(response, account_type="platform")
    response.status_code = 204
    return response


@router.get("/me", response_model=PlatformMeResponse)
def platform_me(
    account: PlatformAccount = Depends(get_current_platform_account),
    db: Session = Depends(get_db),
):
    from app.platform.infrastructure.mfa_models import PlatformMFA
    factor = db.get(PlatformMFA, account.id)
    role = PlatformAccountRole.ROOT if account.is_root else account.role
    return PlatformMeResponse(
        id=account.id,
        full_name=account.full_name,
        email=account.email,
        is_root=account.is_root,
        role=role,
        permissions=sorted(permission.value for permission in PLATFORM_ROLE_PERMISSIONS[role]),
        mfa_enrollment_required=settings.platform_mfa_required and not (factor and factor.enabled),
    )


@router.post("/change-password")
@router.post("/account/change-password")
def change_password(
    payload: ChangePasswordRequest,
    account: PlatformAccount = Depends(get_current_platform_account),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, account.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    try:
        validate_password(payload.new_password, payload.password_confirmation, account.email, 12)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if verify_password(payload.new_password, account.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must be different from current password.")
    account.password_hash = hash_password(payload.new_password)
    account.password_changed_at = datetime.now(timezone.utc)
    account.token_version += 1
    revoke_account_sessions(db, "platform", account.id, reason="password_changed")
    log_platform_security(db, PLATFORM_PASSWORD_CHANGED, account.id, account.email,
                          details={"sessions_invalidated": True})
    db.commit()
    return {"message": "Password changed successfully."}
