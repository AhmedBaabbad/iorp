"""Shared pytest fixtures for the IORP backend test suite.

All tests use an isolated SQLite in-memory database — no running PostgreSQL
required.  Each test function receives a fresh database (function-scoped
engine + create_all), giving complete isolation between tests.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

# Import all model modules so Base.metadata knows every table before create_all.
import app.commercial.infrastructure.models  # noqa: F401
import app.foundation.infrastructure.models  # noqa: F401
from app.core.db import Base
from app.core.security import hash_password
from app.dependencies import get_db
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, User
from app.main import app


# ── Database / session ────────────────────────────────────────────────────────

@pytest.fixture
def db():
    """Fresh SQLite in-memory database for a single test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# ── FastAPI test client ───────────────────────────────────────────────────────

@pytest.fixture
def client(db):
    """TestClient wired to the in-memory test database via DI override."""
    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


# ── Seed helpers ──────────────────────────────────────────────────────────────

@pytest.fixture
def test_org(db):
    """One active organization, committed to the test DB."""
    org = Organization(
        name="Test Org",
        code="test-org",
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@pytest.fixture
def test_user(db, test_org):
    """One active user in test_org, password is 'Test1234!'."""
    user = User(
        organization_id=test_org.id,
        full_name="Test User",
        email="test@example.com",
        password_hash=hash_password("Test1234!"),
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(client, test_user):
    """Bearer headers for test_user, obtained via the login endpoint."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "Test1234!"},
    )
    assert resp.status_code == 200, f"Login failed during fixture setup: {resp.json()}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
