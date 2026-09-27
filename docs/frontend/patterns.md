# Frontend Patterns — IORP v0.1

Sprint 5–7 reference. Read this before adding or changing frontend features.

---

## A. Feature Structure Pattern

### Folder layout

Every feature lives in `frontend/src/features/{name}/` with three required subfolders:

```
features/{name}/
  api/
    {name}-api.ts       ← all HTTP calls for this feature
  types/
    index.ts            ← TypeScript types for this feature
  components/
    {Component}.tsx     ← list, detail, form, badges, utils
    {name}-utils.ts     ← formatting helpers (formatDate, labels Records)
  index.ts              ← barrel: re-exports public API + types
```

### Component count by entity type

| Entity type | Components | Examples |
|-------------|-----------|---------|
| Simple entity | 3 | `{Name}sList`, `{Name}Detail`, `{Name}Form` |
| Nested entity (no own page) | 2 | `{Name}sList` (section), `{Name}Form` (inline) |
| Complex entity | 4–5 | add `{Name}StatusBadge`, `{Name}PriorityBadge`, utils |

### Thin page rule

Pages in `app/` are 4–11 lines maximum. They import and render one feature component. No logic, no state, no data fetching in pages.

```tsx
// app/production-orders/page.tsx  (4 lines)
import { ProductionOrdersList } from "@/features/production-orders";
export default function Page() { return <ProductionOrdersList />; }
```

Pattern B (async page, passes id prop) is used when `await params` is required by Next.js 15:

```tsx
// app/production-orders/[id]/page.tsx  (9 lines)
export default async function Page({ params }: Props) {
  const { id } = await params;
  return <ProductionOrderDetail productionOrderId={id} />;
}
```

### Nested section pattern

Two features are embedded sections inside a parent detail page — they are NOT standalone routes:

| Section | Lives inside | No separate route |
|---------|-------------|-------------------|
| `SampleEvaluationsList` + `SampleEvaluationForm` | `/samples/[id]` | ✓ |
| `ProductionOrderItemsList` + `ProductionOrderItemForm` | `/production-orders/[id]` | ✓ |

Both use `SectionShell` as the container. Both pass `onCreated` callback for inline list refresh without page reload.

---

## B. Critical Design Decisions

### D1 — Use `shift_definition_id`, not `shift_id`

The backend field is `shift_definition_id` everywhere. Do not shorten to `shift_id` in frontend types, form values, or API calls. This naming is intentional (shifts are reusable definitions, not event instances).

**FE6 rule:** follow the backend field name exactly in types and form values.

### D2 — `production_order_number` is auto-generated

Never add `production_order_number` as a form input. It is server-assigned on create. Display it read-only in detail header and as a labeled "Order Number" field in the detail grid. Show "Order number is auto-generated" in the form subtitle.

**FE6 rule:** `inspection_code` (QualityCheck) and `report_number` (NCR) follow the same pattern — read-only, labeled, never in forms.

### D3 — `duration_minutes` is auto-calculated

`DowntimeEvent.duration_minutes` is computed by the backend when `end_time` is set. Never show it as an input in the create form. Show it as a read-only field in the detail page after the event is closed.

### D4 — Downtime `status` is auto-derived from `end_time`

The backend sets `status = open` on create and `status = closed` when `end_time` is PATCHed. Do not add a status select to the DowntimeEventForm. The "End Downtime" PATCH is the only status transition — see D8.

### D5 — `crosses_midnight` is auto-calculated

`Shift.crosses_midnight` is computed from `start_time` and `end_time`. Never add it as a checkbox or input. The ShiftForm detects spans-midnight client-side (`end_time <= start_time`) and shows a notice only — it does not send this value to the API.

### D6 — WasteRecord has no status field

`WasteRecord` is an immutable operational fact. It has no lifecycle, no status badge, no Submit/Approve buttons. The absence is intentional — do not add status to WasteRecord in any sprint.

**FE6 rule:** `QualityDefect` and `NonConformanceItem` also have no status — follow the same pattern.

### D7 — Quality fields absent from Production UI

`approved_qty`, `rejected_qty`, `quality_hold`, and similar fields do not appear anywhere in the Production UI features. Quality data lives in the Quality/NCR module only. Production outputs record quantity produced; quality assessment is separate.

### D8 — Status transitions via dedicated action buttons

Two features have status lifecycles driven by action buttons on the detail page:

