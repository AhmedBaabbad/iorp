from app.core.security import hash_password
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, User


CHECKS_BASE = "/api/v1/quality/quality-checks"


def _create_org(db, code="quality-check-other-org") -> Organization:
    org = Organization(
        name="Other Quality Org",
        code=code,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _create_user(db, org, email="quality-check-other@example.com") -> User:
    user = User(
        organization_id=org.id,
        full_name="Other Quality User",
        email=email,
        password_hash=hash_password("Other1234!"),
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _login(client, email, password="Other1234!") -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _base_check(**overrides) -> dict:
    payload = {
        "check_datetime": "2026-07-02T08:00:00+00:00",
        "check_type": "in_process_inspection",
        "qty_inspected": 10,
        "qty_accepted": 8,
        "qty_rejected": 2,
    }
    payload.update(overrides)
    return payload


def _create_check(client, auth_headers, **overrides):
    resp = client.post(CHECKS_BASE, json=_base_check(**overrides), headers=auth_headers)
    assert resp.status_code == 201
    return resp


# ── Create ─────────────────────────────────────────────────────────────────────

def test_create_quality_check(client, auth_headers):
    resp = client.post(CHECKS_BASE, json=_base_check(), headers=auth_headers)

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "open"
    assert data["inspection_code"].startswith("QI-")
    assert data["qty_inspected"] == 10
    assert data["qty_accepted"] == 8
    assert data["qty_rejected"] == 2
    assert data["result"] is None
    assert data["organization_id"] is not None
    assert data["checked_by_user_id"] is not None


def test_create_check_inspection_code_auto_generated(client, auth_headers):
    first = _create_check(client, auth_headers)
    second = _create_check(client, auth_headers)

    assert first.json()["inspection_code"] != second.json()["inspection_code"]
    assert first.json()["inspection_code"].startswith("QI-")


def test_create_check_status_not_caller_settable(client, auth_headers):
    # status field is not in create schema — extra fields are ignored
    payload = _base_check()
    payload["status"] = "closed"
    resp = client.post(CHECKS_BASE, json=payload, headers=auth_headers)

    assert resp.status_code == 201
    assert resp.json()["status"] == "open"


def test_create_check_qty_imbalance_rejected(client, auth_headers):
    resp = client.post(
        CHECKS_BASE,
        json=_base_check(qty_accepted=5, qty_rejected=3),  # 5+3 != 10
        headers=auth_headers,
    )

    assert resp.status_code == 422


def test_create_check_qty_inspected_zero_rejected(client, auth_headers):
    resp = client.post(
        CHECKS_BASE,
        json=_base_check(qty_inspected=0, qty_accepted=0, qty_rejected=0),
        headers=auth_headers,
    )

    assert resp.status_code == 422


# ── Read / List ────────────────────────────────────────────────────────────────

def test_get_quality_check(client, auth_headers):
    check = _create_check(client, auth_headers)

    resp = client.get(f"{CHECKS_BASE}/{check.json()['id']}", headers=auth_headers)

    assert resp.status_code == 200
    assert resp.json()["id"] == check.json()["id"]
    assert resp.json()["inspection_code"] == check.json()["inspection_code"]


def test_get_check_wrong_org_returns_404(client, db, auth_headers):
    other_org = _create_org(db)
    _create_user(db, other_org)
    other_headers = _login(client, "quality-check-other@example.com")
    other_check = _create_check(client, other_headers)

    resp = client.get(f"{CHECKS_BASE}/{other_check.json()['id']}", headers=auth_headers)

    assert resp.status_code == 404


def test_list_quality_checks(client, auth_headers):
    _create_check(client, auth_headers)
    _create_check(client, auth_headers, check_type="general", qty_accepted=10, qty_rejected=0)

    resp = client.get(CHECKS_BASE, headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_filter_by_check_type(client, auth_headers):
    _create_check(client, auth_headers, check_type="in_process_inspection")
    _create_check(client, auth_headers, check_type="general", qty_accepted=10, qty_rejected=0)

    resp = client.get(f"{CHECKS_BASE}?check_type=general", headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["check_type"] == "general"


def test_list_filter_by_status(client, auth_headers):
    check = _create_check(client, auth_headers)
    client.patch(
        f"{CHECKS_BASE}/{check.json()['id']}",
        json={"status": "under_inspection"},
        headers=auth_headers,
    )
    _create_check(client, auth_headers)

    resp = client.get(f"{CHECKS_BASE}?check_status=under_inspection", headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["status"] == "under_inspection"


# ── Update ─────────────────────────────────────────────────────────────────────

def test_patch_quality_check_status(client, auth_headers):
    check = _create_check(client, auth_headers)

    resp = client.patch(
        f"{CHECKS_BASE}/{check.json()['id']}",
        json={"status": "under_inspection"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "under_inspection"


def test_patch_close_requires_result(client, auth_headers):
    check = _create_check(client, auth_headers)

    resp = client.patch(
        f"{CHECKS_BASE}/{check.json()['id']}",
        json={"status": "closed"},
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_patch_close_with_result(client, auth_headers):
    check = _create_check(client, auth_headers)

    resp = client.patch(
        f"{CHECKS_BASE}/{check.json()['id']}",
        json={"status": "closed", "result": "accepted"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "closed"
    assert resp.json()["result"] == "accepted"


def test_patch_partial_qty_update(client, auth_headers):
    check = _create_check(client, auth_headers)

    resp = client.patch(
        f"{CHECKS_BASE}/{check.json()['id']}",
        json={"qty_accepted": 9, "qty_rejected": 1},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["qty_accepted"] == 9
    assert resp.json()["qty_rejected"] == 1
    assert resp.json()["qty_inspected"] == 10


def test_patch_check_wrong_org_returns_404(client, db, auth_headers):
    other_org = _create_org(db)
    _create_user(db, other_org)
    other_headers = _login(client, "quality-check-other@example.com")
    other_check = _create_check(client, other_headers)

    resp = client.patch(
        f"{CHECKS_BASE}/{other_check.json()['id']}",
        json={"status": "under_inspection"},
        headers=auth_headers,
    )

    assert resp.status_code == 404
