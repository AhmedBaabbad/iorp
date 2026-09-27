from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy.orm import Session

from app.core.rate_limit import LoginRateLimitError, check_rate_limit
from app.dependencies import get_db
from app.platform.application.password_reset import InvalidResetTokenError, PasswordTooWeakError, PlatformPasswordResetService, ResetTokenExpiredError

router = APIRouter(prefix="/platform/auth", tags=["platform-password-reset"])


class ForgotPasswordRequest(BaseModel): email: EmailStr
class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str
    new_password_confirmation: str
    @model_validator(mode="after")
    def passwords_match(self):
        if self.new_password != self.new_password_confirmation: raise ValueError("Passwords do not match")
        return self


def _limited(request: Request, scope: str, limit: int):
    try: check_rate_limit(request, scope, limit=limit, window_seconds=900)
    except LoginRateLimitError as exc: return JSONResponse(status_code=429, headers={"Retry-After": str(exc.retry_after_seconds)}, content={"code": "RATE_LIMIT_EXCEEDED", "message": "Too many requests.", "retry_after_seconds": exc.retry_after_seconds})


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    limited = _limited(request, "platform_forgot_password", 3)
    if limited: return limited
    PlatformPasswordResetService().request_reset(db, str(payload.email))
    return {"message": "If this email is registered, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    limited = _limited(request, "platform_reset_password", 5)
    if limited: return limited
    try: PlatformPasswordResetService().execute_reset(db, payload.token, payload.new_password)
    except ResetTokenExpiredError: return JSONResponse(status_code=400, content={"code": "RESET_TOKEN_EXPIRED", "message": "This reset link has expired. Please request a new one."})
    except InvalidResetTokenError: return JSONResponse(status_code=400, content={"code": "INVALID_RESET_TOKEN", "message": "This reset link is invalid or has expired. Please request a new one."})
    except PasswordTooWeakError as exc: return JSONResponse(status_code=400, content={"code": "PASSWORD_TOO_WEAK", "message": str(exc)})
    return {"message": "Password has been reset successfully. You can now log in."}