| Feature | Transition | Mechanism |
|---------|-----------|-----------|
| ShiftReport | draft → submitted → approved | "Submit Report" / "Approve Report" buttons; each disappears after its transition |
| DowntimeEvent | open → closed | "End Downtime" section with `datetime-local` input; PATCH `end_time` |

After a status PATCH, call `setEntity(response)` with the returned object. Do NOT call a redundant reload — the PATCH response contains the full updated state.

**FE6 rule:** NCR status progression (draft → under_review → closed) should follow the ShiftReport pattern — dedicated buttons, disappear after transition, no redundant reload.

### D9 — `work_center_id` required on execution entities

Work center is required on create for: `ProductionOutput`, `DowntimeEvent`, `WasteRecord`, `ShiftReport`. It is also required for `Shift` and `ProductionOrder`. All these forms load the work center list from the API via `getWorkCenters()` — never hardcoded options.

### D10 — Nested sections are not standalone routes

See Section A. `SampleEvaluations` and `ProductionOrderItems` have no URLs of their own. Creating a new evaluation or item does not redirect — it triggers `onCreated()` which refreshes the list inline. This keeps the parent entity in context throughout the interaction.

**FE6 rule:** `QualityDefects` (nested in QualityChecks) and `NonConformanceItems` (nested in NCR Reports) must follow this same pattern. Do not create `/quality-checks/[id]/defects/new` routes.

---

## C. Patterns Reference

### P1 — Feature-oriented structure

Each domain feature is self-contained: its own API calls, types, and components. No feature imports from another feature's `api/` folder. Cross-feature imports are only allowed in component files, not API files (ADR-004).

```
✓  ProductionOrderDetail imports getWorkCenters from @/features/work-centers
✗  production-orders-api.ts imports anything from @/features/shifts
```

### P2 — Thin pages

Pages delegate entirely to feature components. Zero business logic in `app/` files. All state, effects, and handlers live in `features/{name}/components/`.

### P3 — API centralized in `{name}-api.ts`

One file per feature for all HTTP calls. All functions call `apiClient` from `@/lib/api-client`. The `apiClient` is never re-implemented, never replaced with `fetch` or `axios` directly.

```ts
// features/shifts/api/shifts-api.ts
export function getShifts(filters: ShiftListFilters = {}) {
  // builds query string, calls apiClient
}
```

### P4 — `lib/api-client.ts` is the only HTTP client

Never add `axios`, `ky`, `swr`, or other HTTP libraries. Never call `fetch()` directly. All API calls go through `apiClient<T>(path, options?)`.

### P5 — Nested section pattern

Nested entity sections (evaluations, items) are rendered by the parent detail component using `SectionShell`. They receive the parent ID as a prop and an `onCreated` callback.

The form is toggled via an "Add [Item]" button in the section header — it is not permanently visible. When `isFormOpen = false`: the button is visible. When `isFormOpen = true`: the form renders and the button hides. The form receives an `onCancel` prop to collapse itself on cancel or after a successful submit.

A status guard may additionally suppress both button and form — for example, when the parent entity is closed, the "Add" button is hidden and replaced by an explanatory message ("Defects cannot be added to a closed quality check." / "Items cannot be added to a closed NCR report.").

### P6 — Feature-specific status badge components

Each feature with a status field has its own badge component (e.g., `ShiftReportStatusBadge`, `ProductionOrderStatusBadge`). Badge components use a `Record<Status, {background, color}>` for colors and a `Record<Status, string>` labels Record for human-readable display. They spread `sharedStyles.badge` as the base style.

Do not create a shared generic `StatusBadge` component — keep badges feature-specific so each feature can evolve its status set independently.

### P7 — Loading / empty / error / submit UX baseline

Every list page and detail page implements all four states:

| State | Implementation |
|-------|---------------|
| Loading | `sharedStyles.state` div with "Loading {entity}..." text |
| Empty | `sharedStyles.state` section with heading + CTA link |
| Error | `sharedStyles.error` div with `role="alert"` + "Try again" button |
| Submit | Button disabled + label changes to "Creating..." / "Submitting..." / "Ending..." |

List pages with user-triggered reload use `isMountedRef` + `useCallback`. Simple single-load pages use `isMounted` boolean inside `useEffect`.

---

## D. Status Badge Colors

All badges spread `sharedStyles.badge` and override background + color. Canonical hex values:

