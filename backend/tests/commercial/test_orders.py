from copy import deepcopy
from uuid import uuid4

import pytest

from app.core.security import hash_password
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, User

_BASE_CUSTOMER = {"customer_code": "CUST-ORDER-001", "name": "Order Corp"}

_BASE_ORDER = {
    "order_number": "ORD-001",
    "order_date": "2026-06-09T10:00:00Z",
    "items": [
        {
            "line_no": 1,
            "product_type": "Steel Rod",
            "quantity": "100.00",
            "unit": "kg",
        }
    ],
}


@pytest.fixture
def customer_id(client, auth_headers):
    resp = client.post(
        "/api/v1/commercial/customers",
        json=_BASE_CUSTOMER,
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _order_payload(**overrides):
    payload = deepcopy(_BASE_ORDER)
    payload.update(overrides)
    return payload


def test_create_order_returns_201(client, auth_headers, customer_id):
    resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/orders",
        json=_order_payload(),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["order_number"] == "ORD-001"
    assert data["status"] == "draft"
    assert len(data["items"]) == 1


def test_create_order_status_is_server_set(client, auth_headers, customer_id):
    resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/orders",
        json=_order_payload(status="confirmed"),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "draft"


def test_create_order_without_price_items_allowed(client, auth_headers, customer_id):
    resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/orders",
        json=_order_payload(),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    item = resp.json()["items"][0]
    assert item["agreed_unit_price"] is None
    assert item["line_total"] is None


def test_create_order_with_price_calculates_line_total(client, auth_headers, customer_id):
    payload = _order_payload()
    payload["items"][0]["agreed_unit_price"] = "5.00"
    resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/orders",
        json=payload,
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["items"][0]["line_total"] == "500.00"


def test_create_order_duplicate_number_returns_400(client, auth_headers, customer_id):
    first = client.post(
        f"/api/v1/commercial/customers/{customer_id}/orders",
        json=_order_payload(),
        headers=auth_headers,
    )
    assert first.status_code == 201

    resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/orders",
        json=_order_payload(),
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_create_order_customer_not_found_returns_404(client, auth_headers):
    resp = client.post(
        f"/api/v1/commercial/customers/{uuid4()}/orders",
        json=_order_payload(),
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_list_orders_returns_results(client, auth_headers, customer_id):
    create_resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/orders",
        json=_order_payload(),
        headers=auth_headers,
    )
    assert create_resp.status_code == 201

    resp = client.get("/api/v1/commercial/orders", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["order_number"] == "ORD-001"
    assert "items" not in items[0]


def test_get_order_returns_items(client, auth_headers, customer_id):
    create_resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/orders",
        json=_order_payload(),
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    order_id = create_resp.json()["id"]

    resp = client.get(f"/api/v1/commercial/orders/{order_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == order_id
    assert len(data["items"]) == 1


def test_get_order_not_found_returns_404(client, auth_headers):
    resp = client.get(f"/api/v1/commercial/orders/{uuid4()}", headers=auth_headers)
    assert resp.status_code == 404


def test_update_order_status(client, auth_headers, customer_id):
    create_resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/orders",
        json=_order_payload(),
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    order_id = create_resp.json()["id"]

    resp = client.patch(
        f"/api/v1/commercial/orders/{order_id}",
        json={"status": "confirmed"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"


def test_tenant_isolation(client, db, auth_headers, customer_id):
    create_resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/orders",
        json=_order_payload(),
        headers=auth_headers,
    )
    assert create_resp.status_code == 201

    org_b = Organization(
        name="Other Order Org",
        code="other-order-org",
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
    )
    db.add(org_b)
    db.commit()
    db.refresh(org_b)

    user_b = User(
        organization_id=org_b.id,
        full_name="Other Order User",
        email="other-order@example.com",
        password_hash=hash_password("Other1234!"),
        status=UserStatus.ACTIVE,
    )
    db.add(user_b)
    db.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "other-order@example.com", "password": "Other1234!"},
    )
    assert login_resp.status_code == 200
    headers_b = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    resp = client.get("/api/v1/commercial/orders", headers=headers_b)
    assert resp.status_code == 200
    assert resp.json() == []
