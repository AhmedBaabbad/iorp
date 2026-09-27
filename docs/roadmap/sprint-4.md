# Sprint 4 — Status

**Completed:** 2026-07-03

---

## Scope delivered

Sprint 4 delivered the Quality and NCR module baseline — a 5-entity vertical slice covering the full inspection-to-non-conformance chain. All entities, routes, services, repositories, and migrations are implemented and reviewed.

### Quality module (baseline)

| Item | Status |
|------|--------|
| QualityCheck model + migration | ✓ Done |
| QualityCheck CRUD API + inspection_code auto-generation (D3) | ✓ Done |
| QualityCheck quantity constraint: accepted + rejected = inspected (D2) | ✓ Done |
| QualityCheck status/result two-field separation (D1) | ✓ Done |
| QualityDefect model + migration | ✓ Done |
| QualityDefect nested API (`/quality-checks/{id}/defects`) + flat list (D5) | ✓ Done |
| QualityDefect defect_count default=1 (D6) + 11 DefectCategory values (D7) | ✓ Done |
| QualityRejection model + migration | ✓ Done |
| QualityRejection API + rejection_notes required (D8) | ✓ Done |
| QualityRejection disposition_status auto-set to pending (D9) | ✓ Done |
| NonConformanceReport model + migration | ✓ Done |
| NonConformanceReport API + report_number auto-generation (D11) + status=draft (D11) | ✓ Done |
| NonConformanceItem model + migration | ✓ Done |
| NonConformanceItem nested API + line_no auto-assignment (D13) | ✓ Done |
| NCR item status guard on CLOSED reports (D12) | ✓ Done |
| QualityDefect has NO status field (D14) | ✓ Done |
| NCRItem has NO status field (D14) | ✓ Done |
| NCR module lives in `backend/app/quality/` — not a separate `ncr/` dir (D10) | ✓ Done |
| Three-level tenant isolation for all 5 entities (ADR-001) | ✓ Done |
| No Production module imports in Quality code (ADR-004) | ✓ Done |
| Production references stored as plain UUID — no cross-module FK (ADR-004) | ✓ Done |

### Review and stabilization (REV4-001 through REV4-006)

| Review | Outcome |
|--------|---------|
| REV4-001 ADR compliance | APPROVED after 2 fixes (IS-001: schema over-validation removed; IS-002: type annotation fix) |
| REV4-002 Tenant scope | APPROVED — all 5 entities pass three-level isolation; QualityDefect has dual isolation (direct + parent JOIN) |
| REV4-003 Quality vs NCR boundaries | APPROVED — clean separation; NCR inside `quality/`; no Production imports |
| REV4-004 Internal consistency | APPROVED (4 LOW observations, none blocking) |
| REV4-005 End-to-end flow validation | APPROVED — B1–B14 all pass; 2 LOW issues fixed post-review |
| REV4-006 Seed / test / docs sync | This document |

---

## Sprint 4 design decisions (D1–D14)

