from uuid import UUID
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.auth_cookies import clear_refresh_cookie, request_metadata, set_refresh_cookie
from app.core.security import TokenValidationError, decode_token, revoke_refresh_token, rotate_refresh_token
from app.core.login_protection import InvalidCredentialsError, LoginProtectionError
from app.core.rate_limit import LoginRateLimitError, check_rate_limit
from app.core.organization_access import OrganizationAccessError
from fastapi.responses import JSONResponse
from app.dependencies import CurrentUserContext, get_current_user, get_db
from app.foundation.api.schemas import (
    CurrentUserResponse,
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
    UserProfileResponse,
    UserProfileUpdate,
    EffectiveAccessResponse,
)
from app.foundation.application.effective_access import compute_effective_access
from app.foundation.api.routes_users import _effective_access_locale, _effective_access_response
from app.foundation.application.services import FoundationService, OrganizationRootProtectionError


from app.foundation.application.sessions import SessionService

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> LoginResponse:
    try:
        check_rate_limit(request, "tenant_login", limit=settings.login_rate_limit)
    except LoginRateLimitError as exc:
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(exc.retry_after_seconds)},
            content={"code": "RATE_LIMIT_EXCEEDED", "message": "Too many login attempts. Please try again later.", "retry_after_seconds": exc.retry_after_seconds},
        )
    service = FoundationService(db)
    try:
        ip, user_agent = request_metadata(request)
        login_response = service.login(payload, ip=ip, user_agent=user_agent)
    except OrganizationAccessError as exc:
        return JSONResponse(status_code=403, content={"code": exc.code, "message": exc.message})
    except LoginProtectionError as exc:
        content = {"code": exc.code, "message": exc.message}
        if exc.locked_until is not None:
            content.update({"locked_until": exc.locked_until.isoformat(), "retry_after_seconds": exc.retry_after_seconds})
        return JSONResponse(status_code=403, content=content)
    except InvalidCredentialsError as exc:
        return JSONResponse(
            status_code=401,
            content={
                "code": "INVALID_CREDENTIALS",
                "message": "Invalid credentials.",
                "failed_login_attempts": exc.failed_attempts,
                "remaining_attempts": exc.remaining_attempts,
            },
        )
    if login_response is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )
    set_refresh_cookie(response, login_response.refresh_token or "", account_type="tenant")
    return login_response


def _token_error(exc: TokenValidationError) -> JSONResponse:
    return JSONResponse(status_code=401, content={"code": exc.code, "message": "The session is no longer valid."})


@router.post("/refresh", response_model=LoginResponse)
def refresh_session(request: Request, response: Response, db: Session = Depends(get_db)):
    try:
        check_rate_limit(request, "tenant_refresh", limit=settings.refresh_rate_limit)
    except LoginRateLimitError as exc:
        return JSONResponse(status_code=429, headers={"Retry-After": str(exc.retry_after_seconds)}, content={"code": "RATE_LIMIT_EXCEEDED", "message": "Too many requests."})
    raw = request.cookies.get(settings.refresh_cookie_name)
    if not raw:
        return JSONResponse(status_code=401, content={"code": "INVALID_TOKEN", "message": "The session is no longer valid."})
    try:
        claims = decode_token(raw, "refresh")
        if claims["account_type"] != "tenant":
            raise TokenValidationError("TOKEN_TYPE_INVALID")
        user = FoundationService(db).get_user(UUID(str(claims["sub"])))
        if user is None or user.status.value != "active":
            raise TokenValidationError("ACCOUNT_INACTIVE")
        if str(user.organization_id) != claims.get("organization_id"):
            raise TokenValidationError("INVALID_TOKEN")
        if user.token_version != claims["token_version"]:
            raise TokenValidationError("SESSION_INVALIDATED")
        organization = user.organization
        if organization.status.value != "active":
            raise TokenValidationError("ORGANIZATION_UNAVAILABLE")
        ip, user_agent = request_metadata(request)
        _, pair = rotate_refresh_token(db, raw, "tenant", ip=ip, user_agent=user_agent)
        db.commit()
    except (TokenValidationError, ValueError, TypeError) as exc:
        clear_refresh_cookie(response, account_type="tenant")
        return _token_error(exc if isinstance(exc, TokenValidationError) else TokenValidationError("INVALID_TOKEN"))
    set_refresh_cookie(response, pair.refresh_token, account_type="tenant")
    return LoginResponse(access_token=pair.access_token, expires_in=pair.access_expires_in)


