"""Production work centers API tests."""

from uuid import uuid4
import re

from app.core.security import hash_password
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, User
from tests.production.conftest import grant_production_role


_BASE_WORK_CENTER = {
    "code": "EXT-01",
    "name": "Extrusion Line 1",
    "center_type": "extrusion",
    "location": "Hall A",
    "notes": "Primary extrusion work center",
}


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_other_org_headers(client, db) -> dict[str, str]:
    org = Organization(
        name="Other Org",
        code="other-org-production",
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    user = User(
        organization_id=org.id,
        full_name="Other User",
        email="other-production@example.com",
        password_hash=hash_password("Other1234!"),
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    grant_production_role(db, org, user)

    return _login(client, "other-production@example.com", "Other1234!")


def test_create_work_center(client, auth_headers):
    response = client.post(
        "/api/v1/production/work-centers",
        json=_BASE_WORK_CENTER,
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert re.fullmatch(r"WC-[A-Z]+-001", data["code"])
    assert data["name"] == "Extrusion Line 1"
    assert data["center_type"] == "extrusion"
    assert data["status"] == "active"
    assert data["location"] == "Hall A"
    assert data["notes"] == "Primary extrusion work center"
    assert "id" in data
    assert "organization_id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_work_center_requires_auth(client):
    response = client.post("/api/v1/production/work-centers", json=_BASE_WORK_CENTER)
    assert response.status_code == 401


def test_list_work_centers_empty(client, auth_headers):
    response = client.get("/api/v1/production/work-centers", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_list_work_centers(client, auth_headers):
    created = client.post(
        "/api/v1/production/work-centers",
        json=_BASE_WORK_CENTER,
        headers=auth_headers,
    )

    response = client.get("/api/v1/production/work-centers", headers=auth_headers)

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["code"] == created.json()["code"]
    assert items[0]["center_type"] == "extrusion"


def test_get_work_center(client, auth_headers):
    create_response = client.post(
        "/api/v1/production/work-centers",
        json=_BASE_WORK_CENTER,
        headers=auth_headers,
    )
    work_center_id = create_response.json()["id"]

    response = client.get(
        f"/api/v1/production/work-centers/{work_center_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == work_center_id
    assert response.json()["code"] == create_response.json()["code"]


def test_get_work_center_not_found(client, auth_headers):
    response = client.get(
        f"/api/v1/production/work-centers/{uuid4()}",
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_update_work_center(client, auth_headers):
    create_response = client.post(
        "/api/v1/production/work-centers",
        json=_BASE_WORK_CENTER,
        headers=auth_headers,
    )
    work_center_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/production/work-centers/{work_center_id}",
        json={
            "name": "Extrusion Line 1A",
            "status": "under_maintenance",
            "notes": "Temporarily down",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Extrusion Line 1A"
    assert data["status"] == "under_maintenance"
    assert data["notes"] == "Temporarily down"
    assert data["code"] == create_response.json()["code"]


def test_update_work_center_not_found(client, auth_headers):
    response = client.patch(
        f"/api/v1/production/work-centers/{uuid4()}",
        json={"name": "Ghost center"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_work_center_codes_are_generated_and_unique(client, auth_headers):
    first = client.post("/api/v1/production/work-centers", json=_BASE_WORK_CENTER, headers=auth_headers)
    second = client.post("/api/v1/production/work-centers", json=_BASE_WORK_CENTER, headers=auth_headers)
    assert first.status_code == second.status_code == 201
    assert first.json()["code"].endswith("-001")
    assert second.json()["code"].endswith("-002")
    assert first.json()["code"] != second.json()["code"]



def test_duplicate_work_center_code_allowed_across_orgs(client, db, auth_headers):
    client.post(
        "/api/v1/production/work-centers",
        json=_BASE_WORK_CENTER,
        headers=auth_headers,
    )
    other_headers = _create_other_org_headers(client, db)

    response = client.post(
        "/api/v1/production/work-centers",
        json=_BASE_WORK_CENTER,
        headers=other_headers,
    )

    assert response.status_code == 201


def test_tenant_isolation_for_list_get_and_update(client, db, auth_headers):
    create_response = client.post(
        "/api/v1/production/work-centers",
        json=_BASE_WORK_CENTER,
        headers=auth_headers,
    )
    work_center_id = create_response.json()["id"]

    other_headers = _create_other_org_headers(client, db)

    list_response = client.get("/api/v1/production/work-centers", headers=other_headers)
    assert list_response.status_code == 200
    assert list_response.json() == []

    get_response = client.get(
        f"/api/v1/production/work-centers/{work_center_id}",
        headers=other_headers,
    )
    assert get_response.status_code == 404

    update_response = client.patch(
        f"/api/v1/production/work-centers/{work_center_id}",
        json={"name": "Cross tenant update"},
        headers=other_headers,
    )
    assert update_response.status_code == 404