| # | Decision | Rule |
|---|----------|------|
| D1 | status / result separation | `status` = lifecycle (open/under_inspection/closed); `result` = outcome (accepted/rejected/etc.) — two independent fields |
| D2 | Quantity constraint | `qty_accepted + qty_rejected = qty_inspected` — enforced at schema (create) and service (update) |
| D3 | inspection_code auto-generated | `QI-YYYY-NNNN` — service generates; absent from create schema; unique per org |
| D4 | check_type = business type | `in_process_inspection / finished_product_inspection / sample_inspection / reinspection / issue_triggered / general` — not measurement methods |
| D5 | quality_check_id required in QualityDefect | Enforced via nested route path `/quality-checks/{check_id}/defects`; 400 if check not in org |
| D6 | defect_count default=1 | `Field(default=1, gt=0)` — optional in create body; always positive |
| D7 | DefectCategory has 11 values | dimension / thickness / surface / color / strength / winding / weight / packaging / labeling / finish / other |
| D8 | rejection_notes required | `Field(min_length=1)` in schema + whitespace guard in service — Quality PRD BR-02 |
| D9 | disposition_status auto-set to pending | Absent from create schema; service sets `DispositionStatus.PENDING`; Pydantic ignores extra fields |
| D10 | NCR lives in `backend/app/quality/` | No separate `ncr/` module in v0.1 — scaffold decision; all NCR code co-located with Quality |
| D11 | report_number auto-generated; status=draft | `NCR-YYYY-NNNN` — same pattern as inspection_code; both absent from create schema |
| D12 | NCR item status guard on CLOSED | `_validate_open_parent_report` blocks create and update; org check fires before status check (TN6 order) |
| D13 | NCR item line_no auto-assigned | `(max_line_no(report_id) or 0) + 1`; explicit override allowed; unique constraint at DB level |
| D14 | QualityDefect and NCRItem have NO status | Both are static fact records in v0.1 — no workflow lifecycle needed |

---

## Fixes applied post-review

| Fix | Scope | What changed |
|-----|-------|-------------|
| IS-001 (REV4-001) | `schemas.py` | Removed `_validate_closed_requires_result` from `QualityCheckUpdate` — schema fired without existing state; service handles it correctly |
| IS-002 (REV4-001) | `services.py` | Fixed `_validate_rejection_notes` type from `str \| None` to `str`; removed unreachable `is None` branch |
| IS-001 (REV4-005) | `services.py` | Added NCR closed-report re-open guard in `update_report` |
| IS-002 (REV4-005) | `services.py` | Added `_validate_defect_belongs_to_check` — defect must belong to same check when both IDs are provided |

---

## Test coverage (Sprint 4)

| File | Tests | Focus |
|------|-------|-------|
| `test_sprint4_baseline.py` | 8 | D1-D12 design decisions and critical behavior baseline |
| `test_quality_checks.py` | 15 | QualityCheck CRUD, qty constraint, status/result, tenant isolation |
| `test_quality_defects.py` | 7 | QualityDefect CRUD, nested route, defect_count, tenant isolation |
| `test_quality_rejections.py` | 9 | QualityRejection CRUD, rejection_notes, disposition lifecycle |
| `test_non_conformance_reports.py` | 10 | NCR Report CRUD, auto-number, status lifecycle, re-open guard |
| `test_non_conformance_items.py` | 5 | NCR Item CRUD, line_no auto-assign, status guard on CLOSED |

Sprint 1–3 tests: 73+. Sprint 4 adds 54. Cumulative total: **127+ tests**.

---

## Known deferred items (not blocking Sprint 5)

| Item | Reason deferred |
|------|----------------|
| TN5 soft rule: at least one quality reference on QualityRejection | LOW — not enforced in v0.1. Rejection can have neither `quality_check_id` nor `quality_defect_id`. Enforcement promoted to CAPA sprint. |
| Status transition sequence enforcement (Quality + NCR) | LOW — forward-only transition guard deferred. Only the terminal state guards are enforced (close requires result; NCR item blocked on CLOSED). |
| Flat list route for NCR items | LOW — NCR items have nested list and direct get; no org-wide flat list. May be added if needed for CAPA dashboard. |
| RBAC enforcement | Deferred from Sprint 2. All authenticated users still have full access. |
| CAPA (Corrective and Preventive Actions) | ADR-003 scope freeze. Planned for Sprint 5A. |
| Quality / NCR frontend UI | ADR-003 scope freeze. Backend API complete. |

---

## Sprint 5 — Candidate scope

**Option A: CAPA / Corrective Actions baseline**
- CorrectiveAction entity linked to NCR or QualityRejection
- CAPA lifecycle: open → in_progress → verified → closed
- Root cause + corrective measure tracking

**Option B: Frontend UI expansion**
- Production / Quality / NCR read-only dashboards
- Shift report entry UI
- Quality inspection submission form
