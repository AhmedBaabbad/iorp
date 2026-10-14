import pytest
from app.core.storage import LocalFileStorage
from app.foundation.infrastructure.models import UserRole
from app.foundation.infrastructure.organization_queries import FoundationOrganizationQueries


def grant_commercial_role(db, org, user, role_code="commercial_manager"):
    """Grant a user the commercial_manager role (commercial:*) via the same seeding
    path real organizations use. Commercial routes enforce permissions, so any user
    created directly in a test (including a second "other org" user) needs a role."""
    provider = FoundationOrganizationQueries(db, LocalFileStorage("uploads"))
    roles = provider._seed_roles(org, provider._get_or_create_permissions(org.id))
    db.add(UserRole(user_id=user.id, role_id=roles[role_code].id))
    db.commit()


@pytest.fixture
def auth_headers(client, db, test_org, test_user):
    """The shared test_user carries no role; these suites exercise a commercial manager."""
    grant_commercial_role(db, test_org, test_user)
    resp = client.post("/api/v1/auth/login", json={"email": "test@example.com", "password": "Test1234!"})
    assert resp.status_code == 200, f"Login failed during fixture setup: {resp.json()}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def approver_headers(client, db, test_org):
    """Another commercial manager: who prepared a sales order does not confirm it (PROJECT-GOV-004)."""
    from app.core.security import hash_password
    from app.foundation.domain.enums import UserStatus
    from app.foundation.infrastructure.models import User
    approver = User(organization_id=test_org.id, full_name="Confirming Manager", email="confirming-manager@example.com",
                    password_hash=hash_password("Approver123!"), status=UserStatus.ACTIVE)
    db.add(approver); db.commit()
    grant_commercial_role(db, test_org, approver)
    resp = client.post("/api/v1/auth/login", json={"email": "confirming-manager@example.com", "password": "Approver123!"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def with_owner(test_user):
    """Customers require a Sales Owner; the commercial-manager test user is an eligible one."""
    return lambda body: {**body, "sales_owner_user_id": str(test_user.id)}
