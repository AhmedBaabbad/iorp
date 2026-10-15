import os
from pathlib import Path
import subprocess
import sys
import pytest
from cryptography.fernet import Fernet
from app.core.config import Settings


def test_mandatory_mfa_requires_independent_key():
    with pytest.raises(ValueError, match='requires configured'):
        Settings(_env_file=None, platform_mfa_required=True, platform_mfa_keys='')
    assert Settings(_env_file=None, platform_mfa_required=True, platform_mfa_keys=Fernet.generate_key().decode()).platform_mfa_required


@pytest.mark.parametrize('origin', ['*','http://app.example.test','https://user:password@app.example.test','https://app.example.test?x=1'])
def test_production_cors_rejects_unsafe_origins(origin):
    with pytest.raises(ValueError,match='CORS'):
        Settings(_env_file=None, app_env='production', cors_origins=origin, frontend_url='https://app.example.test',platform_frontend_url='https://app.example.test')


def test_production_docs_and_openapi_are_not_registered(tmp_path):
    env=dict(os.environ,APP_ENV='production',DEBUG='false',EMAIL_MODE='smtp',SMTP_TLS='true',SMTP_SSL='false',
        REFRESH_COOKIE_SECURE='true',SECRET_KEY='synthetic-test-key-with-at-least-32-characters',
        FRONTEND_URL='https://app.example.test',PLATFORM_FRONTEND_URL='https://app.example.test',
        CORS_ORIGINS='https://app.example.test',DATABASE_URL='postgresql+psycopg://unused:unused@127.0.0.1:1/unreachable',
        PYTHONPATH=str(Path(__file__).parents[1]))
    result=subprocess.run([sys.executable,'-c',"from app.main import app; assert app.docs_url is None and app.openapi_url is None and app.redoc_url is None"],cwd=tmp_path,env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
