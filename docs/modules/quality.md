# Quality Module

**Status:** Sprint 4 — Baseline Complete (5 entities)

The quality module owns the inspection and non-conformance chain: recording quality checks, logging defects, formalizing rejections, and opening non-conformance cases with line items. All data is org-scoped via `TenantContext` (ADR-001). No imports from `app.production`, `app.commercial`, or `app.foundation` models are allowed — only `app.core.*` and `app.quality.*` (ADR-004).

**NCR co-location note (D10):** NonConformanceReport and NonConformanceItem live inside `backend/app/quality/` — not in a separate `ncr/` module. This is a deliberate v0.1 scaffold decision. The NCR domain is small enough to co-locate with Quality. A future migration to `backend/app/ncr/` would be a pure file move with no business logic change.

---

## Entities and domain objects

### QualityCheck
An inspection event. The root entity of the quality chain.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → foundation_organizations | Tenant scope |
| inspection_code | String(32) | Auto-generated `QI-YYYY-NNNN` — never a caller input (D3) |
| check_datetime | DateTime(tz) | When the inspection occurred |
| check_type | Enum | Business type — see approved values below (D4) |
| status | Enum `open/under_inspection/closed` | Lifecycle state — default `open` (D1) |
| result | Enum `accepted/rejected/conditional_accept/needs_reinspection` nullable | Inspection outcome — null until set (D1) |
| qty_inspected | Integer | Total units submitted — must be `> 0` |
| qty_accepted | Integer | Units that passed — must be `>= 0` |
| qty_rejected | Integer | Units that failed — must be `>= 0` |
| production_order_id | UUID nullable | Plain UUID ref — no FK (ADR-004) |
| production_order_item_id | UUID nullable | Plain UUID ref — no FK |
| shift_report_id | UUID nullable | Plain UUID ref — no FK |
| notes | Text nullable | |
| checked_by_user_id | UUID FK → foundation_users (DB-level only) | |

**D1 — status vs result (two separate fields):**
- `status` tracks the inspection lifecycle: `open` → `under_inspection` → `closed`
- `result` records the inspection outcome: `accepted` / `rejected` / `conditional_accept` / `needs_reinspection`
- Setting status to `closed` requires `result` to be set (enforced in service — returns 400 if missing)
- These are never combined into a single `result_status` field

**D2 — Quantity constraint:**
`qty_accepted + qty_rejected = qty_inspected` must hold at all times.
- Enforced on create by Pydantic `model_validator(mode="after")` → 422
- Enforced on update by service after merging partial values → 400

**D3 — inspection_code auto-generation:**
Service generates `QI-{year}-{sequence:04d}`. The field is absent from the create schema. A 20-attempt retry loop handles race conditions. Unique per org: `UNIQUE(organization_id, inspection_code)` at DB level.

**D4 — check_type approved values (business types, NOT measurement methods):**
`in_process_inspection` / `finished_product_inspection` / `sample_inspection` / `reinspection` / `issue_triggered` / `general`

Do NOT use: `visual`, `dimension`, `tensile`, `weight`. Those describe measurement methods and belong in a future measurement-detail table, not in the check type.

### QualityDefect
A specific defect found during a quality check. Requires a parent check.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK | Direct tenant scope (dual isolation with parent check) |
| quality_check_id | UUID FK → quality_checks | Required — not nullable (D5) |
| defect_date | Date | |
| defect_category | Enum (11 values) | See enum reference below (D7) |
| severity | Enum `minor/major/critical` | |
| defect_count | Integer | Default 1, must be `> 0` (D6) |
| description | String(min=1) | Required |
| notes | Text nullable | |
| detected_by_user_id | UUID FK → foundation_users (DB-level only) | |

**D5 — quality_check_id required:**
`QualityDefect` is created via the nested route `POST /quality-checks/{check_id}/defects`. The `check_id` comes from the URL path and is validated against the caller's org. There is no way to create a defect without a valid parent check in the same org.

