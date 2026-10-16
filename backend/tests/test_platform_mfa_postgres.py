"""Opt-in: real PostgreSQL row locks prevent concurrent reuse of the same factor."""
import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from datetime import timedelta
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet
from fastapi import HTTPException
import pyotp
from app.core.db import Base, engine
from app.core.config import settings
from app.platform.application import mfa
from app.platform.infrastructure.models import PlatformAccount
from app.platform.infrastructure.mfa_models import PlatformMFA
from app.main import app

pytestmark = pytest.mark.skipif(os.environ.get('RUN_POSTGRES_TESTS') != '1', reason='Disposable PostgreSQL opt-in')


@pytest.mark.parametrize('recovery', [False, True])
def test_concurrent_factor_replay_is_rejected(monkeypatch, recovery):
    fixed_now = mfa.now()
    monkeypatch.setattr(mfa, 'now', lambda: fixed_now)
    schema='test_mfa_'+uuid4().hex
    monkeypatch.setattr(settings,'platform_mfa_keys',Fernet.generate_key().decode())
    with engine.begin() as c: c.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    isolated=sa.create_engine(engine.url,connect_args={'options':f'-csearch_path={schema}'})
    try:
        Base.metadata.create_all(isolated)
        account_id=uuid4(); secret=pyotp.random_base32();code='synthetic-recovery-code' if recovery else pyotp.TOTP(secret).at(fixed_now)
        with Session(isolated) as db:
            db.add(PlatformAccount(id=account_id,email='isolated@example.test',full_name='Isolated',password_hash='unused',status='active',role='root',is_root=True,token_version=0))
            db.flush()
            db.add(PlatformMFA(account_id=account_id,secret=mfa.cipher().encrypt(secret.encode()).decode(),enabled=True,
                expires_at=mfa.now()+timedelta(minutes=5),last_counter=-1,recovery_hashes=[mfa.digest(code)] if recovery else []))
            db.commit()
        def attempt(_):
            with Session(isolated) as db:
                try:
                    mfa.verify_factor(db,db.get(PlatformAccount,account_id),code)
                    return 'accepted'
                except HTTPException:
                    return 'rejected'
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(attempt,range(2))) == ['accepted','rejected']
    finally:
        isolated.dispose()
        with engine.begin() as c: c.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
