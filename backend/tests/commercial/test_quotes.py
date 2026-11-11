import re
from copy import deepcopy
from uuid import uuid4

import pytest

from app.core.security import hash_password
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, User
from tests.commercial.conftest import grant_commercial_role

_BASE_CUSTOMER = {"customer_code": "CUST-QUOTE-001", "name": "Quote Corp"}

_BASE_QUOTE = {
    "quote_number": "Q-001",
    "issue_date": "2026-06-09T10:00:00Z",
    "valid_until": "2026-06-19T10:00:00Z",
    "currency": "SAR",
    "discount_amount": "0.00",
    "tax_amount": "0.00",
    "items": [
        {
            "line_no": 1,
            "product_type": "Steel Rod",
            "quantity": "100.00",
            "unit": "kg",
            "unit_price": "5.00",
        }
    ],
}


@pytest.fixture
def customer_id(client, auth_headers, with_owner):
    resp = client.post(
        "/api/v1/commercial/customers",
        json=with_owner(_BASE_CUSTOMER),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _quote_payload(**overrides):
    payload = deepcopy(_BASE_QUOTE)
    payload.update(overrides)
    return payload


def test_create_quote_returns_201(client, auth_headers, customer_id):
    resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/quotes",
        json=_quote_payload(),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert re.match(r"^QT-\d{4}-\d{4}$", data["quote_number"])  # server-generated; client value ignored
    assert data["status"] == "draft"
    assert "subtotal_amount" in data
    assert "total_amount" in data
    assert len(data["items"]) == 1


def test_create_quote_status_is_server_set(client, auth_headers, customer_id):
    resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/quotes",
        json=_quote_payload(status="accepted"),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "draft"


def test_create_quote_totals_calculated_correctly(client, auth_headers, customer_id):
    resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/quotes",
        json=_quote_payload(),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["subtotal_amount"] == "500.00"
    assert data["total_amount"] == "500.00"


def test_client_quote_number_is_ignored_and_numbers_stay_unique(client, auth_headers, customer_id):
    first = client.post(
        f"/api/v1/commercial/customers/{customer_id}/quotes",
        json=_quote_payload(),
        headers=auth_headers,
    )
    assert first.status_code == 201

    resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/quotes",
        json=_quote_payload(),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["quote_number"] != first.json()["quote_number"]


def test_create_quote_customer_not_found_returns_404(client, auth_headers):
    resp = client.post(
        f"/api/v1/commercial/customers/{uuid4()}/quotes",
        json=_quote_payload(),
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_list_quotes_returns_results(client, auth_headers, customer_id):
    create_resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/quotes",
        json=_quote_payload(),
        headers=auth_headers,
    )
    assert create_resp.status_code == 201

    resp = client.get("/api/v1/commercial/quotes", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert re.match(r"^QT-\d{4}-\d{4}$", items[0]["quote_number"])
    assert "items" not in items[0]


def test_get_quote_returns_items(client, auth_headers, customer_id):
    create_resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/quotes",
        json=_quote_payload(),
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    quote_id = create_resp.json()["id"]

    resp = client.get(f"/api/v1/commercial/quotes/{quote_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == quote_id
    assert len(data["items"]) == 1


def test_get_quote_not_found_returns_404(client, auth_headers):
    resp = client.get(f"/api/v1/commercial/quotes/{uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


def test_update_quote_status(client, auth_headers, customer_id):
    create_resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/quotes",
        json=_quote_payload(),
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    quote_id = create_resp.json()["id"]

    resp = client.post(f"/api/v1/commercial/quotes/{quote_id}/issue", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "issued"


def test_tenant_isolation(client, db, auth_headers, customer_id):
    create_resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/quotes",
        json=_quote_payload(),
        headers=auth_headers,
    )
    assert create_resp.status_code == 201

    org_b = Organization(
        name="Other Quote Org",
        code="other-quote-org",
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
    )
    db.add(org_b)
    db.commit()
    db.refresh(org_b)

    user_b = User(
        organization_id=org_b.id,
        full_name="Other Quote User",
        email="other-quote@example.com",
        password_hash=hash_password("Other1234!"),
        status=UserStatus.ACTIVE,
    )
    db.add(user_b)
    db.commit()
    grant_commercial_role(db, org_b, user_b)

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "other-quote@example.com", "password": "Other1234!"},
    )
    assert login_resp.status_code == 200
    headers_b = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    resp = client.get("/api/v1/commercial/quotes", headers=headers_b)
    assert resp.status_code == 200
    assert resp.json()["items"] == []
