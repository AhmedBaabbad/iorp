"""No factor or grant plaintext is persisted or included in audit details."""
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet, MultiFernet, InvalidToken
import pyotp
from fastapi import HTTPException
from sqlalchemy import select, update
from app.core.config import settings
from app.core.audit import AuditActor, PlatformAuditService
from app.core.security import verify_password, revoke_account_sessions
from app.platform.infrastructure.mfa_models import PlatformMFA, PlatformStepUp


def now():
    return datetime.now(timezone.utc)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def cipher():
    try:
        keys = [Fernet(k.strip()) for k in settings.platform_mfa_keys.split(',') if k.strip()]
        if not keys: raise ValueError()
        return MultiFernet(keys)
    except (ValueError, TypeError):
        raise HTTPException(503, detail={'code': 'MFA_UNAVAILABLE'}) from None


def audit(db, account, action, outcome='success'):
    PlatformAuditService(db).record(event_type=action, category='identity', outcome=outcome,
        actor=AuditActor('platform', account.id, account.email, account.full_name),
        target_type='platform_account', target_id=account.id)


def factor(db, account):
    return db.scalar(select(PlatformMFA).where(PlatformMFA.account_id == account.id).with_for_update())


def reject(db, account, row):
    if row:
        row.failures += 1
        if row.failures >= 5: row.blocked_until = now() + timedelta(minutes=15)
    audit(db, account, 'platform_mfa_verification_failed', 'failure')
    db.commit()
    raise HTTPException(400, detail={'code': 'VERIFICATION_FAILED'})


def verify_factor(db, account, code, *, pending=False):
    code = code.strip()
    row = factor(db, account)
    if not row or (not pending and not row.enabled) or (pending and row.expires_at <= now()):
        reject(db, account, row)
    if row.blocked_until and row.blocked_until > now():
        raise HTTPException(429, detail={'code': 'VERIFICATION_LOCKED'})
    if row.blocked_until:
        row.failures = 0
        row.blocked_until = None
    if not code.isascii(): reject(db, account, row)
    # High-entropy recovery tokens need no reversible encryption or slow password KDF.
    hashed = digest(code)
    if not pending and hashed in row.recovery_hashes:
        row.recovery_hashes = [h for h in row.recovery_hashes if h != hashed]
        row.failures = 0
        audit(db, account, 'platform_recovery_code_used')
        db.commit()  # consume even if subsequent operation fails
        return row
    try:
        secret = cipher().decrypt(row.secret.encode()).decode()
    except InvalidToken:
        raise HTTPException(503, detail={'code': 'MFA_UNAVAILABLE'}) from None
    totp = pyotp.TOTP(secret)
    counter = int(now().timestamp()) // 30
    for accepted in range(counter - 1, counter + 2):
        if accepted > row.last_counter and secrets.compare_digest(totp.at(accepted * 30), code):
            row.last_counter = accepted
            row.failures = 0
            db.commit()  # durable replay prevention independently of the business transaction
            return row
    reject(db, account, row)


def verify_identity(db, account, password, code):
    row = factor(db, account)
    if not verify_password(password, account.password_hash): reject(db, account, row)
    if row and row.enabled: verify_factor(db, account, code)


def recovery_codes():
    codes = [secrets.token_hex(16) for _ in range(10)]
    return codes, [digest(c) for c in codes]


def invalidate(db, account):
    account.token_version += 1
    revoke_account_sessions(db, 'platform', account.id, reason='mfa_changed')
    db.execute(update(PlatformStepUp).where(PlatformStepUp.account_id == account.id).values(used=True))


def binding(method, path, body):
    return digest(json.dumps([method.upper(), path, body], sort_keys=True, separators=(',', ':'), ensure_ascii=True))
