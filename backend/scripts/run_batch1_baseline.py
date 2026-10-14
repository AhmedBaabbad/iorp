"""Reproducible isolated baseline; does not load an operational database URL."""
import os
from pathlib import Path
import subprocess
import sys

SUITES = [
    'tests/test_tenant_isolation.py', 'tests/test_batch1_isolation.py',
    'tests/test_platform_isolation.py', 'tests/test_jwt_token_architecture.py',
    'tests/test_readiness_transactions.py', 'tests/test_recovery_drill.py',
    'tests/test_file_policy.py', 'tests/test_delegations.py', 'tests/test_notifications.py',
]

if __name__ == '__main__':
    env = dict(os.environ, APP_ENV='test', DEBUG='false', EMAIL_MODE='console',
               PRODUCTION_AUTO_START_BY_DATE='false', RUN_POSTGRES_TESTS='0',
               DATABASE_URL='postgresql+psycopg://unused:unused@127.0.0.1:1/isolated_unreachable')
    raise SystemExit(subprocess.call([sys.executable, '-m', 'pytest', *SUITES, '-q', '--tb=short', '--disable-warnings'],
                                     cwd=Path(__file__).resolve().parents[1], env=env))
