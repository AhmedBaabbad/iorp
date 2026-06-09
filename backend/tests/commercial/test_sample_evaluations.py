from uuid import uuid4

import pytest

from app.core.security import hash_password
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, User

_BASE_CUSTOMER = {"customer_code": "CUST-EVAL-001", "name": "Evaluation Corp"}

_BASE_SAMPLE = {
    "sample_code": "SAMP-EVAL-001",
    "product_type": "Steel Rod",
    "request_date": "2026-06-09T10:00:00Z",
}

_BASE_EVALUATION = {
    "evaluation_date": "2026-06-10T10:00:00Z",
    "result_status": "accepted",
    "comments": "Meets baseline requirements.",
    "next_action": "proceed_to_quote",
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


@pytest.fixture
def sample_id(client, auth_headers, customer_id):
    resp = client.post(
        f"/api/v1/commercial/customers/{customer_id}/samples",
        json=_BASE_SAMPLE,
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_create_evaluation_returns_201(client, auth_headers, sample_id):
    resp = client.post(
        f"/api/v1/commercial/samples/{sample_id}/evaluations",
        json=_BASE_EVALUATION,
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["sample_id"] == sample_id
    assert data["result_status"] == "accepted"
    assert data["next_action"] == "proceed_to_quote"
    assert "evaluated_by_user_id" in data


def test_create_evaluation_marks_sample_evaluated(client, auth_headers, sample_id):
    resp = client.post(
        f"/api/v1/commercial/samples/{sample_id}/evaluations",
        json=_BASE_EVALUATION,
        headers=auth_headers,
    )
    assert resp.status_code == 201

    sample_resp = client.get(
        f"/api/v1/commercial/samples/{sample_id}",
        headers=auth_headers,
    )
    assert sample_resp.status_code == 200
    assert sample_resp.json()["status"] == "evaluated"


def test_create_evaluation_sample_not_found_returns_404(client, auth_headers):
    resp = client.post(
        f"/api/v1/commercial/samples/{uuid4()}/evaluations",
        json=_BASE_EVALUATION,
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_list_evaluations_returns_results(client, auth_headers, sample_id):
    create_resp = client.post(
        f"/api/v1/commercial/samples/{sample_id}/evaluations",
        json=_BASE_EVALUATION,
        headers=auth_headers,
    )
    assert create_resp.status_code == 201

    resp = client.get(
        f"/api/v1/commercial/samples/{sample_id}/evaluations",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["sample_id"] == sample_id


def test_list_evaluations_sample_not_found_returns_404(client, auth_headers):
    resp = client.get(
        f"/api/v1/commercial/samples/{uuid4()}/evaluations",
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_get_evaluation_by_id(client, auth_headers, sample_id):
    create_resp = client.post(
        f"/api/v1/commercial/samples/{sample_id}/evaluations",
        json=_BASE_EVALUATION,
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    evaluation_id = create_resp.json()["id"]

    resp = client.get(
        f"/api/v1/commercial/sample-evaluations/{evaluation_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == evaluation_id
    assert data["sample_id"] == sample_id
    assert data["result_status"] == "accepted"
    assert data["next_action"] == "proceed_to_quote"


def test_get_evaluation_not_found_returns_404(client, auth_headers):
    resp = client.get(
        f"/api/v1/commercial/sample-evaluations/{uuid4()}",
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_tenant_isolation(client, db, auth_headers, sample_id):
    create_resp = client.post(
        f"/api/v1/commercial/samples/{sample_id}/evaluations",
        json=_BASE_EVALUATION,
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    evaluation_id = create_resp.json()["id"]

    org_b = Organization(
        name="Other Evaluation Org",
        code="other-evaluation-org",
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
    )
    db.add(org_b)
    db.commit()
    db.refresh(org_b)

    user_b = User(
        organization_id=org_b.id,
        full_name="Other Evaluation User",
        email="other-evaluation@example.com",
        password_hash=hash_password("Other1234!"),
        status=UserStatus.ACTIVE,
    )
    db.add(user_b)
    db.commit()

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "other-evaluation@example.com", "password": "Other1234!"},
    )
    assert login_resp.status_code == 200
    headers_b = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    resp = client.get(
        f"/api/v1/commercial/sample-evaluations/{evaluation_id}",
        headers=headers_b,
    )
    assert resp.status_code == 404
