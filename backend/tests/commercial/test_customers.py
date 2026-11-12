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
from tests.commercial.conftest import grant_commercial_role

_BASE_CUSTOMER = {"name": "Test Corp"}


# ── Create ────────────────────────────────────────────────────────────────────

def test_create_customer(client, auth_headers, with_owner):
    resp = client.post(
        "/api/v1/commercial/customers",
        json=with_owner(_BASE_CUSTOMER),
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
    assert resp.json() == {"items": [], "total": 0, "page": 1, "page_size": 50, "pages": 0}


def test_list_customers(client, auth_headers, with_owner):
    client.post("/api/v1/commercial/customers", json=with_owner(_BASE_CUSTOMER), headers=auth_headers)
    resp = client.get("/api/v1/commercial/customers", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["customer_code"] == "CUST-00001"


# ── Validation ────────────────────────────────────────────────────────────────

def test_customer_codes_are_generated_sequentially(client, auth_headers, with_owner):
    client.post("/api/v1/commercial/customers", json=with_owner(_BASE_CUSTOMER), headers=auth_headers)
    resp = client.post(
        "/api/v1/commercial/customers",
        json=with_owner({"name": "Second Corp"}),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["customer_code"] == "CUST-00002"


def test_customer_code_not_reused_after_delete(client, auth_headers, with_owner):
    created = client.post(
        "/api/v1/commercial/customers",
        json=with_owner(_BASE_CUSTOMER),
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
        json=with_owner({"name": "Replacement Corp"}),
        headers=auth_headers,
    )
    assert recreated.status_code == 201
    assert recreated.json()["customer_code"] == "CUST-00002"


# ── Tenant isolation ──────────────────────────────────────────────────────────

def test_tenant_isolation(client, db, test_org, auth_headers, with_owner):
    """Customers created by org A must not appear in org B's list."""
    # Org A creates a customer
    client.post(
        "/api/v1/commercial/customers",
        json=with_owner({"name": "Org A Customer"}),
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
    grant_commercial_role(db, org_b, user_b)

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "other@example.com", "password": "Other1234!"},
    )
    assert login_resp.status_code == 200
    headers_b = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    list_resp = client.get("/api/v1/commercial/customers", headers=headers_b)
    assert list_resp.status_code == 200
    assert list_resp.json()["items"] == [], "Org B must not see org A's customers."


# ── Pagination, search and lookup (ARCH-PAGE-001) ─────────────────────────────

def test_customers_come_in_pages_newest_first_without_overlap(client, auth_headers, with_owner):
    for n in range(7):
        client.post("/api/v1/commercial/customers", json=with_owner({**_BASE_CUSTOMER, "name": f"Client {n}"}), headers=auth_headers)
    first = client.get("/api/v1/commercial/customers?page=1&page_size=3", headers=auth_headers).json()
    assert (first["total"], first["page"], first["page_size"], first["pages"]) == (7, 1, 3, 3)
    assert [c["name"] for c in first["items"]] == ["Client 6", "Client 5", "Client 4"]
    seen = [c["id"] for p in (1, 2, 3) for c in
            client.get(f"/api/v1/commercial/customers?page={p}&page_size=3", headers=auth_headers).json()["items"]]
    assert len(seen) == len(set(seen)) == 7
    assert client.get("/api/v1/commercial/customers?page=9&page_size=3", headers=auth_headers).json()["items"] == []
    assert client.get("/api/v1/commercial/customers?page_size=101", headers=auth_headers).status_code == 422
    assert client.get("/api/v1/commercial/customers?page=0", headers=auth_headers).status_code == 422


def test_customers_are_searched_and_filtered_by_the_server(client, auth_headers, with_owner):
    client.post("/api/v1/commercial/customers", json=with_owner({**_BASE_CUSTOMER, "name": "Gulf Packaging", "primary_contact": {"name": "Main contact", "phone": "0551234567"}}), headers=auth_headers)
    client.post("/api/v1/commercial/customers", json=with_owner({**_BASE_CUSTOMER, "name": "Red Sea Foods", "status": "inactive"}), headers=auth_headers)
    names = lambda q: [c["name"] for c in client.get(f"/api/v1/commercial/customers?{q}", headers=auth_headers).json()["items"]]
    assert names("search=gulf") == ["Gulf Packaging"]
    assert names("search=0551") == ["Gulf Packaging"]
    assert names("search=CUST-00002") == ["Red Sea Foods"]
    assert names("status=inactive") == ["Red Sea Foods"]
    page = client.get("/api/v1/commercial/customers?search=gulf", headers=auth_headers).json()
    assert page["total"] == 1


def test_customer_lookup_for_pickers(client, auth_headers, with_owner):
    ids = [client.post("/api/v1/commercial/customers", json=with_owner({**_BASE_CUSTOMER, "name": name}), headers=auth_headers).json()["id"]
           for name in ("Alpha Films", "Beta Bags", "Alpha Rolls")]
    found = client.get("/api/v1/commercial/customers/lookup?search=alpha", headers=auth_headers).json()
    assert [c["name"] for c in found] == ["Alpha Films", "Alpha Rolls"] and set(found[0]) == {"id", "customer_code", "name", "status"}
    named = client.get(f"/api/v1/commercial/customers/lookup?ids={ids[1]}", headers=auth_headers).json()
    assert [c["name"] for c in named] == ["Beta Bags"]
    assert len(client.get("/api/v1/commercial/customers/lookup?limit=2", headers=auth_headers).json()) == 2
