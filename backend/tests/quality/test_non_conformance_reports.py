from app.core.security import hash_password
from app.foundation.domain.enums import OrganizationStatus, UserStatus
from app.foundation.infrastructure.models import Organization, User


NCR_BASE = "/api/v1/quality/non-conformance-reports"


def _create_org(db, code="ncr-report-other-org") -> Organization:
    org = Organization(
        name="Other NCR Org",
        code=code,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _create_user(db, org, email="ncr-report-other@example.com") -> User:
    user = User(
        organization_id=org.id,
        full_name="Other NCR User",
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


def _base_report(**overrides) -> dict:
    payload = {
        "report_date": "2026-07-02",
        "source_type": "internal_production",
        "report_type": "product_non_conformance",
        "title": "Roll surface non-conformance",
        "description": "Surface marks found during final inspection.",
    }
    payload.update(overrides)
    return payload


def _create_report(client, auth_headers, **overrides):
    resp = client.post(NCR_BASE, json=_base_report(**overrides), headers=auth_headers)
    assert resp.status_code == 201
    return resp


# ── Create ─────────────────────────────────────────────────────────────────────

def test_create_ncr_report(client, auth_headers):
    resp = client.post(NCR_BASE, json=_base_report(), headers=auth_headers)

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "draft"
    assert data["report_number"].startswith("NCR-")
    assert data["title"] == "Roll surface non-conformance"
    assert data["organization_id"] is not None
    assert data["detected_by_user_id"] is not None


def test_create_report_number_auto_generated(client, auth_headers):
    first = _create_report(client, auth_headers)
    second = _create_report(client, auth_headers)

    assert first.json()["report_number"] != second.json()["report_number"]
    assert first.json()["report_number"].startswith("NCR-")


def test_create_report_status_not_caller_settable(client, auth_headers):
    payload = _base_report()
    payload["status"] = "open"
    resp = client.post(NCR_BASE, json=payload, headers=auth_headers)

    assert resp.status_code == 201
    assert resp.json()["status"] == "draft"


def test_create_report_title_required(client, auth_headers):
    payload = _base_report()
    del payload["title"]
    resp = client.post(NCR_BASE, json=payload, headers=auth_headers)

    assert resp.status_code == 422


def test_create_report_description_required(client, auth_headers):
    payload = _base_report()
    del payload["description"]
    resp = client.post(NCR_BASE, json=payload, headers=auth_headers)

    assert resp.status_code == 422


def test_create_report_with_reference_code(client, auth_headers):
    resp = client.post(
        NCR_BASE,
        json=_base_report(reference_code="BATCH-2026-001"),
        headers=auth_headers,
    )

    assert resp.status_code == 201
    assert resp.json()["reference_code"] == "BATCH-2026-001"


# ── Read / List ────────────────────────────────────────────────────────────────

def test_get_ncr_report(client, auth_headers):
    report = _create_report(client, auth_headers)

    resp = client.get(f"{NCR_BASE}/{report.json()['id']}", headers=auth_headers)

    assert resp.status_code == 200
    assert resp.json()["id"] == report.json()["id"]
    assert resp.json()["description"] == "Surface marks found during final inspection."


def test_get_report_wrong_org_returns_404(client, db, auth_headers):
    other_org = _create_org(db)
    _create_user(db, other_org)
    other_headers = _login(client, "ncr-report-other@example.com")
    other_report = _create_report(client, other_headers)

    resp = client.get(f"{NCR_BASE}/{other_report.json()['id']}", headers=auth_headers)

    assert resp.status_code == 404


def test_list_ncr_reports(client, auth_headers):
    _create_report(client, auth_headers)
    _create_report(client, auth_headers, source_type="supplier")

    resp = client.get(NCR_BASE, headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_filter_by_source_type(client, auth_headers):
    _create_report(client, auth_headers, source_type="internal_production")
    _create_report(client, auth_headers, source_type="supplier")

    resp = client.get(f"{NCR_BASE}?source_type=supplier", headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["source_type"] == "supplier"


def test_list_filter_by_status(client, auth_headers):
    report = _create_report(client, auth_headers)
    client.patch(f"{NCR_BASE}/{report.json()['id']}", json={"status": "open"}, headers=auth_headers)
    _create_report(client, auth_headers)

    resp = client.get(f"{NCR_BASE}?ncr_status=open", headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["status"] == "open"


# ── Update ─────────────────────────────────────────────────────────────────────

def test_patch_ncr_report_status(client, auth_headers):
    report = _create_report(client, auth_headers)

    resp = client.patch(
        f"{NCR_BASE}/{report.json()['id']}",
        json={"status": "open"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "open"


def test_patch_ncr_report_title(client, auth_headers):
    report = _create_report(client, auth_headers)

    resp = client.patch(
        f"{NCR_BASE}/{report.json()['id']}",
        json={"title": "Updated title"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated title"


def test_patch_report_wrong_org_returns_404(client, db, auth_headers):
    other_org = _create_org(db)
    _create_user(db, other_org)
    other_headers = _login(client, "ncr-report-other@example.com")
    other_report = _create_report(client, other_headers)

    resp = client.patch(
        f"{NCR_BASE}/{other_report.json()['id']}",
        json={"status": "open"},
        headers=auth_headers,
    )

    assert resp.status_code == 404


def test_cannot_reopen_closed_ncr_report(client, auth_headers):
    report = _create_report(client, auth_headers)
    close_resp = client.patch(
        f"{NCR_BASE}/{report.json()['id']}",
        json={"status": "closed"},
        headers=auth_headers,
    )
    assert close_resp.status_code == 200

    resp = client.patch(
        f"{NCR_BASE}/{report.json()['id']}",
        json={"status": "open"},
        headers=auth_headers,
    )

    assert resp.status_code == 400
