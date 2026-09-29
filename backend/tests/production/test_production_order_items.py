from tests.production.order_fixtures import historical_order
import pytest

from app.core.security import hash_password
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, User
from tests.production.conftest import grant_production_role


ZERO_UUID = "00000000-0000-0000-0000-000000000000"
ITEMS_BASE = "/api/v1/production/production-orders/{production_order_id}/items"


def _create_org(db, code="other-org") -> Organization:
    org = Organization(
        name="Other Org",
        code=code,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _create_user(db, org, email="other@example.com") -> User:
    user = User(
        organization_id=org.id,
        full_name="Other User",
        email=email,
        password_hash=hash_password("Other1234!"),
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    grant_production_role(db, org, user)
    return user


def _login(client, email, password="Other1234!") -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _base_order(work_center_id: str, **overrides) -> dict:
    payload = {
        "work_center_id": work_center_id,
        "product_type": "PE Film",
        "planned_quantity": "100.00",
        "unit": "kg",
        "planned_start_date": "2026-07-01",
        "planned_end_date": "2026-07-02",
    }
    payload.update(overrides)
    return payload


def _base_item(**overrides) -> dict:
    payload = {
        "planned_quantity": "12.50",
        "unit": "kg",
        "notes": "First roll",
    }
    payload.update(overrides)
    return payload


def _items_url(production_order_id: str) -> str:
    return ITEMS_BASE.format(production_order_id=production_order_id)


def _item_url(production_order_id: str, item_id: str) -> str:
    return f"{_items_url(production_order_id)}/{item_id}"


def _create_work_center(client, auth_headers, code="WC-ITEM-001"):
    resp = client.post(
        "/api/v1/production/work-centers",
        json={"code": code, "name": "Line 1", "center_type": "extrusion"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp


def _create_order(client, auth_headers, work_center_id: str, **overrides):
    resp = historical_order(client, auth_headers, _base_order(work_center_id, **overrides))
    assert resp.status_code == 201
    return resp


def _create_item(client, auth_headers, production_order_id: str, **overrides):
    resp = client.post(
        _items_url(production_order_id),
        json=_base_item(**overrides),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp


# Status changes only through transitions; walk the lifecycle to reach the wanted status.
_PATH_TO = {"released": ["release"], "in_progress": ["release", "start"], "completed": ["release", "start", "complete"], "cancelled": ["cancel"]}


def _patch_order_status(client, auth_headers, production_order_id: str, status: str):
    for action in _PATH_TO[status]:
        resp = client.post(
            f"/api/v1/production/production-orders/{production_order_id}/transitions",
            json={"action": action, "reason": "Test"},
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
    return resp


@pytest.fixture
def work_center(client, auth_headers):
    return _create_work_center(client, auth_headers).json()


@pytest.fixture
def production_order(client, auth_headers, work_center):
    return _create_order(client, auth_headers, work_center["id"]).json()


def test_create_item_auto_line_no(client, auth_headers, production_order):
    resp = client.post(
        _items_url(production_order["id"]),
        json=_base_item(planned_quantity="12.50"),
        headers=auth_headers,
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["line_no"] == 1
    assert data["planned_quantity"] == "12.500"  # same precision as allocations


def test_create_item_explicit_line_no(client, auth_headers, production_order):
    resp = client.post(
        _items_url(production_order["id"]),
        json=_base_item(line_no=5),
        headers=auth_headers,
    )

    assert resp.status_code == 201
    assert resp.json()["line_no"] == 5


def test_create_item_auto_increments_line_no(client, auth_headers, production_order):
    first = _create_item(client, auth_headers, production_order["id"])
    second = _create_item(client, auth_headers, production_order["id"])

    assert first.json()["line_no"] == 1
    assert second.json()["line_no"] == 2


def test_create_item_order_not_found(client, auth_headers):
    resp = client.post(
        _items_url(ZERO_UUID),
        json=_base_item(),
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_create_item_cancelled_order_rejected(client, auth_headers, production_order):
    _patch_order_status(client, auth_headers, production_order["id"], "cancelled")

    resp = client.post(
        _items_url(production_order["id"]),
        json=_base_item(),
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_create_item_duplicate_line_no_rejected(client, auth_headers, production_order):
    _create_item(client, auth_headers, production_order["id"], line_no=1)

    resp = client.post(
        _items_url(production_order["id"]),
        json=_base_item(line_no=1),
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_create_item_requires_auth(client, production_order):
    resp = client.post(
        _items_url(production_order["id"]),
        json=_base_item(),
    )
    assert resp.status_code == 401


def test_list_items(client, auth_headers, production_order):
    _create_item(client, auth_headers, production_order["id"], line_no=2)
    _create_item(client, auth_headers, production_order["id"], line_no=1)

    resp = client.get(_items_url(production_order["id"]), headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert [item["line_no"] for item in data] == [1, 2]


def test_list_items_order_not_found(client, auth_headers):
    resp = client.get(_items_url(ZERO_UUID), headers=auth_headers)
    assert resp.status_code == 404


def test_get_item(client, auth_headers, production_order):
    create_resp = _create_item(client, auth_headers, production_order["id"])
    item_id = create_resp.json()["id"]

    resp = client.get(_item_url(production_order["id"], item_id), headers=auth_headers)

    assert resp.status_code == 200
    assert "notes" in resp.json()


def test_get_item_not_found(client, auth_headers, production_order):
    resp = client.get(_item_url(production_order["id"], ZERO_UUID), headers=auth_headers)
    assert resp.status_code == 404


def test_update_item(client, auth_headers, production_order):
    create_resp = _create_item(client, auth_headers, production_order["id"])
    item_id = create_resp.json()["id"]

    resp = client.patch(
        _item_url(production_order["id"], item_id),
        json={"planned_quantity": "25.75"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["planned_quantity"] == "25.750"


def test_update_item_completed_order_rejected(client, auth_headers, production_order):
    create_resp = _create_item(client, auth_headers, production_order["id"])
    item_id = create_resp.json()["id"]
    _patch_order_status(client, auth_headers, production_order["id"], "completed")

    resp = client.patch(
        _item_url(production_order["id"], item_id),
        json={"planned_quantity": "25.75"},
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_delete_item(client, auth_headers, production_order):
    create_resp = _create_item(client, auth_headers, production_order["id"])
    item_id = create_resp.json()["id"]

    delete_resp = client.delete(
        _item_url(production_order["id"], item_id),
        headers=auth_headers,
    )
    get_resp = client.get(_item_url(production_order["id"], item_id), headers=auth_headers)

    assert delete_resp.status_code == 204
    assert get_resp.status_code == 404


def test_delete_item_in_progress_order_rejected(client, auth_headers, production_order):
    create_resp = _create_item(client, auth_headers, production_order["id"])
    item_id = create_resp.json()["id"]
    _patch_order_status(client, auth_headers, production_order["id"], "in_progress")

    resp = client.delete(
        _item_url(production_order["id"], item_id),
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_delete_item_completed_order_rejected(client, auth_headers, production_order):
    create_resp = _create_item(client, auth_headers, production_order["id"])
    item_id = create_resp.json()["id"]
    _patch_order_status(client, auth_headers, production_order["id"], "completed")

    resp = client.delete(
        _item_url(production_order["id"], item_id),
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_tenant_isolation(client, db, auth_headers, production_order):
    first_item = _create_item(client, auth_headers, production_order["id"])

    other_org = _create_org(db, code="production-item-tenant-org")
    _create_user(db, other_org, email="production-item-tenant@example.com")
    other_headers = _login(client, "production-item-tenant@example.com")
    other_work_center = _create_work_center(client, other_headers, code="WC-ITEM-SECOND")
    other_order = _create_order(client, other_headers, other_work_center.json()["id"])
    other_item = _create_item(client, other_headers, other_order.json()["id"])

    get_resp = client.get(
        _item_url(ZERO_UUID, other_item.json()["id"]),
        headers=auth_headers,
    )
    list_resp = client.get(_items_url(production_order["id"]), headers=auth_headers)

    assert get_resp.status_code == 404
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1
    assert list_resp.json()[0]["id"] == first_item.json()["id"]