@router.post("/logout", status_code=204)
def logout_session(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get(settings.refresh_cookie_name)
    if raw:
        try:
            ip, user_agent = request_metadata(request)
            revoke_refresh_token(db, raw, "tenant", ip=ip, user_agent=user_agent)
        except TokenValidationError:
            pass
    clear_refresh_cookie(response, account_type="tenant")
    response.status_code = 204
    return response


@router.get("/me", response_model=CurrentUserResponse)
def me(current: CurrentUserContext = Depends(get_current_user)) -> CurrentUserResponse:
    return current.profile


@router.get("/me/profile", response_model=UserProfileResponse)
def my_profile(
    current: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserProfileResponse:
    return FoundationService(db).get_my_profile(current.user)


@router.get("/me/effective-access", response_model=EffectiveAccessResponse)
def my_effective_access(
    request: Request,
    current: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EffectiveAccessResponse:
    report = compute_effective_access(db, current.user.id, current.tenant.organization_id)
    return _effective_access_response(report, _effective_access_locale(request, current))


@router.patch("/me", response_model=UserProfileResponse)
def update_my_profile(
    payload: UserProfileUpdate,
    current: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserProfileResponse:
    try:
        return FoundationService(db).update_my_profile(current.user, payload)
    except OrganizationRootProtectionError as exc:
        return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "message": str(exc)})
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/change-password")
def change_password(
    payload: PasswordChangeRequest,
    current: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str | bool]:
    try:
        FoundationService(db).change_password(current.user, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": exc.code, "message": str(exc)} if hasattr(exc, "code") else str(exc)) from exc
    return {
        "message": "Password changed successfully",
        "session_invalidated": True,
    }



# ── SEC-001: my sign-ins ─────────────────────────────────────────────────────────────────────────────────────────────────
class EndSessions(BaseModel):
    session_ids: list[UUID] = Field(default_factory=list, max_length=50)
    all_others: bool = False


@router.get("/sessions")
def my_sessions(current: CurrentUserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    """Where I am signed in: device, address, since when, last activity; this device marked."""
    return SessionService(db, current.tenant.organization_id).mine(current.user, current.session_id)


@router.post("/sessions/end")
def end_my_sessions(payload: EndSessions, current: CurrentUserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    """Ends some of my other sign-ins, or all of them but this one."""
    service = SessionService(db, current.tenant.organization_id)
    ids = [s["id"] for s in service.mine(current.user, current.session_id)] if payload.all_others else payload.session_ids
    return {"ended": service.end_mine(current.user, ids, current.session_id)}


from pydantic import BaseModel, EmailStr, Field, ConfigDict
from app.dependencies import get_platform_email_queries
from app.core.interfaces.platform_email_queries import PlatformEmailQueryInterface
from app.foundation.application.email_change import request_change, confirm_change, EmailChangeError
from app.foundation.api.routes_password_reset import _limited

class EmailChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    current_password: str = Field(min_length=1, max_length=1024)

class EmailChangeConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    old_code: str = Field(min_length=32, max_length=32)
    new_code: str = Field(min_length=32, max_length=32)

@router.post("/me/email-change")
def request_email_change(payload: EmailChangeRequest, request: Request, current: CurrentUserContext = Depends(get_current_user), db: Session = Depends(get_db), platform_emails: PlatformEmailQueryInterface = Depends(get_platform_email_queries)):
    limited = _limited(request, "email_change_request", 3)
    if limited: return limited
    try:
        request_change(db, current.user, str(payload.email), payload.current_password, platform_emails, _effective_access_locale(request, current))
    except EmailChangeError as exc:
        db.rollback()
        return JSONResponse(status_code=400, content={"code": exc.code, "detail": str(exc)})
    return {"message": "Verification sent to both mailboxes."}

@router.post("/me/email-change/confirm")
def confirm_email_change(payload: EmailChangeConfirmation, request: Request, current: CurrentUserContext = Depends(get_current_user), db: Session = Depends(get_db), platform_emails: PlatformEmailQueryInterface = Depends(get_platform_email_queries)):
    limited = _limited(request, "email_change_confirm", 5)
    if limited: return limited
    try:
        confirm_change(db, current.user, payload.old_code, payload.new_code, platform_emails)
    except EmailChangeError as exc:
        db.rollback()
        return JSONResponse(status_code=400, content={"code": exc.code, "detail": str(exc)})
    return {"message": "Email changed. Sign in again."}
