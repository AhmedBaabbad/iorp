"""Sprint 4 Quality/NCR baseline tests.

8 focused tests verifying the critical Sprint 4 design decisions (D1-D14).
Each test is fully independent and uses the shared conftest fixtures
(client, auth_headers) that wire up a fresh in-memory SQLite DB per test.

Critical decisions verified here:
  D1  — status and result are TWO SEPARATE fields in QualityCheck
  D2  — quantities balance (accepted + rejected = inspected) when the check closes: tests/quality/test_quality_inspections.py
  D3  — inspection_code auto-generated as QI-YYYY-NNNN, never a caller input
  D5  — quality_check_id REQUIRED in QualityDefect (enforced via nested route path)
  D6  — defect_count defaults to 1 when not provided
  D8/D9 — rejections (notes required, pending until a disposition is decided): tests/quality/test_quality_inspections.py
  D11 — report_number auto-generated as NCR-YYYY-NNNN, never a caller input
  D12 — NCR items cannot be created or modified on CLOSED reports
"""

import re

CHECKS_BASE = "/api/v1/quality/quality-checks"
NCR_BASE    = "/api/v1/quality/non-conformance-reports"


# ── Shared payload builders ───────────────────────────────────────────────────

def _base_check(**overrides) -> dict:
    payload = {
        "check_datetime": "2026-07-03T08:00:00+00:00",
        "check_type": "general",   # D4: business type — not visual/dimension
        "qty_inspected": 100,
    }
    payload.update(overrides)
    return payload


def _base_rejection(**overrides) -> dict:
    payload = {
        "rejection_date": "2026-07-03",
        "rejection_reason": "dimension_failure",
        "rejection_notes": "Batch rejected — thickness deviation exceeds tolerance.",  # D8: required
        "disposition": "rework",
        "quantity_rejected": 15,
        "unit": "pcs",
        # disposition_status intentionally absent — must auto-set to 'pending' (D9)
    }
    payload.update(overrides)
    return payload


def _base_report(**overrides) -> dict:
    payload = {
        "report_date": "2026-07-03",
        "source_type": "incoming_material",
        "report_type": "material_non_conformance",
        "title": "Non-conforming LLDPE granules — Batch B-44",
        "description": "Moisture content exceeds specification.",
        # report_number intentionally absent — must auto-generate (D11)
        # status intentionally absent — must auto-set to 'draft' (D11)
    }
    payload.update(overrides)
    return payload


# ── T2 — status/result Auto-Set and Separation (D1) ──────────────────────────

