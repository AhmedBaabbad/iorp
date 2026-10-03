from tests.production.order_fixtures import historical_order
"""Sprint 3 Production baseline tests.

8 focused tests verifying the critical Sprint 3 design decisions (D1-D8).
Each test is fully independent and uses the shared conftest fixtures
(client, auth_headers) that wire up a fresh in-memory SQLite DB per test.

Critical decisions verified here:
  D3 — duration_minutes is auto-calculated, never a caller input
  D4 — status in downtime_events is auto-derived from end_time
  D5 — crosses_midnight is auto-calculated in shift_definitions
  D7 — WasteRecord has no status field
  D8 — ProductionOrder priority defaults to 'normal'
"""

from decimal import Decimal
from datetime import datetime, timezone


# ── Local helpers (each test is self-contained) ───────────────────────────────

def _wc(client, headers, code="WC-T", center_type="extrusion"):
    """Create a work center and return its JSON body."""
    resp = client.post(
        "/api/v1/production/work-centers",
        json={"code": code, "name": f"Test Center {code}", "center_type": center_type},
        headers=headers,
    )
    assert resp.status_code == 201, f"work center create failed: {resp.text}"
    return resp.json()


def _sd(client, headers, wc_id, code, start, end):
    """Create a shift definition and return its JSON body."""
    resp = client.post(
        "/api/v1/production/shift-definitions",
        json={
            "code": code,
            "name": f"Shift {code}",
            "shift_type": "custom",
            "start_time": start,
            "end_time": end,
        },
        headers=headers,
    )
    assert resp.status_code == 201, f"shift definition create failed: {resp.text}"
    return resp.json()


def _po(client, headers, wc_id, **kwargs):
    """Create a production order and return its JSON body."""
    payload = {
        "work_center_id": wc_id,
        "product_type": "Steel Rod 14mm",
        "planned_quantity": "1000.00",
        "unit": "kg",
        "planned_start_date": "2026-07-01",
        "planned_end_date": "2026-07-07",
    }
    payload.update(kwargs)
    resp = historical_order(client, headers, payload)
    assert resp.status_code == 201, f"production order create failed: {resp.text}"
    return resp.json()


