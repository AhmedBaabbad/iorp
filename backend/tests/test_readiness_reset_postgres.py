"""Disposable PostgreSQL schema; verifies a reset token cannot win twice."""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
from datetime import timedelta
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from app.core.db import Base, engine
from app.core.utils import utc_now
from app.core.token_utils import hash_token
from app.foundation.infrastructure.models import Organization, User, TenantPasswordResetToken
from app.platform.infrastructure.models import PlatformAccount, PlatformPasswordResetToken

pytestmark = pytest.mark.skipif(os.environ.get('RUN_POSTGRES_TESTS') != '1', reason='Opt-in isolated PostgreSQL test')


@pytest.mark.parametrize('kind', ['tenant', 'platform'])
def test_concurrent_reset_is_single_use(kind):
    from app.foundation.application.password_reset import TenantPasswordResetService, InvalidResetTokenError as TenantError
    from app.platform.application.password_reset import PlatformPasswordResetService, InvalidResetTokenError as PlatformError
    name = 'test_readiness_' + uuid4().hex
    with engine.begin() as c: c.execute(sa.text(f'CREATE SCHEMA "{name}"'))
    isolated = sa.create_engine(engine.url, connect_args={'options': f'-csearch_path={name}', 'connect_timeout': 5})
    try:
        Base.metadata.create_all(isolated)
        with Session(isolated) as db:
            org = Organization(name='Reset concurrency', code='reset', timezone='UTC')
            db.add(org); db.flush()
            model = User if kind == 'tenant' else PlatformAccount
            account = model(full_name='Reset', email='reset@example.invalid', password_hash='unused', **({'organization_id': org.id} if kind == 'tenant' else {}))
            db.add(account); db.flush()
            raw = 'synthetic-test-token-' + uuid4().hex
            values = dict(token_hash=hash_token(raw), expires_at=utc_now() + timedelta(minutes=5))
            token = TenantPasswordResetToken(user_id=account.id, organization_id=org.id, **values) if kind == 'tenant' else PlatformPasswordResetToken(account_id=account.id, **values)
            db.add(token); db.commit()
            account_id, version = account.id, account.token_version
        barrier = Barrier(2)
        def reset(_):
            with Session(isolated) as db:
                barrier.wait(timeout=10)
                try:
                    (TenantPasswordResetService() if kind == 'tenant' else PlatformPasswordResetService()).execute_reset(db, raw, 'StrongReset123!')
                    return 'success'
                except (TenantError, PlatformError):
                    db.rollback()
                    return 'rejected'
        with ThreadPoolExecutor(max_workers=2) as pool: outcomes = list(pool.map(reset, range(2)))
        assert sorted(outcomes) == ['rejected', 'success']
        with Session(isolated) as db: assert db.get(model, account_id).token_version == version + 1
    finally:
        isolated.dispose()
        with engine.begin() as c: c.execute(sa.text(f'DROP SCHEMA "{name}" CASCADE'))