def test_status_and_result_are_separate_fields(client, auth_headers):
    """
    T2: CRITICAL — Sprint 4 decision D1.
    status and result are TWO SEPARATE fields in QualityCheck:
      status = lifecycle state  (always 'open' on creation)
      result = inspection outcome  (always null/None on creation)
    There must be no combined 'result_status' field.
    """
    resp = client.post(CHECKS_BASE, json=_base_check(), headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()

    # Both fields must exist independently (D1)
    assert "status" in data, "status must be a top-level field (D1)"
    assert "result" in data, "result must be a top-level field (D1)"
    assert "result_status" not in data, "result_status must NOT exist — they are two separate fields (D1)"

    # Auto-set values on creation (never caller-supplied)
    assert data["status"] == "open",  "status must auto-set to 'open' on creation (D1)"
    assert data["result"] is None,    "result must be null on creation (D1)"


# ── T3 — inspection_code Auto-Generation (D3) ────────────────────────────────

def test_inspection_code_auto_generation(client, auth_headers):
    """
    T3: Sprint 4 decision D3.
    inspection_code must be:
      - present in the response (never null)
      - formatted as QI-YYYY-NNNN (four-digit year, four-digit sequence)
      - absent from the create request body (never a caller input)
    Two checks in the same org must receive distinct codes.
    """
    payload = _base_check()
    assert "inspection_code" not in payload, "inspection_code must NOT be in create payload (D3)"

    first  = client.post(CHECKS_BASE, json=payload, headers=auth_headers)
    second = client.post(CHECKS_BASE, json=payload, headers=auth_headers)
    assert first.status_code == 201
    assert second.status_code == 201

    code = first.json()["inspection_code"]
    assert re.match(r"^QI-\d{4}-\d{4}$", code), (
        f"inspection_code '{code}' must match QI-YYYY-NNNN (D3)"
    )
    assert first.json()["inspection_code"] != second.json()["inspection_code"], (
        "Two checks in the same org must receive distinct inspection_codes (D3)"
    )


# ── T4 — quality_check_id Required in QualityDefect (D5 / D6) ────────────────

def test_quality_defect_requires_check_id(client, auth_headers):
    """
    T4: CRITICAL — Sprint 4 decisions D5 and D6.
    D5 — quality_check_id is REQUIRED for QualityDefect.
         The route is nested (/quality-checks/{check_id}/defects).
         A non-existent check_id must return 400.
    D6 — defect_count defaults to 1 when not provided.
    D7 — defect_category must be one of the 11 approved values (thickness used here).
    """
    # Non-existent check_id — must fail with 400 (not found in org)
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp_bad = client.post(
        f"{CHECKS_BASE}/{fake_id}/defects",
        json={
            "defect_date": "2026-07-03",
            "defect_category": "thickness",   # D7: one of 11 approved categories
            "severity": "major",
            "description": "Film thickness deviation: measured 0.3mm, target 0.5mm.",
        },
        headers=auth_headers,
    )
    assert resp_bad.status_code == 400, (
        "Creating a defect with a non-existent check_id must return 400 (D5)"
    )

    # Valid check — defect_count must default to 1 (D6)
    check = client.post(CHECKS_BASE, json=_base_check(), headers=auth_headers)
    assert check.status_code == 201
    check_id = check.json()["id"]

    resp_ok = client.post(
        f"{CHECKS_BASE}/{check_id}/defects",
        json={
            "defect_date": "2026-07-03",
            "defect_category": "thickness",
            "severity": "major",
            "description": "Film thickness deviation: measured 0.3mm, target 0.5mm.",
            # defect_count omitted — must default to 1 (D6)
        },
        headers=auth_headers,
    )
    assert resp_ok.status_code == 201
    assert resp_ok.json()["defect_count"] == 1, (
        "defect_count must default to 1 when not provided (D6)"
    )
    assert resp_ok.json()["quality_check_id"] == check_id, (
        "quality_check_id in response must match the URL path parameter (D5)"
    )


# ── T6 — NCR report_number Auto-Generation and status=draft (D11) ────────────

def test_ncr_report_number_auto_generation(client, auth_headers):
    """
    T6: Sprint 4 decision D11.
    report_number must be:
      - present in the response (never null)
      - formatted as NCR-YYYY-NNNN
      - absent from the create request body (never a caller input)
    status must auto-set to 'draft' on creation (never a caller input).
    Two reports must receive distinct numbers.
    """
    payload = _base_report()
    assert "report_number" not in payload, "report_number must NOT be in create payload (D11)"
    assert "status" not in payload,        "status must NOT be in create payload (D11)"

    first  = client.post(NCR_BASE, json=payload, headers=auth_headers)
    second = client.post(NCR_BASE, json=payload, headers=auth_headers)
    assert first.status_code == 201
    assert second.status_code == 201

    number = first.json()["report_number"]
    assert re.match(r"^NCR-\d{4}-\d{4}$", number), (
        f"report_number '{number}' must match NCR-YYYY-NNNN (D11)"
    )
    assert first.json()["status"] == "draft", (
        "NCR status must auto-set to 'draft' on creation (D11)"
    )
    assert first.json()["report_number"] != second.json()["report_number"], (
        "Two NCR reports must receive distinct report_numbers (D11)"
    )


# ── T7 — NCR Item Status Guard on Closed Report (D12) ─────────────────────────

def test_ncr_item_status_guard_on_closed_report(client, auth_headers):
    """
    T7: CRITICAL — Sprint 4 decision D12.
    NCR items cannot be created or modified on a CLOSED report.
    This is the most critical guard in the NCR module.
    The guard fires for both create and update operations.
    """
    # Create and close an NCR report
    report = client.post(NCR_BASE, json=_base_report(), headers=auth_headers)
    assert report.status_code == 201
    report_id = report.json()["id"]

    close = client.patch(
        f"{NCR_BASE}/{report_id}",
        json={"status": "closed"},
        headers=auth_headers,
    )
    assert close.status_code == 200
    assert close.json()["status"] == "closed"

    # Attempt to create an item on the closed report — must be blocked (D12)
    item_resp = client.post(
        f"{NCR_BASE}/{report_id}/items",
        json={
            "item_name": "Blocked item",
            "issue_description": "This item must not be created on a closed report.",
        },
        headers=auth_headers,
    )
    assert item_resp.status_code == 400, (
        "Creating an item on a CLOSED report must return 400 (D12)"
    )
    assert "closed" in item_resp.json()["detail"].lower(), (
        "Error message must indicate the report is closed (D12)"
    )


# ── T8 — Cross-Tenant Isolation for Quality (ADR-001) ─────────────────────────

def test_cross_tenant_isolation_quality(client, db, auth_headers):
    """
    T8: Tenant isolation for Quality entities (ADR-001).
    Org A's QualityCheck must be:
      - invisible to Org B on direct GET (404)
      - unusable as a parent for Org B's QualityDefect (400 — not in org)
    organization_id is never accepted from the caller — it comes from the JWT.
    """
    from app.core.security import hash_password
    from app.foundation.domain.enums import OrganizationStatus, UserStatus
    from app.foundation.infrastructure.models import Organization, User

    # Create a QualityCheck as Org A (the test org from conftest)
    check = client.post(CHECKS_BASE, json=_base_check(), headers=auth_headers)
    assert check.status_code == 201
    check_id = check.json()["id"]

    # Create Org B with its own user directly in DB
    org_b = Organization(
        name="Org B Quality T8",
        code="org-b-q-t8",
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
    )
    db.add(org_b)
    db.commit()
    db.refresh(org_b)

    user_b = User(
        organization_id=org_b.id,
        full_name="Org B Quality User",
        email="orgb-quality-t8@example.com",
        password_hash=hash_password("OrgB1234!"),
        status=UserStatus.ACTIVE,
    )
    db.add(user_b)
    db.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "orgb-quality-t8@example.com", "password": "OrgB1234!"},
    )
    assert login.status_code == 200
    headers_b = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Org B cannot access Org A's check → 404 (ADR-001)
    get_resp = client.get(f"{CHECKS_BASE}/{check_id}", headers=headers_b)
    assert get_resp.status_code == 404, (
        "Org B must not access Org A's QualityCheck — must return 404 (ADR-001)"
    )

    # Org B cannot create a defect against Org A's check → 400 (ADR-001)
    defect_resp = client.post(
        f"{CHECKS_BASE}/{check_id}/defects",
        json={
            "defect_date": "2026-07-03",
            "defect_category": "surface",
            "severity": "minor",
            "description": "Cross-tenant defect attempt.",
        },
        headers=headers_b,
    )
    assert defect_resp.status_code == 400, (
        "Org B must not create a defect under Org A's check — must return 400 (ADR-001)"
    )
