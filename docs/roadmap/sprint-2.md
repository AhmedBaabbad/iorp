# Sprint 2 — Status

**Completed:** 2026-06-10

---

## Scope delivered

Sprint 2 is a complete vertical slice (Slice 2) covering the commercial pipeline from sample tracking through quoting and confirmed order creation.

### Commercial (Slice 2)

| Item | Status |
|------|--------|
| Sample model + migration | ✓ Done |
| Sample CRUD API (create, list, list-for-customer, get, update) | ✓ Done |
| Sample code uniqueness per customer | ✓ Done |
| SampleEvaluation model + migration | ✓ Done |
| Sample evaluation API (create, list, get) | ✓ Done |
| Cancelled-sample guard on evaluation | ✓ Done |
| EVALUATED status bypass protection on sample update | ✓ Done |
| Quote model + migration | ✓ Done |
| Quote CRUD API (create, list, list-for-customer, get, update) | ✓ Done |
| Quote total auto-calculation (subtotal − discount + tax) | ✓ Done |
| CommercialOrder model + migration | ✓ Done |
| Commercial order API (create, list, list-for-customer, get, update) | ✓ Done |
| Quote status validation on order link (ISSUED/ACCEPTED only) | ✓ Done |
| Dev seed updated with Slice 2 data (sample, evaluation, quote, order) | ✓ Done |

### Pre-sprint refactoring

| Item | Status |
|------|--------|
| `CustomerService` (619 lines) split into `CustomerService`, `SampleService`, `QuoteService`, `OrderService` | ✓ Done |

### Review and stabilization (REV2-004 through REV2-007)

| Review | Outcome |
|--------|---------|
| REV2-004 Commercial consistency | Fixed: `SampleRepository.get_by_code` scoped org-wide instead of per-customer; follow-ups router variable and tag rename |
| REV2-005 End-to-end commercial flow | Fixed: cancelled-sample evaluation guard; quote status validation on order link; EVALUATED bypass protection on sample PATCH |
| REV2-006 Frontend readiness | Fixed: `PageFrame` moved from `features/customers/` to `components/layout/`; `SectionShell` extracted from duplicated section boilerplate; `estimated_consumption` type precision (`string \| null`) |
| REV2-007 Seed / test / docs sync | This document |

---

## Test coverage (Sprint 2)

| File | Tests |
|------|-------|
| `test_samples.py` | 16 |
| `test_sample_evaluations.py` | 9 |
| `test_quotes.py` | 13 |
| `test_orders.py` | 13 |
| **Total new** | **51** |

Sprint 1 tests (auth, customers, tenant isolation): 14. Cumulative total: 65+.

---

## Known deferred items (not blocking Sprint 3)

| Item | Reason deferred |
|------|----------------|
| Sample, quote, order frontend UI | ADR-003 scope freeze. Backend API is complete. |
| RBAC enforcement | Roles stored, not enforced. Planned post-Sprint 2. |
| Quote PDF generation | ADR-003 scope freeze. |
| Order → Production conversion | Planned for Sprint 3 (Production module). |
| 401 mid-session interceptor | Carried from Sprint 1 deferred items. |

---

## Sprint 3 — Recommended next work

**Commercial Slice 3 / Production module entry point.**

Proposed scope:
- `production_orders` — conversion path from confirmed `commercial_orders`
- Production status tracking
- RBAC enforcement on commercial routes (lock endpoints to roles)
- Sample, quote, and order frontend pages (deferred from Slice 2)
