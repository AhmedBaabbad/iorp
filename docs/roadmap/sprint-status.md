# Sprint Status — IORP v0.1

Cumulative sprint status. Updated after each sprint completes.

---

| Sprint | Focus | Status | Completed |
|--------|-------|--------|-----------|
| Sprint 1 | Foundation + Commercial baseline | Done | 2026-06-08 |
| Sprint 1 Review | Foundation stabilization | Done | 2026-06-08 |
| Sprint 2 | Commercial flow expansion | Done | 2026-06-10 |
| Sprint 2 Review | Commercial stabilization | Done | 2026-06-10 |
| Sprint 3 | Production baseline | Done | 2026-07-02 |
| Sprint 3 Review | Production stabilization | Done | 2026-07-02 |
| Sprint 4 | Quality & NCR backend baseline | Done | 2026-07-03 |
| Sprint 4 Review | Quality/NCR backend stabilization | Done | 2026-07-03 |
| Sprint 5 | Commercial + Production UI | Done | 2026-07-06 |
| Sprint 5 Review | Frontend stabilization | Done | 2026-07-06 |
| Sprint 6 | Quality + NCR UI | Done | 2026-07-07 |
| Sprint 6 Review | Quality/NCR UI stabilization | Done | 2026-07-07 |
| Sprint 7 | CAPA UI Expansion | Done | 2026-07-07 |
| Sprint 7 Review | CAPA UI stabilization | Done | 2026-07-07 |

---

## Sprint 1 — Foundation + Commercial baseline

Delivered: JWT auth, organizations, users, roles, permissions. Customers, interactions, follow-ups. 3 customers, 1 interaction, 1 follow-up in seed data.

## Sprint 2 — Commercial flow expansion

Delivered: Samples, sample evaluations, quotes, confirmed orders. Full commercial pipeline from lead to confirmed order.

## Sprint 3 — Production baseline

Delivered: Work centers, shifts, production orders, production order items, shift reports, production outputs, downtime events, waste records. 8 backend entities.

## Sprint 4 — Quality & NCR backend baseline

Delivered: QualityCheck (auto-generated inspection_code QI-YYYY-NNNN), QualityDefect (nested, no status), QualityRejection (disposition + disposition_status), NonConformanceReport (auto-generated report_number NCR-YYYY-NNNN), NonConformanceItem (line_no auto-assigned). 127+ tests pass. Closed-report item guard on backend. Quantity constraint (accepted + rejected = inspected) on backend.

## Sprint 5 — Commercial + Production UI

Delivered: 12 frontend feature modules. Commercial UI (samples, evaluations, quotes, orders) and Production UI (work centers, shifts, orders, items, shift reports, outputs, downtime events, waste records). All pages thin (5–10 lines). Feature-oriented structure per ADR-002. Patterns documented in `docs/frontend/patterns.md`. Validated through REV5-001 to REV5-005.

## Sprint 6 — Quality + NCR UI

Delivered: 5 frontend feature modules. Quality UI (quality-checks, quality-defects, quality-rejections) and NCR UI (ncr-reports, ncr-items).

| Task | Delivered |
|------|-----------|
| FE6-001 | Quality Checks — list / detail / create; TWO badge components (status + result); Start/Close Inspection lifecycle |
| FE6-002 | Quality Defects — nested section in QualityCheckDetail; 11-category select; critical=RED badge; status guard for closed checks |
| FE6-003 | Quality Rejections — list / detail / create; rejection_notes required; Mark as Executed lifecycle; TWO badge components (disposition + disposition_status) |
| FE6-004 | NCR Reports — list / detail / create; Open/Start Review/Close Report lifecycle; NCR Reports added to nav + dashboard |
| FE6-005 | NCR Items — nested section in NcrReportDetail; replaced FE6-004 placeholder; status guard for closed reports; line_no as #1/#2 badges |

Validated through REV6-001 to REV6-005. All 14 critical behaviors (B1–B14) confirmed. Quality/NCR design decisions documented in `docs/frontend/patterns.md` Section F (FE6-D1 to FE6-D15).

## Sprint 7 — CAPA UI Expansion

Delivered: 3 frontend feature areas. CAPA UI now covers corrective actions, action follow-ups, and closure verification.

| Task | Delivered |
|------|-----------|
| FE7-001 | Corrective Actions UI Baseline |
| FE7-002 | Action Follow-up UI Baseline |
| FE7-003 | Closure and Verification UI Baseline |

Corrective Actions have list, create, and detail routes. Action Follow-ups and Closure Verification are nested inside Corrective Action detail and do not have standalone routes. Validated through REV7-001 to REV7-006.

Next recommended frontend direction: dashboard and cross-module summary work, role-based UX improvements, or the next approved roadmap item. Keep future work within v0.1 scope until explicitly expanded.