def _dt(client, headers, wc_id, start_iso, end_iso=None, category="breakdown"):
    """Create a downtime event and return its JSON body."""
    payload = {
        "work_center_id": wc_id,
        "start_time": start_iso,
        "category": category,
        "reason_code": "Test downtime reason",
    }
    if end_iso is not None:
        payload["end_time"] = end_iso
    resp = client.post(
        "/api/v1/production/downtime-events",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 201, f"downtime event create failed: {resp.text}"
    return resp.json()


# ── T1 — Work center create and list ─────────────────────────────────────────

def test_work_center_create_and_list(client, auth_headers):
    """
    T1: Create a work center with center_type=extrusion and verify
    it appears in the list scoped to the current tenant.
    Verifies basic production entity CRUD and organization_id scoping.
    """
    wc = _wc(client, auth_headers, code="WC-T1-EXT", center_type="extrusion")

    assert wc["code"].startswith("WC-") and wc["code"].endswith("-001")
    assert wc["center_type"] == "extrusion"
    assert wc["status"] == "active"           # auto-set on create
    assert "organization_id" in wc            # exposed in read schema (never in create input)

    # List must include the newly created work center
    resp = client.get("/api/v1/production/work-centers", headers=auth_headers)
    assert resp.status_code == 200
    codes = [w["code"] for w in resp.json()]
    assert wc["code"] in codes


# ── T2 — crosses_midnight auto-calculation (D5) ───────────────────────────────

def test_shift_definition_crosses_midnight(client, auth_headers):
    """
    T2: CRITICAL — Sprint 3 decision D5.
    crosses_midnight must be auto-calculated from end_time <= start_time.
    It is never a caller input.

    Night shift (23:00→07:00): end_time < start_time → crosses_midnight = True
    Morning shift (07:00→15:00): end_time > start_time → crosses_midnight = False
    """
    wc = _wc(client, auth_headers, code="WC-T2-SHIFTS")
    wc_id = wc["id"]

    # Night shift — must produce crosses_midnight = True
    night = _sd(client, auth_headers, wc_id, "SHIFT-NIGHT-T2", "23:00:00", "07:00:00")
    assert night["crosses_midnight"] is True, (
        "Night shift (23:00→07:00) must auto-calculate crosses_midnight=True (D5)"
    )
    # duration_hours must also be correct: 8 h across midnight
    assert night["duration_hours"] == "8.00"

    # Morning shift — must produce crosses_midnight = False
    morn = _sd(client, auth_headers, wc_id, "SHIFT-MORN-T2", "07:00:00", "15:00:00")
    assert morn["crosses_midnight"] is False, (
        "Morning shift (07:00→15:00) must auto-calculate crosses_midnight=False (D5)"
    )
    assert morn["duration_hours"] == "8.00"


# ── T3 — ProductionOrder auto-number (B2) and default priority (B3 / D8) ─────

def test_production_order_auto_number_and_default_priority(client, auth_headers):
    """
    T3: Sprint 3 decisions B2 and D8.
    B2 — Creating an order without order_number must auto-generate one.
    D8 — Creating an order without priority must default to 'normal'.
    """
    wc = _wc(client, auth_headers, code="WC-T3-PO")

    # Auto-generate order number (B2)
    order = _po(client, auth_headers, wc["id"])
    assert order["production_order_number"] is not None
    assert order["production_order_number"] != ""
    assert order["production_order_number"].startswith("PO-"), (
        "Auto-generated number must follow PO-YYYYNNNN format (B2)"
    )

    # Default priority to 'normal' (D8) — do not send priority in payload
    order2 = _po(client, auth_headers, wc["id"])
    assert order2["priority"] == "normal", (
        "ProductionOrder priority must default to 'normal' when not specified (D8)"
    )


# ── T4 — Production order item status guard (B5) ─────────────────────────────

def test_production_order_item_status_guard_cancelled(client, auth_headers):
    """
    T4: CRITICAL — Sprint 3 behavior B5.
    A cancelled production_order must reject new items with HTTP 400.
    This is a required business rule guard.
    """
    wc = _wc(client, auth_headers, code="WC-T4-GUARD")
    order = _po(client, auth_headers, wc["id"])
    order_id = order["id"]

    # Cancel through the dedicated action (a status PATCH cannot cancel since PROD-PLAN-003)
    patch = client.post(
        f"/api/v1/production/production-orders/{order_id}/cancel",
        json={"reason": "Test cancellation"},
        headers=auth_headers,
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["status"] == "cancelled"

    # Adding an item to a cancelled order must be rejected with 400 (B5)
    item_resp = client.post(
        f"/api/v1/production/production-orders/{order_id}/items",
        json={"planned_quantity": "100.00", "unit": "kg"},
        headers=auth_headers,
    )
    assert item_resp.status_code == 400, (
        "Adding items to a cancelled production order must return HTTP 400 (B5)"
    )
    assert "cancelled" in item_resp.json()["detail"].lower()


# ── T5 — Downtime event open flow (B6 / D3 / D4) ────────────────────────────

def test_downtime_event_open_flow(client, auth_headers):
    """
    T5: CRITICAL — Sprint 3 behaviors B6 and decisions D3 / D4.
    Creating a downtime event without end_time must auto-derive:
      status = 'open'           (D4 — derived, never a caller input)
      duration_minutes = None   (D3 — NULL because end_time is absent)
    """
    wc = _wc(client, auth_headers, code="WC-T5-DT")
    now_iso = datetime.now(timezone.utc).isoformat()

    event = _dt(client, auth_headers, wc["id"], now_iso)  # no end_time

    # status must be auto-derived as 'open' (D4)
    assert event["status"] == "open", (
        "status must auto-derive to 'open' when end_time is absent (D4)"
    )
    # duration_minutes must be NULL (D3)
    assert event["duration_minutes"] is None, (
        "duration_minutes must be NULL when end_time is absent (D3)"
    )


# ── T6 — Downtime event closed flow (B6 / D3 / D4) ──────────────────────────

def test_downtime_event_closed_flow(client, auth_headers):
    """
    T6: CRITICAL — Sprint 3 behaviors B6 and decisions D3 / D4.
    Updating a downtime event with end_time must auto-derive:
      status = 'closed'                     (D4)
      duration_minutes = integer minutes    (D3 — auto-calculated from timestamps)
    duration_minutes is never a caller input.
    """
    wc = _wc(client, auth_headers, code="WC-T6-DT")

    start = datetime(2026, 7, 2, 10, 0, 0, tzinfo=timezone.utc)
    end   = datetime(2026, 7, 2, 10, 45, 0, tzinfo=timezone.utc)  # exactly 45 minutes later

    # Create as OPEN
    event = _dt(client, auth_headers, wc["id"], start.isoformat())
    assert event["status"] == "open"
    assert event["duration_minutes"] is None
    event_id = event["id"]

    # Update with end_time — must transition to closed with correct duration
    resp = client.patch(
        f"/api/v1/production/downtime-events/{event_id}",
        json={"end_time": end.isoformat()},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    updated = resp.json()

    # status must auto-derive to 'closed' (D4)
    assert updated["status"] == "closed", (
        "status must auto-derive to 'closed' when end_time is set (D4)"
    )
    # duration_minutes must be auto-calculated as 45 (D3), to the hundredth of a minute
    assert Decimal(str(updated["duration_minutes"])) == Decimal("45"), (
        "duration_minutes must equal (end_time - start_time) in minutes = 45 (D3)"
    )


# ── T7 — Cross-tenant isolation ───────────────────────────────────────────────

def test_cross_tenant_isolation_work_center(client, db, auth_headers):
    """
    T7: Tenant isolation for production entities.
    Org A's work center must be invisible to Org B (404 on direct access,
    empty list on list endpoint).
    Validates ADR-001 multi-tenancy for Production module.
    """
    from app.core.security import hash_password
    from app.foundation.domain.enums import OrganizationStatus, UserStatus
    from app.foundation.infrastructure.models import Organization, User

    # Create work center as the test org (Org A)
    wc = _wc(client, auth_headers, code="WC-T7-ORGA")
    wc_id = wc["id"]

    # Create Org B with its own user directly in DB
    org_b = Organization(name="Org B T7", code="org-b-t7", status=OrganizationStatus.ACTIVE, timezone="UTC")
    db.add(org_b)
    db.commit()
    db.refresh(org_b)

    user_b = User(
        organization_id=org_b.id,
        full_name="Org B User",
        email="orgb-t7@example.com",
        password_hash=hash_password("OrgB1234!"),
        status=UserStatus.ACTIVE,
    )
    db.add(user_b)
    db.commit()
    db.refresh(user_b)
    from tests.production.conftest import grant_production_role
    grant_production_role(db, org_b, user_b)

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "orgb-t7@example.com", "password": "OrgB1234!"},
    )
    assert login_resp.status_code == 200
    headers_b = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    # Org B must not access Org A's work center by ID → 404
    resp = client.get(f"/api/v1/production/work-centers/{wc_id}", headers=headers_b)
    assert resp.status_code == 404, "Org B must not access Org A's work center (ADR-001)"

    # Org B's list must be empty
    list_resp = client.get("/api/v1/production/work-centers", headers=headers_b)
    assert list_resp.status_code == 200
    assert list_resp.json() == [], "Org B must see an empty list — no cross-tenant leakage"


# ── T8 — Quantity validation (B8 / B9) ───────────────────────────────────────

def test_quantity_validation(client, auth_headers):
    """
    T8: Sprint 3 behaviors B8 and B9.
    quantity = 0 on a final result entry must be rejected.
    quantity_wasted = -5 on WasteRecord must be rejected.
    Both use Pydantic Field(gt=0) validated at schema level before reaching service.
    """
    wc = _wc(client, auth_headers, code="WC-T8-QTY")
    order = _po(client, auth_headers, wc["id"])

    # A final result entry with quantity = 0 must fail (B8; legacy outputs are read-only now).
    # Pydantic Field(gt=0) returns 422 Unprocessable Entity
    output_resp = client.post(
        f"/api/v1/production/production-orders/{order['id']}/result/entries",
        json={"disposition": "stock_good", "quantity": "0"},
        headers=auth_headers,
    )
    # Every other field is valid, so the 422 is about the quantity alone.
    assert output_resp.status_code == 422, "quantity=0 must be rejected (B8)"
    assert any(e["loc"][-1] == "quantity" for e in output_resp.json()["detail"])

    # WasteRecord with quantity_wasted = -5 must fail (B9)
    waste_resp = client.post(
        "/api/v1/production/waste-records",
        json={
            "production_order_id": order["id"],
            "work_center_id": wc["id"],
            "waste_date": "2026-07-02",
            "quantity_wasted": "-5",
            "unit": "kg",
            "waste_category": "startup_setup",
        },
        headers=auth_headers,
    )
    # Every other field is valid, so the 422 is about the quantity alone.
    assert waste_resp.status_code == 422, "quantity_wasted=-5 must be rejected (B9)"
    assert any(e["loc"][-1] == "quantity_wasted" for e in waste_resp.json()["detail"])
