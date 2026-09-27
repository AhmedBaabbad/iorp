from app.core.security import hash_password
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, User


CHECKS_BASE = "/api/v1/quality/quality-checks"
DEFECTS_BASE = "/api/v1/quality/quality-defects"


def _create_org(db, code="quality-defect-other-org") -> Organization:
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


def _create_user(db, org, email="quality-defect-other@example.com") -> User:
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
        "check_datetime": "2026-07-02T08:00:00+00:00",
        "check_type": "in_process_inspection",
        "qty_inspected": 10,
        "qty_accepted": 8,
        "qty_rejected": 2,
    }
    payload.update(overrides)
    return payload


def _base_defect(**overrides) -> dict:
    payload = {
        "defect_date": "2026-07-02",
        "defect_category": "thickness",
        "severity": "major",
        "defect_count": 2,
        "description": "Gauge is above tolerance on two rolls",
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


def test_create_quality_defect(client, auth_headers):
    check = _create_quality_check(client, auth_headers)

    resp = client.post(
        f"{CHECKS_BASE}/{check.json()['id']}/defects",
        json=_base_defect(),
        headers=auth_headers,
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["quality_check_id"] == check.json()["id"]
    assert data["organization_id"] is not None
    assert data["detected_by_user_id"] is not None
    assert data["defect_count"] == 2


def test_create_defect_count_zero_rejected(client, auth_headers):
    check = _create_quality_check(client, auth_headers)

    resp = client.post(
        f"{CHECKS_BASE}/{check.json()['id']}/defects",
        json=_base_defect(defect_count=0),
        headers=auth_headers,
    )

    assert resp.status_code == 422


def test_list_defects_by_quality_check(client, auth_headers):
    check = _create_quality_check(client, auth_headers)
    first = _create_defect(client, auth_headers, check.json()["id"])
    _create_defect(
        client,
        auth_headers,
        check.json()["id"],
        defect_category="surface",
        description="Surface scratch",
    )

    resp = client.get(f"{CHECKS_BASE}/{check.json()['id']}/defects", headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()) == 2
    assert {item["quality_check_id"] for item in resp.json()} == {check.json()["id"]}
    assert first.json()["id"] in {item["id"] for item in resp.json()}


def test_get_defect_wrong_org_returns_404(client, db, auth_headers):
    other_org = _create_org(db)
    _create_user(db, other_org)
    other_headers = _login(client, "quality-defect-other@example.com")
    other_check = _create_quality_check(client, other_headers)
    other_defect = _create_defect(client, other_headers, other_check.json()["id"])

    resp = client.get(f"{DEFECTS_BASE}/{other_defect.json()['id']}", headers=auth_headers)

    assert resp.status_code == 404


def test_patch_quality_defect(client, auth_headers):
    check = _create_quality_check(client, auth_headers)
    defect = _create_defect(client, auth_headers, check.json()["id"])

    resp = client.patch(
        f"{DEFECTS_BASE}/{defect.json()['id']}",
        json={"severity": "critical", "defect_count": 3},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["severity"] == "critical"
    assert resp.json()["defect_count"] == 3


def test_flat_list_filter_by_severity(client, auth_headers):
    check = _create_quality_check(client, auth_headers)
    critical = _create_defect(
        client,
        auth_headers,
        check.json()["id"],
        severity="critical",
        description="Critical winding defect",
    )
    _create_defect(client, auth_headers, check.json()["id"], severity="minor")

    resp = client.get(f"{DEFECTS_BASE}?severity=critical", headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == critical.json()["id"]
