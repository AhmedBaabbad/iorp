import secrets
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session
import pyotp
from app.core.config import settings
from app.core.security import decode_token
from app.dependencies import get_current_platform_account, get_db
from app.platform.infrastructure.models import PlatformAccount
from app.platform.infrastructure.mfa_models import PlatformMFA, PlatformStepUp
from app.platform.application import mfa

router = APIRouter(prefix='/platform/mfa', tags=['platform-security'])


def throttle(request):
    from app.core.rate_limit import check_rate_limit, LoginRateLimitError
    try:
        check_rate_limit(request, 'platform_mfa', limit=10)
    except LoginRateLimitError as exc:
        raise HTTPException(429, detail={'code': 'RATE_LIMIT_EXCEEDED'}, headers={'Retry-After': str(exc.retry_after_seconds)}) from None


class Verify(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    code: str = Field(default='', max_length=128)


class Confirm(BaseModel):
    code: str = Field(min_length=6, max_length=32)
    saved_recovery_codes: bool


class Step(Verify):
    method: str = Field(pattern='^(POST|PUT|PATCH|DELETE)$')
    path: str = Field(min_length=1, max_length=250)
    body: dict | None = None


def sid(request):
    return decode_token(request.headers.get('authorization', '').removeprefix('Bearer '), 'access')['sid']


@router.get('')
def status(account: PlatformAccount = Depends(get_current_platform_account), db: Session = Depends(get_db)):
    row = db.get(PlatformMFA, account.id)
    return {'enabled': bool(row and row.enabled), 'required': settings.platform_mfa_required,
            'recovery_remaining': len(row.recovery_hashes) if row and row.enabled else 0}


@router.post('/enroll')
def enroll(payload: Verify, request: Request, response: Response, account: PlatformAccount = Depends(get_current_platform_account), db: Session = Depends(get_db)):
    throttle(request)
    mfa.verify_identity(db, account, payload.password, payload.code)
    row = mfa.factor(db, account)
    if row and row.enabled: raise HTTPException(409, detail={'code': 'MFA_ALREADY_ENABLED'})
    secret = pyotp.random_base32()
    encrypted = mfa.cipher().encrypt(secret.encode()).decode()
    codes, hashes = mfa.recovery_codes()
    if row is None:
        row = PlatformMFA(account_id=account.id)
        db.add(row)
    row.secret, row.enabled, row.expires_at = encrypted, False, mfa.now() + timedelta(minutes=10)
    row.recovery_hashes, row.last_counter, row.failures, row.blocked_until = hashes, -1, 0, None
    mfa.audit(db, account, 'platform_mfa_enrollment_started')
    db.commit()
    response.headers['Cache-Control'] = 'no-store'
    return {'secret': secret, 'uri': pyotp.TOTP(secret).provisioning_uri(account.email, issuer_name='IORP Platform'), 'recovery_codes': codes}


@router.post('/confirm')
def confirm(payload: Confirm, request: Request, account: PlatformAccount = Depends(get_current_platform_account), db: Session = Depends(get_db)):
    throttle(request)
    row = mfa.factor(db, account)
    if not payload.saved_recovery_codes or not row or row.enabled: raise HTTPException(400, detail={'code': 'ENROLLMENT_INVALID'})
    row = mfa.verify_factor(db, account, payload.code, pending=True)
    row.enabled = True
    mfa.invalidate(db, account)
    mfa.audit(db, account, 'platform_mfa_enabled')
    db.commit()
    return {'login_required': True}


@router.post('/step-up')
def step_up(payload: Step, request: Request, response: Response, account: PlatformAccount = Depends(get_current_platform_account), db: Session = Depends(get_db)):
    throttle(request)
    if not payload.path.startswith('/platform/') or '?' in payload.path:
        raise HTTPException(400, detail={'code': 'INVALID_ACTION'})
    mfa.verify_identity(db, account, payload.password, payload.code)
    raw = secrets.token_urlsafe(32)
    db.add(PlatformStepUp(token_hash=mfa.digest(raw), account_id=account.id, session_id=sid(request),
        binding=mfa.binding(payload.method, payload.path, payload.body), expires_at=mfa.now() + timedelta(minutes=2), used=False))
    mfa.audit(db, account, 'platform_step_up_verified')
    db.commit()
    response.headers['Cache-Control'] = 'no-store'
    return {'authorization': raw, 'expires_in': 120}


async def require_step_up(request: Request, account: PlatformAccount = Depends(get_current_platform_account), db: Session = Depends(get_db)):
    if request.method in {'GET', 'HEAD', 'OPTIONS'}: return
    path = request.url.path.removeprefix(settings.api_prefix)
    body = await request.body()
    try:
        data = await request.json() if body else None
    except ValueError:
        raise HTTPException(400, detail={'code': 'INVALID_REQUEST'}) from None
    raw = request.headers.get('X-Platform-Step-Up', '')
    result = db.execute(update(PlatformStepUp).where(
        PlatformStepUp.token_hash == mfa.digest(raw), PlatformStepUp.account_id == account.id,
        PlatformStepUp.session_id == sid(request), PlatformStepUp.binding == mfa.binding(request.method, path, data),
        PlatformStepUp.expires_at > mfa.now(), PlatformStepUp.used.is_(False)).values(used=True))
    if result.rowcount != 1:
        db.rollback()
        mfa.audit(db, account, 'platform_step_up_denied', 'denied')
        db.commit()
        raise HTTPException(403, detail={'code': 'STEP_UP_REQUIRED'})
    db.commit()  # fail closed: one attempted action, even when the action subsequently fails


@router.post('/disable', dependencies=[Depends(require_step_up)])
def disable(account: PlatformAccount = Depends(get_current_platform_account), db: Session = Depends(get_db)):
    row = mfa.factor(db, account)
    if row: db.delete(row)
    mfa.invalidate(db, account)
    mfa.audit(db, account, 'platform_mfa_disabled')
    db.commit()
    return {'login_required': True}


@router.post('/recovery', dependencies=[Depends(require_step_up)])
def recovery(response: Response, account: PlatformAccount = Depends(get_current_platform_account), db: Session = Depends(get_db)):
    row = mfa.factor(db, account)
    if not row or not row.enabled: raise HTTPException(409, detail={'code': 'MFA_NOT_ENABLED'})
    codes, row.recovery_hashes = mfa.recovery_codes()
    mfa.invalidate(db, account)
    mfa.audit(db, account, 'platform_recovery_codes_replaced')
    db.commit()
    response.headers['Cache-Control'] = 'no-store'
    return {'recovery_codes': codes, 'login_required': True}
