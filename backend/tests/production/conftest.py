import pytest
import re
from app.core.storage import LocalFileStorage
from app.foundation.infrastructure.models import UserRole
from app.foundation.infrastructure.organization_queries import FoundationOrganizationQueries


def grant_production_role(db, org, user, role_code="production_manager"):
    """Grant a user the production_manager role (production:*) in their org,
    via the same seeding path real organizations use. Production routes now
    enforce permissions, so any user created directly in a test — including
    a second "other org" user for tenant-isolation checks — needs this."""
    provider = FoundationOrganizationQueries(db, LocalFileStorage("uploads"))
    permissions = provider._get_or_create_permissions(org.id)
    roles = provider._seed_roles(org, permissions)
    db.add(UserRole(user_id=user.id, role_id=roles[role_code].id))
    db.commit()


@pytest.fixture(autouse=True)
def _grant_default_production_role(db, test_org, test_user):
    """The shared test_user fixture carries no role by default."""
    # PostgreSQL substring(text, regex) is not SQLite substring(text, offset).
    # Match production code generation semantics in this SQLite-only suite.
    def regex_substring(value, pattern):
        match = re.search(pattern, value or "")
        return match.group(1) if match else None
    db.connection().connection.driver_connection.create_function("substring", 2, regex_substring)
    grant_production_role(db, test_org, test_user)