| Semantic | Background | Text | Used by |
|----------|-----------|------|---------|
| Gray (draft/inactive/closed/recorded/cancelled) | `#f3f4f6` | `#4b5563` | All |
| Blue (submitted/released/verified/confirmed) | `#dbeafe` | `#1e40af` | All |
| Green (approved/completed/active/posted/accepted) | `#dcfce7` | `#166534` | All |
| Amber (in_progress/under_maintenance/needs_modification) | `#fef3c7` | `#92400e` | prod-orders, work-centers |
| Red (open/urgent/rejected/cancelled) | `#fee2e2` | `#991b1b` | downtime, prod-orders |
| Purple (converted/evaluated/contamination) | `#ede9fe` | `#5b21b6` | commercial-orders, waste |
| Orange (material downtime/startup waste) | `#ffedd5` | `#9a3412` | downtime, waste |
| Yellow (manpower/trim waste) | `#fef9c3` | `#854d0e` | downtime, waste |
| Teal (setup downtime) | `#ccfbf1` | `#0f766e` | downtime |
| Stone (material_loss waste) | `#e7e5e4` | `#44403c` | waste |

**Downtime open badge is all-caps "OPEN"** — the only all-caps badge in the system. Intentional for urgency.

**FE6 Quality/NCR badge colors — actual implemented values (see Section F for full badge details):**

- `QualityCheckStatusBadge`: open=gray, under_inspection=amber, closed=green
- `QualityCheckResultBadge`: accepted=green, rejected=red, conditional_accept=amber, needs_reinspection=orange, null/Pending=gray
- `NcrStatusBadge`: draft=gray, open=blue, under_review=amber, closed=green
- `DispositionBadge` (decision): hold=amber, scrap=red, rework=blue, return_to_process=gray
- `DispositionStatusBadge` (execution state): pending=orange (`#ffedd5`/`#9a3412`), executed=green

---

## E. What Came Next — FE6 (Done)

Sprint 6 delivered all five Quality/NCR UI features. All are complete and validated (REV6-001 to REV6-005).

| Task | Feature built | Status |
|------|--------------|--------|
| FE6-001 | Quality Checks — list / detail / create / status lifecycle | ✓ Done |
| FE6-002 | Quality Defects — nested section in QualityCheckDetail | ✓ Done |
| FE6-003 | Quality Rejections — list / detail / create / Mark as Executed | ✓ Done |
| FE6-004 | NCR Reports — list / detail / create / Open/Review/Close progression | ✓ Done |
| FE6-005 | NCR Items — nested section in NcrReportDetail (replaced FE6-004 placeholder) | ✓ Done |

**What came next:** Sprint 7 delivered CAPA UI. See Section G and `next-steps.md`.

---

## F. Quality/NCR Pattern Reference (Sprint 6)

Sprint 6 design decisions — must be respected in FE7:

| # | Decision | Documented in |
|---|----------|--------------|
| FE6-D1 | status and result are SEPARATE fields in QualityCheck — two distinct badges always | F1 |
| FE6-D2 | inspection_code auto-generated (QI-YYYY-NNNN) — never a form input | F1 |
| FE6-D3 | qty_accepted + qty_rejected must equal qty_inspected — client-side validation | F1 |
| FE6-D4 | check_type = business type — 6 values, no measurement method values | F1 |
| FE6-D5 | quality_check_id required in QualityDefect — non-nullable | F2 |
| FE6-D6 | defect_count required — default=1, validates >= 1 | F2 |
| FE6-D7 | QualityDefect has NO status field — static fact record | F2, F6 |
| FE6-D8 | DefectCategory 11 values — includes thickness/winding/color/finish | F2 |
| FE6-D9 | rejection_notes required — Quality PRD BR-02 | F3 |
| FE6-D10 | disposition vs disposition_status — TWO separate fields, TWO badge components | F3 |
| FE6-D11 | report_number auto-generated (NCR-YYYY-NNNN) — never a form input | F4 |
| FE6-D12 | NCR status set via action buttons on detail page — not via create form select | F4 |
| FE6-D13 | NCR items status guard — closed report blocks new items with explicit message | F4, F5 |
| FE6-D14 | line_no auto-assigned (#1, #2...) — never a user input, never a form field | F5 |
| FE6-D15 | NcrItem has NO status field — static fact record | F5, F6 |

---

### F1 — Quality Checks Pattern

**Mirror:** `features/production-orders/`
**Component count:** 5

| Component | Purpose |
|-----------|---------|
| `QualityChecksList` | List with 5 filters; two separate badge columns (Status + Result) |
| `QualityCheckDetail` | Detail with action buttons + QualityDefectsList nested section |
| `QualityCheckForm` | Create form; inspection_code absent; qty constraint validation |
| `QualityCheckStatusBadge` | open (gray), under_inspection (amber), closed (green) |
| `QualityCheckResultBadge` | accepted (green), rejected (red), conditional_accept (amber), needs_reinspection (orange), null/Pending (gray) |

**Critical — two badge components (FE6-D1):** `status` = lifecycle stage. `result` = quality outcome. They are separate fields on the model and must always show as two separate badges in both list columns and detail grid cells. Never merge them into one badge.

**Status transitions — action buttons on detail page (not form selects):**
- `status = open` → "Start Inspection" button → PATCH `{ status: "under_inspection" }`
- `status = under_inspection` → result select + "Close Inspection" button → PATCH `{ status: "closed", result: selectedResult }`
- `status = closed` → "Closed inspections are final." notice, no buttons

"Close Inspection" is `disabled={!selectedResult}` with tooltip "Select a result first". The handler also has an early-return guard. This prevents permanently incomplete quality records (FE6-D1).

**inspection_code (FE6-D2):** Never a form input. Show "Inspection code: Auto-generated" notice in form. Display as read-only `DetailItem` on detail page.

**Quantity constraint (FE6-D3):** `qty_accepted + qty_rejected` must equal `qty_inspected`. Client-side `validateQuantities()` runs before submit and shows inline error. Both fields are required.

**check_type (FE6-D4):** 6 business values only — `in_process_inspection`, `finished_product_inspection`, `sample_inspection`, `reinspection`, `issue_triggered`, `general`. No measurement method values (no `visual`, `dimension`, `tensile`).

**API filter param:** `check_status` (not `status`) — this is the backend query parameter name. The frontend filter state uses `status` internally but maps to `check_status` when building the query string.

---

### F2 — Quality Defects Pattern

**Mirror:** nested section (`SampleEvaluationsList` + `SampleEvaluationForm` pattern from Sprint 5)
**Component count:** 4

| Component | Purpose |
|-----------|---------|
| `QualityDefectsList` | Nested section; "Add Defect" toggle; status guard for closed checks |
| `QualityDefectForm` | Inline create; `qualityCheckId` from prop, never typed by user |
| `DefectSeverityBadge` | minor (gray), major (amber), critical (RED `#fee2e2`/`#991b1b`) |
| `DefectCategoryBadge` | 11 categories with formatted labels |

**NO StatusBadge (FE6-D7):** QualityDefect is a static fact record. No lifecycle, no status field, no action buttons. Do not add status to QualityDefect in FE7.

**Nested inside:** `/quality-checks/[id]` as a section at the bottom of `QualityCheckDetail`:
```tsx
<QualityDefectsList qualityCheckId={check.id} checkStatus={check.status} />
```

**quality_check_id (FE6-D5):** Comes from the parent `qualityCheckId` prop — never typed by the user. Passed as the URL path parameter to `POST /quality-checks/${qualityCheckId}/defects`.

**Status guard:** `isClosed = checkStatus === "closed"`. When closed: "Add Defect" button hidden, form suppressed, message shown: "Defects cannot be added to a closed quality check." When open: "Add Defect" button toggles `isFormOpen`. Form receives `onCancel` to close itself.

**DefectCategory — 11 values (FE6-D8):** `dimension`, `thickness`, `surface`, `color`, `strength`, `winding`, `weight`, `packaging`, `labeling`, `finish`, `other`. All 11 must be present in the select. Never reduce this list — thickness/winding/color/finish are production-specific values that the business requires.

**defect_count (FE6-D6):** Required, default=1, validates `>= 1` with inline error "Defect count must be at least 1".

**critical severity (FE6-D8):** RED badge (`#fee2e2`/`#991b1b`) by design. Intentionally alarming. Do not soften this to a neutral color.

**API:** `getDefectsByCheck(qualityCheckId)`, `createDefect(qualityCheckId, payload)` — both use nested route `/quality-checks/${id}/defects`.

---

### F3 — Quality Rejections Pattern

**Mirror:** `features/quality-checks/` (list / detail / create + action button)
**Component count:** 5

| Component | Purpose |
|-----------|---------|
| `QualityRejectionsList` | List with 5 filters; shows DispositionBadge + DispositionStatusBadge |
| `QualityRejectionDetail` | Detail with "Mark as Executed" action button |
| `QualityRejectionForm` | Create form; rejection_notes prominently required |
| `DispositionBadge` | The DECISION: hold (amber), scrap (red), rework (blue), return_to_process (gray) |
| `DispositionStatusBadge` | The EXECUTION STATE: pending (orange), executed (green) |

**Critical — two badge components (FE6-D10):** `disposition` = what to do with the rejected material (the decision). `disposition_status` = whether that decision has been carried out (the execution state). These are semantically different fields that serve different audit purposes. Never merge them.

**rejection_notes required (FE6-D9):** Labeled "Rejection Justification (required)". Inline error: "Rejection justification is required". Submission blocked without notes. This is Quality PRD BR-02 — a rejection without justification has zero analytical value.

**8 RejectionReason values:** `failed_quality_check`, `critical_defect`, `out_of_spec`, `dimension_failure`, `surface_failure`, `packaging_failure`, `labeling_issue`, `other`. All 8 must be present in the form select.

**disposition_status auto-set to pending:** Backend sets `pending` on create. Never in the form. After create, detail page loads showing orange "Pending" badge and "Mark as Executed" button.

**"Mark as Executed" action button:** Only rendered when `disposition_status === "pending"`. After click: PATCH `{ disposition_status: "executed" }` → `setRejection(updatedRejection)` → button disappears, green "Executed" badge appears, "This disposition has been executed." shown.

**API:** `getQualityRejections`, `getQualityRejectionById`, `createQualityRejection`, `updateDispositionStatus(id)` — `updateDispositionStatus` uses a default payload `{ disposition_status: "executed" }`, no user input required.

---

### F4 — NCR Reports Pattern

**Mirror:** `features/shift-reports/`
**Component count:** 5

| Component | Purpose |
|-----------|---------|
| `NcrReportsList` | List with 4 filters; NcrSourceTypeBadge + NcrStatusBadge |
| `NcrReportDetail` | Detail with 3 action buttons + NcrItemsList nested section |
| `NcrReportForm` | Create form; report_number absent; title + description required |
| `NcrStatusBadge` | draft (gray), open (blue), under_review (amber), closed (green) |
| `NcrSourceTypeBadge` | 6 source type values with feature-specific colors |

**report_number auto-generated (FE6-D11):** Backend assigns NCR-YYYY-NNNN on create. Never a form input. Show "Report number: Auto-generated" notice in form. Display as `DetailItem label="Report Number"` on detail page.

**Status auto-set to draft on create (FE6-D12):** No status select in the create form. All transitions happen via action buttons on the detail page.

**Status action buttons — exclusive per state:**
- `status = "draft"` → "Open Report" → PATCH `{ status: "open" }` → `setReport(updatedReport)`
- `status = "open"` → "Start Review" → PATCH `{ status: "under_review" }` → `setReport(updatedReport)`
- `status = "under_review"` → "Close Report" → PATCH `{ status: "closed" }` → `setReport(updatedReport)`
- `status = "closed"` → "Report is closed." notice, no button

Each button is rendered in its own `{report.status === "..." ? ... : null}` conditional block. In-place `setReport` refresh — no redirect between transitions.

**Navigation:** NCR Reports in the Quality/NCR nav section alongside "Quality Checks" and "Rejections". Dashboard has NCR Reports entry.

**API:** `getNcrReports`, `getNcrReportById`, `createNcrReport`, `updateNcrReportStatus`
**API filter param:** `ncr_status` (not `status`) — the backend query parameter name.

---

### F5 — NCR Items Pattern

**Mirror:** nested section (`ProductionOrderItemsList` + `ProductionOrderItemForm` pattern from Sprint 5)
**Component count:** 2 — the simplest nested section in the system

| Component | Purpose |
|-----------|---------|
| `NcrItemsList` | Nested section; "Add Item" toggle; status guard for closed reports; expand/collapse for long descriptions |
| `NcrItemForm` | Inline create; `ncrReportId` from prop |

**NO StatusBadge (FE6-D15):** NcrItem is a static fact record. No lifecycle, no status field, no action buttons. Do not add status to NcrItem in FE7.

**Nested inside:** `/non-conformance-reports/[id]` at the bottom of `NcrReportDetail`:
```tsx
<NcrItemsList ncrReportId={report.id} reportStatus={report.status} />
```

**Status guard (FE6-D13):** `isClosed = reportStatus === "closed"`. When closed:
- "Add Item" button not rendered
- Message: "Items cannot be added to a closed NCR report."
- Form also suppressed

When open: "Add Item" toggles `isFormOpen`. Form receives `onCancel` to close itself after submit or cancel.

**line_no auto-assigned (FE6-D14):** Backend assigns max+1 per report on create. Shown as `#1`, `#2` indigo badges. Never a form field. Note "Line number is auto-assigned" shown in form.

**Required fields:** `item_name` and `issue_description` — both required with inline errors. All other fields optional.

**Expand/collapse:** Long `issue_description` values (> 180 chars) have a per-item "Show more / Show less" toggle. Uses `expandedItemIds: Set<string>` + `toggleDescription(id)` pattern.

**The FE6-004 placeholder was replaced in FE6-005.** The `NcrReportDetail` previously had a `SectionShell` placeholder for NCR items. That was replaced with the real `<NcrItemsList>` component in FE6-005.

**API:** `getItemsByReport(reportId)`, `createItem(reportId, payload)` — nested route `/non-conformance-reports/${id}/items`.

---

### F6 — Static Records Rule in Quality/NCR

**`QualityDefect` and `NcrItem` are STATIC FACT RECORDS.**

They have:
- No `status` field
- No action buttons
- No lifecycle progression
- No "Close", "Resolve", "Approve", or "Submit" buttons

**Do NOT add status or lifecycle to these entities in FE7.**

This is a deliberate design decision (FE6-D7, FE6-D15). These entities record facts that happened. They are not workflow entities. The same pattern applies to `WasteRecord` from Sprint 3 (Section B, D6).

**The correct CAPA pattern:**
CAPA corrective actions will be NEW entities that REFERENCE quality rejections (`quality_rejection_id`) and NCR reports (`ncr_report_id`). CAPA does not extend or modify `QualityDefect` or `NcrItem`.

Corrective actions have their own lifecycle (open → in_progress → closed). That lifecycle lives on the corrective action entity, not on defects or items.

**Identifying static records vs lifecycle entities:**

| Entity | Type | Why |
|--------|------|-----|
| `WasteRecord` | Static | Operational fact — waste happened |
| `QualityDefect` | Static | Inspection fact — defect was found |
| `NcrItem` | Static | Case fact — item is affected |
| `QualityCheck` | Lifecycle | Inspection has stages (open → closed) |
| `NcrReport` | Lifecycle | Case has stages (draft → closed) |
| `QualityRejection` | Lifecycle | Decision has execution state (pending → executed) |

---

## G. CAPA Pattern Reference (Sprint 7)

Sprint 7 delivered the CAPA frontend UI baseline. CAPA is implemented as its own feature group while keeping source references to Quality/NCR as plain contextual links.

| Feature | Pattern | Route behavior |
|---------|---------|----------------|
| Corrective Actions | List / create / detail with status action buttons | Standalone routes under `/corrective-actions` |
| Action Follow-ups | Nested repeatable section with inline create form | No standalone route; lives in Corrective Action detail |
| Closure Verifications | Singleton nested section with inline create form and read-only display | No standalone route; lives in Corrective Action detail |

### FE7-D1 — Corrective Action lifecycle

Corrective actions use detail-page action buttons for status transitions:

- `open` -> "Start Action"
- `in_progress` -> "Complete Action"
- `completed` -> "Close Action"
- `closed` -> read-only closed notice

Do not add a status select to the create form. Status starts server-side and changes through detail-page buttons.

### FE7-D2 — CAPA source context

Corrective actions can reference Quality/NCR source records. Source context is displayed on the detail page.

Sources with standalone pages are links:

- `quality_rejection` -> `/quality-rejections/{id}`
- `ncr_report` -> `/non-conformance-reports/{id}`

Sources without standalone pages remain clear text:

- `quality_defect`
- `ncr_item`

Do not add CAPA fields to Quality Defects or NCR Items. CAPA owns corrective-action workflow; Quality/NCR records remain source context.

### FE7-D3 — Follow-ups stay nested

Action follow-ups are repeatable child records inside Corrective Action detail. They use the same nested-section pattern as NCR Items:

- `SectionShell`
- "Add Follow-up" toggle
- inline form
- refresh list after create
- closed-action guard

Follow-ups do not have standalone pages in v0.1.

### FE7-D4 — Closure verification stays nested and singleton

Closure verification is a singleton section inside Corrective Action detail. When no verification exists and the action is eligible, show the form inline. After creation, show the saved verification read-only.

The section is available when the action is `in_progress` or `completed`. When the action is `closed` without verification, show a clear state message.

### FE7-D5 — CAPA UX baseline

CAPA follows the same v0.1 frontend baseline:

- feature-local API files using `apiClient`
- feature-local types and components
- thin Next.js pages
- loading, empty, error, retry, and submit states
- feature-specific badge components
- no global state management library
- no generic shared status badge framework