**D6 — defect_count:**
Defaults to 1 (`Field(default=1, gt=0)`). Omitting it from the create body produces count=1. Zero or negative counts are rejected with 422.

**D14 — No status field:**
`QualityDefect` intentionally has no status field in v0.1. A defect is a static factual observation — it was found, measured, and recorded. It does not have a lifecycle. Defect resolution tracking belongs to the downstream `QualityRejection` and future CAPA entities.

**Isolation note:**
`QualityDefect` has BOTH `organization_id` (direct) AND a parent JOIN check in `get_by_id`. This is dual isolation — more secure than strictly required, but correct.

### QualityRejection
A formal rejection decision following an inspection or defect finding.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK | Tenant scope |
| quality_check_id | UUID nullable | Optional reference to the triggering check |
| quality_defect_id | UUID nullable | Optional reference to the triggering defect |
| production_order_item_id | UUID nullable | Plain UUID ref — no FK |
| rejection_date | Date | |
| rejection_reason | Enum (8 values) | |
| rejection_notes | String(min=1) | **Required** — Quality PRD BR-02 (D8) |
| disposition | Enum `hold/scrap/rework/return_to_process` | Required |
| disposition_status | Enum `pending/executed` | Auto-set to `pending` (D9) |
| quantity_rejected | Integer | Must be `> 0` |
| unit | String(min=1) | |
| rejected_by_user_id | UUID FK → foundation_users (DB-level only) | |

**D8 — rejection_notes required:**
`rejection_notes = Field(min_length=1)`. Empty string returns 422. Whitespace-only string (`"   "`) is caught in the service layer and returns 400. This rule is Quality PRD BR-02.

**D9 — disposition vs disposition_status (two separate fields):**
- `disposition` = the decided action (`hold`, `scrap`, `rework`, `return_to_process`) — required on create
- `disposition_status` = whether the action has been carried out (`pending`, `executed`) — auto-set to `pending` on creation, updateable via PATCH

**Coherence rule:**
If both `quality_check_id` and `quality_defect_id` are provided, the defect must belong to the referenced check. This prevents cross-check incoherent references within the same org.

### NonConformanceReport
A formal non-conformance case. Header entity for NCR items.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK | Tenant scope |
| report_number | String(32) | Auto-generated `NCR-YYYY-NNNN` — never a caller input (D11) |
| report_date | Date | |
| source_type | Enum (6 values) | |
| report_type | Enum (6 values) | |
| status | Enum `draft/open/under_review/closed` | Auto-set to `draft` on creation (D11) |
| title | String(min=1, max=255) | Required |
| description | String(min=1) | Required |
| reference_code | String(max=255) nullable | Optional batch/lot reference |
| quality_check_id | UUID nullable | Optional plain UUID ref to triggering check |
| quality_rejection_id | UUID nullable | Optional plain UUID ref to triggering rejection |
| detected_by_user_id | UUID FK → foundation_users (DB-level only) | |

**D11 — report_number auto-generation:**
Same pattern as inspection_code: `NCR-{year}-{sequence:04d}`, 20-attempt retry, unique per org: `UNIQUE(organization_id, report_number)`.

**NCR status lifecycle:**
`draft` → `open` → `under_review` → `closed`

Once `closed`, the report cannot be reopened (enforced in service — returns 400). Items cannot be created or modified on a closed report (D12).

**Boundary note:**
`quality_check_id` and `quality_rejection_id` are plain UUID references with no FK constraints. The service validates org ownership when provided, but does not follow cross-module FKs.

### NonConformanceItem
A line item within an NCR case. Represents a specific material, product batch, or sub-component affected by the non-conformance.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| non_conformance_report_id | UUID FK → non_conformance_reports | Required |
| line_no | Integer | Auto-assigned if not provided (D13) |
| item_reference | String(max=255) nullable | Optional batch/lot/PN reference |
| item_name | String(min=1, max=255) | Required |
| quantity_affected | Numeric(14,2) nullable | Nullable — quantity may be unknown at case open |
| unit | String(max=32) nullable | |
| issue_description | String(min=1) | Required |
| notes | Text nullable | |

