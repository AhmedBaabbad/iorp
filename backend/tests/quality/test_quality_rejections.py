from app.core.security import hash_password
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, User


CHECKS_BASE = "/api/v1/quality/quality-checks"
REJECTIONS_BASE = "/api/v1/quality/quality-rejections"


def _create_org(db, code="quality-rejection-other-org") -> Organization:
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


def _create_user(db, org, email="quality-rejection-other@example.com") -> User:
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


def _base_quality_check(**overrides) -> dict:
    payload = {
        "check_datetime": "2026-07-02T09:00:00+00:00",
        "check_type": "finished_product_inspection",
        "qty_inspected": 10,
        "qty_accepted": 6,
        "qty_rejected": 4,
    }
    payload.update(overrides)
    return payload


def _base_defect(**overrides) -> dict:
    payload = {
        "defect_date": "2026-07-02",
        "defect_category": "surface",
        "severity": "critical",
        "defect_count": 2,
        "description": "Deep surface scratches across the roll",
    }
    payload.update(overrides)
    return payload


def _base_rejection(**overrides) -> dict:
    payload = {
        "rejection_date": "2026-07-02",
        "rejection_reason": "critical_defect",
        "rejection_notes": "Surface damage is visible and fails release criteria.",
        "disposition": "scrap",
        "quantity_rejected": 4,
        "unit": "pcs",
    }
    payload.update(overrides)
    return payload


def _create_quality_check(client, auth_headers, **overrides):
    resp = client.post(
        CHECKS_BASE,
        json=_base_quality_check(**overrides),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp


def _create_defect(client, auth_headers, quality_check_id: str, **overrides):
    resp = client.post(
        f"{CHECKS_BASE}/{quality_check_id}/defects",
        json=_base_defect(**overrides),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp


def _create_rejection(client, auth_headers, **overrides):
    resp = client.post(
        REJECTIONS_BASE,
        json=_base_rejection(**overrides),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp


def test_create_quality_rejection_with_check_and_defect(client, auth_headers):
    check = _create_quality_check(client, auth_headers)
    defect = _create_defect(client, auth_headers, check.json()["id"])

    resp = client.post(
        REJECTIONS_BASE,
        json=_base_rejection(
            quality_check_id=check.json()["id"],
            quality_defect_id=defect.json()["id"],
        ),
        headers=auth_headers,
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["quality_check_id"] == check.json()["id"]
    assert data["quality_defect_id"] == defect.json()["id"]
    assert data["disposition_status"] == "pending"
    assert data["rejected_by_user_id"] is not None


def test_create_rejection_notes_required(client, auth_headers):
    check = _create_quality_check(client, auth_headers)

    resp = client.post(
        REJECTIONS_BASE,
        json=_base_rejection(quality_check_id=check.json()["id"], rejection_notes=""),
        headers=auth_headers,
    )

    assert resp.status_code == 422


def test_create_quantity_zero_rejected(client, auth_headers):
    check = _create_quality_check(client, auth_headers)

    resp = client.post(
        REJECTIONS_BASE,
        json=_base_rejection(quality_check_id=check.json()["id"], quantity_rejected=0),
        headers=auth_headers,
    )

    assert resp.status_code == 422


def test_create_wrong_org_check_rejected(client, db, auth_headers):
    other_org = _create_org(db)
    _create_user(db, other_org)
    other_headers = _login(client, "quality-rejection-other@example.com")
    other_check = _create_quality_check(client, other_headers)

    resp = client.post(
        REJECTIONS_BASE,
        json=_base_rejection(quality_check_id=other_check.json()["id"]),
        headers=auth_headers,
    )

    assert resp.status_code == 400


def test_list_filter_by_disposition_status(client, auth_headers):
    check = _create_quality_check(client, auth_headers)
    pending = _create_rejection(client, auth_headers, quality_check_id=check.json()["id"])

    resp = client.get(f"{REJECTIONS_BASE}?disposition_status=pending", headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == pending.json()["id"]


def test_get_wrong_org_returns_404(client, db, auth_headers):
    other_org = _create_org(db)
    _create_user(db, other_org)
    other_headers = _login(client, "quality-rejection-other@example.com")
    other_check = _create_quality_check(client, other_headers)
    other_rejection = _create_rejection(
        client,
        other_headers,
        quality_check_id=other_check.json()["id"],
    )

    resp = client.get(f"{REJECTIONS_BASE}/{other_rejection.json()['id']}", headers=auth_headers)

    assert resp.status_code == 404


def test_patch_disposition_status_to_executed(client, auth_headers):
    check = _create_quality_check(client, auth_headers)
    rejection = _create_rejection(client, auth_headers, quality_check_id=check.json()["id"])

    resp = client.patch(
        f"{REJECTIONS_BASE}/{rejection.json()['id']}",
        json={"disposition_status": "executed"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["disposition_status"] == "executed"


def test_create_rejection_defect_from_different_check_rejected(client, auth_headers):
    check_a = _create_quality_check(client, auth_headers)
    check_b = _create_quality_check(client, auth_headers)
    defect_on_b = _create_defect(client, auth_headers, check_b.json()["id"])

    resp = client.post(
        REJECTIONS_BASE,
        json=_base_rejection(
            quality_check_id=check_a.json()["id"],
            quality_defect_id=defect_on_b.json()["id"],
        ),
        headers=auth_headers,
    )

    assert resp.status_code == 400
