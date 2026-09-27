# Sprint 3 — Status

**Completed:** 2026-07-02

---

## Scope delivered

Sprint 3 delivered the Production module baseline — a full 8-entity vertical slice covering the operational chain from work center scheduling through production output recording, downtime tracking, and waste logging.

### Production module (baseline)

| Item | Status |
|------|--------|
| WorkCenter model + migration | ✓ Done |
| WorkCenter CRUD API (create, list, get, update) | ✓ Done |
| ShiftDefinition model + migration | ✓ Done |
| ShiftDefinition CRUD API + `crosses_midnight` auto-calculation (D5) | ✓ Done |
| ProductionOrder model + migration | ✓ Done |
| ProductionOrder CRUD API + auto-number generation (B2) + default priority (D8) | ✓ Done |
| ProductionOrderItem model (cascade from order) | ✓ Done |
| ProductionOrderItem nested API (`/production-orders/{id}/items`) | ✓ Done |
| Cancelled-order guard on item create (B5) | ✓ Done |
| ShiftReport model + migration | ✓ Done |
| ShiftReport CRUD API + `shift_ended_at` auto-set on SUBMITTED (B3) | ✓ Done |
| ProductionOutput model + migration | ✓ Done |
| ProductionOutput CRUD API + `quantity_produced > 0` guard (B8) | ✓ Done |
| DowntimeEvent model + migration | ✓ Done |
| DowntimeEvent API + `status` auto-derived from `end_time` (D4) | ✓ Done |
| DowntimeEvent API + `duration_minutes` auto-calculated (D3) | ✓ Done |
| WasteRecord model + migration (no status field, D7) | ✓ Done |
| WasteRecord CRUD API + `quantity_wasted > 0` guard (B9) | ✓ Done |
| Three-level tenant isolation for all 8 entities (ADR-001) | ✓ Done |
| Production module boundary: no imports from Commercial or Foundation models (ADR-004) | ✓ Done |
| `commercial_order_id` as plain UUID reference — no cross-module FK | ✓ Done |
| Dev seed updated with full Sprint 3 Production chain | ✓ Done |

### Review and stabilization (REV3-002 through REV3-006)

| Review | Outcome |
|--------|---------|
| REV3-002 Production tenant scope | APPROVED — all 8 entities pass dual-filter get_by_id, org_id always from TenantContext |
| REV3-003 Production boundaries | APPROVED — QUALITY_STATION/QUALITY/rejected_output are operational classifications only; no quality logic in services |
| REV3-004 Production consistency pass | APPROVED (3 LOW) — IS-001 item method naming, IS-002 shift_definition 404 vs empty list, IS-003 tag naming |
| REV3-005 End-to-end production flow | APPROVED (4 LOW) — all B1-B10 behaviors pass; OB-001 status transitions not directionally enforced (deferred) |
| REV3-006 Seed / test / docs sync | This document |

---

## Test coverage (Sprint 3)

| File | Tests | Focus |
|------|-------|-------|
| `test_sprint3_baseline.py` | 8 | D1-D8 design decisions and B1-B10 behavior baseline |
| `test_work_centers.py` | existing | WorkCenter CRUD and tenant scoping |
| `test_downtime_events.py` | existing | DowntimeEvent lifecycle |

Sprint 1+2 tests (auth, customers, commercial chain): 65+. Cumulative total: 73+.

---

## Sprint 3 design decisions (D1–D8)

| # | Decision | Rule |
|---|----------|------|
| D1 | FK naming | `shift_definition_id` — full entity name, not short alias `shift_id` |
| D2 | work_center_id required on execution entities | All of ShiftReport, ProductionOutput, DowntimeEvent, WasteRecord carry `work_center_id` |
| D3 | duration_minutes auto-calculated | `int((end_time - start_time).total_seconds() // 60)` — never a caller input; NULL when `end_time` is None |
| D4 | status auto-derived in downtime_events | `end_time is None → open`, else `closed` — absent from Create and Update schemas |
| D5 | crosses_midnight auto-calculated | `end_time <= start_time → True` — never a caller input |
| D6 | reason_code free-text | Plain `String` — no enum, no FK, no lookup table |
| D7 | WasteRecord has no status | Static fact record in v0.1 — status intentionally excluded |
| D8 | ProductionOrder priority default | `normal` — set at DB level and schema default |

---

## Known deferred items (not blocking Sprint 4)

| Item | Reason deferred |
|------|----------------|
| Status transition direction enforcement (OB-001) | LOW severity. Order/ShiftReport status can be PATCH'd to any value freely. Directional enforcement planned post-Sprint 3. |
| Short method names on ProductionOrderItemService (IS-001) | LOW severity. Naming inconsistency vs other service classes. Cosmetic — not blocking. |
| `list_shift_definitions` 404 on invalid work_center_id (IS-002) | LOW severity. Other list endpoints return empty list. Behavior is consistent with per-route choice. |
| Tag naming inconsistency (IS-003) | LOW severity. `"production-orders"` vs `"production-work-centers"` naming pattern. Cosmetic. |
| ProductionOutput quality quantities (approved/rejected/rework) | ADR-003 scope freeze. Quality module will own these fields. |
| RBAC enforcement | Deferred from Sprint 2. All authenticated users have full access. |
| Costing and OEE calculations | ADR-003 scope freeze. |
| Production frontend UI | ADR-003 scope freeze. Backend API complete. |

---

## Sprint 4 — Recommended next work

**Candidate scope:**

- RBAC enforcement on all routes (Foundation + Commercial + Production)
- Commercial frontend pages deferred from Sprint 2 (samples, quotes, orders)
- Production frontend — work center dashboard and shift reporting UI
- Status transition guards for ProductionOrder and ShiftReport (OB-001 fix)
- Quality module entry: quality inspection linked to ProductionOutput