**D12 — Status guard on CLOSED report:**
`create_item` and `update_item` both call `_validate_open_parent_report`. The guard checks org ownership first, then checks `report.status == NCRStatus.CLOSED` — returns 400 if closed. This order prevents status guard from leaking information about foreign-org reports.

**D13 — line_no auto-assignment:**
`line_no = (max_line_no(report_id) or 0) + 1`. Unique per report: `UNIQUE(non_conformance_report_id, line_no)` at DB level. Explicit override allowed — providing `line_no` in the request body uses that value.

**D14 — No status field:**
`NonConformanceItem` intentionally has no status field. The parent report's status governs what can be done with items. Per-item status tracking is deferred to CAPA.

**Tenant isolation (cascaded):**
`NonConformanceItem` has NO `organization_id` column. Isolation is cascaded: `get_by_id(org_id, item_id)` JOINs `NonConformanceReport` and filters by `NonConformanceReport.organization_id`.

---

## Enum reference

| Enum | Values |
|------|--------|
| QualityCheckType | `in_process_inspection` / `finished_product_inspection` / `sample_inspection` / `reinspection` / `issue_triggered` / `general` |
| QualityCheckStatus | `open` / `under_inspection` / `closed` |
| QualityCheckResult | `accepted` / `rejected` / `conditional_accept` / `needs_reinspection` |
| DefectCategory (11) | `dimension` / `thickness` / `surface` / `color` / `strength` / `winding` / `weight` / `packaging` / `labeling` / `finish` / `other` |
| DefectSeverity | `minor` / `major` / `critical` |
| RejectionReason | `failed_quality_check` / `critical_defect` / `out_of_spec` / `dimension_failure` / `surface_failure` / `packaging_failure` / `labeling_issue` / `other` |
| Disposition | `hold` / `scrap` / `rework` / `return_to_process` |
| DispositionStatus | `pending` / `executed` |
| NCRSourceType | `internal_production` / `incoming_material` / `supplier` / `warehouse` / `customer_return` / `other` |
| NCRReportType | `material_non_conformance` / `product_non_conformance` / `process_non_conformance` / `packaging_non_conformance` / `documentation_non_conformance` / `other` |
| NCRStatus | `draft` / `open` / `under_review` / `closed` |

---

## Tenant isolation pattern

Three levels of isolation enforce ADR-001 across all 5 entities:

1. **Entity isolation (Level 1)** — `get_by_id(organization_id, entity_id)` dual filter on QualityCheck, QualityRejection, NonConformanceReport.
2. **Cross-reference validation (Level 2)** — Service layer validates all optional FK references (quality_check_id, quality_defect_id, quality_rejection_id) belong to the same org before insert.
3. **Cascaded isolation (Level 3)** — `QualityDefect` and `NonConformanceItem` carry no direct `organization_id`; repositories JOIN the parent entity and filter by parent's `organization_id`.

`organization_id` is never accepted from the caller — always read from `TenantContext` (the authenticated JWT).

---

## Module boundary rules (ADR-004)

- No Python imports from `app.production.*`, `app.commercial.*`, or `app.foundation.infrastructure.models`
- Production references (`production_order_id`, `production_order_item_id`) are plain `UUID` columns with no FK constraints. `production_output_id` was removed with the legacy production outputs (migration `f6a1b2h5`).
- Cross-module existence checks use raw `text()` SQL — no Production model imports
- `created_by_user_id` / `checked_by_user_id` / `detected_by_user_id` / `rejected_by_user_id` use `ForeignKey("foundation_users.id")` at DB level only — no import of the Foundation `User` model into Quality code

---

## Implemented routes

All routes require a valid Bearer token. All results are scoped to the caller's `organization_id`.

See [docs/api/quality.md](../api/quality.md) for the full endpoint list.
