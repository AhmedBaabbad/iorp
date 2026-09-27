# Sprint 5 — Status

**Completed:** 2026-07-06

---

## Scope delivered

Sprint 5 delivered the full frontend UI expansion — 12 feature modules covering the complete Commercial and Production domain. All features follow the feature-oriented pattern (ADR-002), thin-page rule, and the loading/empty/error UX baseline established in Sprint 5.

### Commercial UI (FE5-001 to FE5-004)

| Item | Status |
|------|--------|
| Samples — list / detail / create | ✓ Done |
| Sample Evaluations — nested section in sample detail | ✓ Done |
| Quotes — list / detail / create with items + totals | ✓ Done |
| Commercial Orders — list / detail / create with items | ✓ Done |

### Production UI (FE5-005 to FE5-012)

| Item | Status |
|------|--------|
| Work Centers — list / detail / create | ✓ Done |
| Shifts — list / detail / create with crosses_midnight notice | ✓ Done |
| Production Orders — list / detail / create with priority + auto-number | ✓ Done |
| Production Order Items — nested section in order detail with status guard | ✓ Done |
| Shift Reports — list / detail / create with Submit/Approve progression | ✓ Done |
| Production Outputs — list / detail / create with work_center required | ✓ Done |
| Downtime Events — list / detail / create with open/closed lifecycle | ✓ Done |
| Waste Records — list / detail / create with no status field | ✓ Done |

---

## Reviews completed

| Review | Result |
|--------|--------|
| REV5-001 — Frontend Architecture & ADR Compliance | Approved (IS-001 resolved: `getShiftDefinitionsForSelect` removed, `getShifts()` extended with `work_center_id` filter) |
| REV5-002 — Feature Structure & Thin Pages | Approved |
| REV5-003 — API Integration & UX States | Approved |
| REV5-004 — Cross-Module UI Consistency Pass | Approved |
| REV5-005 — End-to-End Frontend Flow Validation | Approved (3 low-severity fixes identified) |

---

## Key design decisions locked in Sprint 5

See [docs/frontend/patterns.md](../frontend/patterns.md) Section B for full details.

| Decision | Summary |
|----------|---------|
| D1 | `shift_definition_id` not `shift_id` |
| D2 | `production_order_number` auto-generated, read-only |
| D3 | `duration_minutes` auto-calculated, not a form input |
| D4 | Downtime `status` auto-derived from `end_time` |
| D5 | `crosses_midnight` auto-calculated, not a form input |
| D6 | `WasteRecord` has no status field — intentional static record |
| D7 | Quality fields absent from Production UI |
| D8 | Status transitions via action buttons (Submit/Approve, End Downtime) |
| D9 | `work_center_id` required on all execution entities |
| D10 | Nested sections (evaluations, items) not standalone routes |

---

## Remaining low-severity fixes (post-sprint, non-blocking)

From REV5-005:

- **IS-001** (MEDIUM): Shift report references in DowntimeEventDetail, WasteRecordDetail, and ProductionOutputDetail show raw UUIDs. Fix: fetch shift report by ID, show `report_date` as link label.
- **IS-002** (MEDIUM): ShiftReportDetail production order reference shows raw UUID. Fix: load production orders list, apply `formatProductionOrderLabel`.
- **IS-003** (LOW): Redundant `loadDowntimeEvent()` after End Downtime success causes loading flash. Fix: remove the call — `setEvent(closedEvent)` is sufficient.
- **IS-004** (LOW): ShiftForm midnight notice wording includes "(crosses midnight = true)". Fix: clean up the copy.

These fixes are documented in the Codex fix prompt produced by REV5-005.

---

## Patterns established

See [docs/frontend/patterns.md](../frontend/patterns.md) for the full reference.

- **P1** Feature-oriented structure (api/ + types/ + components/)
- **P2** Thin pages (4–11 lines, no logic)
- **P3** API centralized in `{name}-api.ts`
- **P4** `lib/api-client.ts` is the only HTTP client
- **P5** Nested section pattern for sub-entities
- **P6** Feature-specific status badge components
- **P7** Loading/empty/error/submit UX baseline

---

## Next: Sprint 6 — Quality/NCR UI expansion (FE6)

| Task | Scope |
|------|-------|
| FE6-001 | Quality Checks UI — mirror `features/production-orders/` |
| FE6-002 | Quality Defects UI — nested section, mirror sample-evaluations |
| FE6-003 | Quality Rejections UI — mirror `features/production-outputs/` |
| FE6-004 | NCR Reports UI — mirror `features/shift-reports/` |
| FE6-005 | NCR Items UI — nested section, mirror production-order-items |
