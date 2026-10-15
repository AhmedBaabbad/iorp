"""Offline break-glass recovery. Restricted server operators only; never a public API."""
import argparse
from uuid import UUID
from app.core.audit import AuditActor, PlatformAuditService
from app.platform.application.mfa import factor, invalidate
from app.platform.infrastructure.models import PlatformAccount


def recover(db, account_id, confirmed_email, reason):
    account = db.get(PlatformAccount, account_id)
    if not account or confirmed_email != account.email or len(reason.strip()) < 10:
        raise ValueError('Exact account confirmation and incident reason required')
    row = factor(db, account)
    if row: db.delete(row)
    invalidate(db, account)
    PlatformAuditService(db).record(event_type='platform_mfa_operator_recovery', category='identity',
        actor=AuditActor('system'), target_type='platform_account', target_id=account.id,
        target_display=account.email, reason=reason, changes={'mfa_enabled': {'before': bool(row and row.enabled), 'after': False}})
    db.commit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--account-id', type=UUID, required=True)
    parser.add_argument('--reason', required=True)
    args = parser.parse_args()
    confirmation = input('Confirm exact account email after offline identity verification: ').strip()
    from app.core.db import SessionLocal
    with SessionLocal() as db:
        recover(db, args.account_id, confirmation, args.reason)
    print('MFA reset and all sessions revoked. Re-enroll before privileged use when mandatory rollout is enabled.')


if __name__ == '__main__': main()
