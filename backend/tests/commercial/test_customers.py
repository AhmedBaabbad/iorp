"""Baseline commercial customers tests.

Covers:
  - Create customer returns 201 with correct shape
  - List customers returns empty list when none exist
  - List customers returns created customers
  - Customer codes are generated sequentially by the backend
  - Tenant isolation: org B cannot see org A's customers
"""

from app.core.security import hash_password
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, User

_BASE_CUSTOMER = {"name": "Test Corp"}


# ── Create ────────────────────────────────────────────────────────────────────

def test_create_customer(client, auth_headers):
    resp = client.post(
        "/api/v1/commercial/customers",
        json=_BASE_CUSTOMER,
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["customer_code"] == "CUST-00001"
    assert data["name"] == "Test Corp"
    assert data["status"] == "active"
    assert data["relationship_stage"] == "lead"
    assert data["priority_level"] == "medium"
    assert "id" in data


def test_create_customer_requires_auth(client):
    resp = client.post("/api/v1/commercial/customers", json=_BASE_CUSTOMER)
    assert resp.status_code == 401


# ── List ──────────────────────────────────────────────────────────────────────

def test_list_customers_empty(client, auth_headers):
    resp = client.get("/api/v1/commercial/customers", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_customers(client, auth_headers):
    client.post("/api/v1/commercial/customers", json=_BASE_CUSTOMER, headers=auth_headers)
    resp = client.get("/api/v1/commercial/customers", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["customer_code"] == "CUST-00001"


# ── Validation ────────────────────────────────────────────────────────────────

def test_customer_codes_are_generated_sequentially(client, auth_headers):
    client.post("/api/v1/commercial/customers", json=_BASE_CUSTOMER, headers=auth_headers)
    resp = client.post(
        "/api/v1/commercial/customers",
        json={"name": "Second Corp"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["customer_code"] == "CUST-00002"


def test_customer_code_not_reused_after_delete(client, auth_headers):
    created = client.post(
        "/api/v1/commercial/customers",
        json=_BASE_CUSTOMER,
        headers=auth_headers,
    )
    assert created.status_code == 201
    customer_id = created.json()["id"]

    delete_resp = client.delete(
        f"/api/v1/commercial/customers/{customer_id}",
        headers=auth_headers,
    )
    assert delete_resp.status_code == 200

    recreated = client.post(
        "/api/v1/commercial/customers",
        json={"name": "Replacement Corp"},
        headers=auth_headers,
    )
    assert recreated.status_code == 201
    assert recreated.json()["customer_code"] == "CUST-00002"


# ── Tenant isolation ──────────────────────────────────────────────────────────

def test_tenant_isolation(client, db, test_org, auth_headers):
    """Customers created by org A must not appear in org B's list."""
    # Org A creates a customer
    client.post(
        "/api/v1/commercial/customers",
        json={"name": "Org A Customer"},
        headers=auth_headers,
    )

    # Create org B with its own user
    org_b = Organization(
        name="Other Org",
        code="other-org",
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
    )
    db.add(org_b)
    db.commit()
    db.refresh(org_b)

    user_b = User(
        organization_id=org_b.id,
        full_name="Other User",
        email="other@example.com",
        password_hash=hash_password("Other1234!"),
        status=UserStatus.ACTIVE,
    )
    db.add(user_b)
    db.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "other@example.com", "password": "Other1234!"},
    )
    assert login_resp.status_code == 200
    headers_b = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    list_resp = client.get("/api/v1/commercial/customers", headers=headers_b)
    assert list_resp.status_code == 200
    assert list_resp.json() == [], "Org B must not see org A's customers."
