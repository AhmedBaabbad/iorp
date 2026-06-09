"""Commercial samples API tests.

Covers:
  - POST /customers/{id}/samples  — create, auth required, unknown customer,
                                    duplicate code, server-set status
  - GET  /samples                 — list all, empty
  - GET  /customers/{id}/samples  — list for customer, unknown customer
  - GET  /samples/{id}            — get by ID, not found
  - PATCH /samples/{id}           — update notes, update status, not found,
                                    duplicate code rejected
  - Tenant isolation: org B cannot see org A's samples
"""

from uuid import uuid4

import pytest

from app.core.security import hash_password
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, User

_BASE_CUSTOMER = {"customer_code": "CUST-001", "name": "Test Corp"}

_BASE_SAMPLE = {
    "sample_code": "SAMP-001",
    "product_type": "Industrial Adhesive",
    "request_date": "2026-01-15T10:00:00+00:00",
}


# ── Shared fixture ────────────────────────────────────────────────────────────

@pytest.fixture
def customer_id(client, auth_headers):
    """Create a customer and return its ID string."""
    resp = client.post(
        "/api/v1/commercial/customers",
        json=_BASE_CUSTOMER,
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ── Create ────────────────────────────────────────────────────────────────────

def test_create_sample(client, auth_headers, customer_id):
    resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/samples",
        json=_BASE_SAMPLE,
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["sample_code"] == "SAMP-001"
    assert data["product_type"] == "Industrial Adhesive"
    assert data["status"] == "requested"
    assert data["customer_id"] == customer_id
    assert "id" in data
    assert "created_by_user_id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_sample_requires_auth(client, customer_id):
    resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/samples",
        json=_BASE_SAMPLE,
    )
    assert resp.status_code == 401


def test_create_sample_unknown_customer(client, auth_headers):
    resp = client.post(
        f"/api/v1/commercial/customers/{uuid4()}/samples",
        json=_BASE_SAMPLE,
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_create_sample_duplicate_code_rejected(client, auth_headers, customer_id):
    client.post(
        f"/api/v1/commercial/customers/{customer_id}/samples",
        json=_BASE_SAMPLE,
        headers=auth_headers,
    )
    resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/samples",
        json=_BASE_SAMPLE,
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_create_sample_status_is_server_set(client, auth_headers, customer_id):
    """Client-supplied status must be ignored; server always sets 'requested'."""
    payload = {**_BASE_SAMPLE, "status": "evaluated"}
    resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/samples",
        json=payload,
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "requested"


# ── List all ──────────────────────────────────────────────────────────────────

def test_list_samples_empty(client, auth_headers):
    resp = client.get("/api/v1/commercial/samples", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_samples(client, auth_headers, customer_id):
    client.post(
        f"/api/v1/commercial/customers/{customer_id}/samples",
        json=_BASE_SAMPLE,
        headers=auth_headers,
    )
    resp = client.get("/api/v1/commercial/samples", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["sample_code"] == "SAMP-001"


# ── List for customer ─────────────────────────────────────────────────────────

def test_list_samples_for_customer(client, auth_headers, customer_id):
    client.post(
        f"/api/v1/commercial/customers/{customer_id}/samples",
        json=_BASE_SAMPLE,
        headers=auth_headers,
    )
    resp = client.get(
        f"/api/v1/commercial/customers/{customer_id}/samples",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["customer_id"] == customer_id


def test_list_samples_for_unknown_customer(client, auth_headers):
    resp = client.get(
        f"/api/v1/commercial/customers/{uuid4()}/samples",
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ── Get by ID ─────────────────────────────────────────────────────────────────

def test_get_sample(client, auth_headers, customer_id):
    create_resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/samples",
        json=_BASE_SAMPLE,
        headers=auth_headers,
    )
    sample_id = create_resp.json()["id"]

    resp = client.get(
        f"/api/v1/commercial/samples/{sample_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == sample_id
    assert data["sample_code"] == "SAMP-001"
    assert data["status"] == "requested"


def test_get_sample_not_found(client, auth_headers):
    resp = client.get(
        f"/api/v1/commercial/samples/{uuid4()}",
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ── Update (PATCH) ────────────────────────────────────────────────────────────

def test_update_sample_notes(client, auth_headers, customer_id):
    create_resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/samples",
        json=_BASE_SAMPLE,
        headers=auth_headers,
    )
    sample_id = create_resp.json()["id"]

    resp = client.patch(
        f"/api/v1/commercial/samples/{sample_id}",
        json={"notes": "Updated note"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["notes"] == "Updated note"
    assert data["sample_code"] == "SAMP-001"


def test_update_sample_status(client, auth_headers, customer_id):
    create_resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/samples",
        json=_BASE_SAMPLE,
        headers=auth_headers,
    )
    sample_id = create_resp.json()["id"]

    resp = client.patch(
        f"/api/v1/commercial/samples/{sample_id}",
        json={"status": "in_preparation"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_preparation"


def test_update_sample_not_found(client, auth_headers):
    resp = client.patch(
        f"/api/v1/commercial/samples/{uuid4()}",
        json={"notes": "ghost update"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_update_sample_duplicate_code_rejected(client, auth_headers, customer_id):
    """Renaming sample B's code to match sample A must be rejected with 400."""
    client.post(
        f"/api/v1/commercial/customers/{customer_id}/samples",
        json=_BASE_SAMPLE,
        headers=auth_headers,
    )
    create_b = client.post(
        f"/api/v1/commercial/customers/{customer_id}/samples",
        json={**_BASE_SAMPLE, "sample_code": "SAMP-002"},
        headers=auth_headers,
    )
    sample_b_id = create_b.json()["id"]

    resp = client.patch(
        f"/api/v1/commercial/samples/{sample_b_id}",
        json={"sample_code": "SAMP-001"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


# ── Tenant isolation ──────────────────────────────────────────────────────────

def test_tenant_isolation(client, db, auth_headers, customer_id):
    """Samples created by org A must not appear in org B's list."""
    client.post(
        f"/api/v1/commercial/customers/{customer_id}/samples",
        json=_BASE_SAMPLE,
        headers=auth_headers,
    )

    org_b = Organization(
        name="Other Org",
        code="other-org-samples",
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
    )
    db.add(org_b)
    db.commit()
    db.refresh(org_b)

    user_b = User(
        organization_id=org_b.id,
        full_name="Other User",
        email="other-samples@example.com",
        password_hash=hash_password("Other1234!"),
        status=UserStatus.ACTIVE,
    )
    db.add(user_b)
    db.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "other-samples@example.com", "password": "Other1234!"},
    )
    assert login_resp.status_code == 200
    headers_b = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    list_resp = client.get("/api/v1/commercial/samples", headers=headers_b)
    assert list_resp.status_code == 200
    assert list_resp.json() == [], "Org B must not see org A's samples."
