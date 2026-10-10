from uuid import uuid4

import pytest

from app.core.security import hash_password
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, User
from tests.commercial.conftest import grant_commercial_role

_BASE_CUSTOMER = {"customer_code": "CUST-EVAL-001", "name": "Evaluation Corp"}

_BASE_SAMPLE = {
    "sample_code": "SAMP-EVAL-001",
    "product_type": "steel_rod",
    "request_date": "2026-06-09T10:00:00Z",
}

_BASE_EVALUATION = {
    "evaluation_date": "2026-06-10T10:00:00Z",
    "result_status": "accepted",
    "comments": "Meets baseline requirements.",
    "next_action": "proceed_to_quote",
}


def test_evaluator_name_comes_from_authenticated_user(client, auth_headers, sample_id, test_user):
    response = client.post(f'/api/v1/commercial/samples/{sample_id}/evaluations', headers=auth_headers,
        json={**_BASE_EVALUATION, 'evaluated_by_user_id': str(uuid4()), 'evaluated_by_name': 'Forged name'})
    assert response.status_code == 201
    result = response.json()
    assert result['evaluated_by_user_id'] == str(test_user.id)
    assert result['evaluated_by_name'] == test_user.full_name
    listed = client.get(f'/api/v1/commercial/samples/{sample_id}/evaluations', headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json()[0]['evaluated_by_name'] == test_user.full_name
    detail = client.get(f"/api/v1/commercial/sample-evaluations/{result['id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()['evaluated_by_name'] == test_user.full_name


@pytest.fixture
def customer_id(client, auth_headers, with_owner):
    resp = client.post(
        "/api/v1/commercial/customers",
        json=with_owner(_BASE_CUSTOMER),
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
    grant_commercial_role(db, org_b, user_b)

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


@pytest.fixture(autouse=True)
def sample_master_product(db, test_org, test_user):
    from app.masterdata.infrastructure.models import Product
    db.add(Product(organization_id=test_org.id, code='PRD-SAMPLE', key='steel_rod',
        name_ar='Test product', name_en='Test product', created_by_user_id=test_user.id))
    db.commit()
