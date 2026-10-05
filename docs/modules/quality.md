# Quality Module

**Status:** QUAL-001 lifecycle and close gate; QUAL-REPORT-001 report center; QUAL-SPEC-001 specifications and measurements; QUAL-COA-001 certificates of analysis. Defects and NCR unchanged

The quality module owns the inspection and non-conformance chain: recording quality checks, logging defects, formalizing rejections, and opening non-conformance cases with line items. All data is org-scoped via `TenantContext` (ADR-001). No imports from `app.production`, `app.commercial`, or `app.foundation` models are allowed — only `app.core.*` and `app.quality.*` (ADR-004).

**NCR co-location note (D10):** NonConformanceReport and NonConformanceItem live inside `backend/app/quality/` — not in a separate `ncr/` module. This is a deliberate v0.1 scaffold decision. The NCR domain is small enough to co-locate with Quality. A future migration to `backend/app/ncr/` would be a pure file move with no business logic change.

---

## Entities and domain objects

### QualityCheck (QUAL-001)
An inspection of a production lot (an order, optionally one line) or of a commercial sample.

| Column | Type | Notes |
|--------|------|-------|
| inspection_code | String(32) | `QI-YYYY-NNNN` from the locked `quality_code_counters` row — never a caller input |
| check_type | Enum | `in_process_inspection` / `finished_product_inspection` / `reinspection` need an order; `sample_inspection` needs a sample; `issue_triggered` / `general` may name an order |
| status | Enum `open/under_inspection/closed/cancelled` | `closed` and `cancelled` are final |
| result | Enum nullable | Set only by closing |
| qty_inspected / qty_accepted / qty_rejected | Numeric(14,3) | In `unit`; accepted + rejected = inspected when closing |
| unit | String nullable | Taken from the order line, the order or the sample |
| production_order_id / production_order_item_id | UUID nullable | Order must be `in_progress`, `on_hold` or `completed` |
| sample_id | UUID nullable | Commercial sample, read through the shared table |
| started_at, closed_at, closed_by_user_id, cancel_reason | | Lifecycle facts |

**Lifecycle** (rules in `quality/domain/rules.py`, single writer `application/check_service.py`):
`open` → start → `under_inspection` → close(result, quantities) → `closed`; `open`/`under_inspection` → cancel(reason) → `cancelled`.
Closing may skip the start. Edits are allowed only while the check is open or under inspection; the order cannot change once set.

**Closing rules:** inspected > 0; no negative quantity; accepted + rejected = inspected; `accepted` cannot carry a rejected quantity and `rejected` needs one.
A rejected quantity above zero opens a **pending QualityRejection** for it in the same transaction (reason given by the inspector, default `failed_quality_check`).

Every transition writes `quality_status_history` (entity, action, from/to, reason, actor) and the tenant activity log.

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

### QualityRejection (QUAL-001)
A rejected quantity and the decision on what to do with it.

| Column | Type | Notes |
|--------|------|-------|
| rejection_code | String(32) | `QR-YYYY-NNNN`, unique per organization |
| quality_check_id | UUID nullable | The closed check it came from |
| production_order_id / production_order_item_id | UUID | Copied from the check, or named for a manual rejection |
| quantity_rejected | Numeric(14,3) | > 0; the rejections of one check never exceed its rejected quantity |
| rejection_reason, rejection_notes | | Notes required (BR-02) |
| disposition | Enum nullable | `hold` / `scrap` / `rework` / `return_to_process` / `use_as_is`; null until decided |
| disposition_status | Enum `pending/decided/executed` | |
| decided_*, decision_notes, concession_approved_by | | `use_as_is` needs both the approver and the justification |
| executed_*, execution_notes | | |

**Lifecycle:** `pending` → decide → `decided` → execute → `executed` (final). The decision may change while `decided`.
`hold` is a quarantine, not a final decision: it cannot be executed and must be changed first. Editing (date, reason, notes, quantity) is allowed only while `pending`.

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
| QualityCheckStatus | `open` / `under_inspection` / `closed` / `cancelled` |
| QualityCheckResult | `accepted` / `rejected` / `conditional_accept` / `needs_reinspection` |
| DefectCategory (11) | `dimension` / `thickness` / `surface` / `color` / `strength` / `winding` / `weight` / `packaging` / `labeling` / `finish` / `other` |
| DefectSeverity | `minor` / `major` / `critical` |
| RejectionReason | `failed_quality_check` / `critical_defect` / `out_of_spec` / `dimension_failure` / `surface_failure` / `packaging_failure` / `labeling_issue` / `other` |
| Disposition | `hold` / `scrap` / `rework` / `return_to_process` / `use_as_is` |
| DispositionStatus | `pending` / `decided` / `executed` |
| NCRSourceType | `internal_production` / `incoming_material` / `supplier` / `warehouse` / `customer_return` / `other` |
| NCRReportType | `material_non_conformance` / `product_non_conformance` / `process_non_conformance` / `packaging_non_conformance` / `documentation_non_conformance` / `other` |
| NCRStatus | `draft` / `open` / `under_review` / `closed` |

---

## Production order close gate (QUAL-001)

Production asks the composition-root guards before closing an order (`app/core/interfaces/order_close_guards.py`; quality registers
`rejection_service.close_blockers` in `main.py`, so production never imports quality). Under the order lock it raises
`409 {"code": "CLOSE_BLOCKED", "blockers": [{"code", "count"}]}` when the order has:

- checks still `open` or `under_inspection` → `QUALITY_CHECKS_OPEN`
- rejections `pending`, or `decided` as `hold` → `QUALITY_REJECTIONS_UNRESOLVED`

The order page shows a quality section with these counts, and the status panel lists the blockers.

## Permissions

Per action, one source: `quality/domain/permissions.py`, mirrored by `frontend/src/lib/quality-permissions.ts`
(`tests/quality-permissions.test.mjs` keeps them identical). Every quality route declares one; screens hide what the user cannot do.

| Resource | Actions |
|----------|---------|
| `quality:quality_checks` | read, create, update, start, close, cancel, measure |
| `quality:rejections` | read, create, update, decide, execute |
| `quality:quality_defects` | read, create, update |
| `quality:ncr_reports` | read, create, update (NCR items use update) |
| `quality:specifications` | read, create, update, activate (test parameters and product specifications) |
| `quality:certificates` | read, create, update, issue, revoke (certificates of analysis) |

Migration `f6a1b2i6` split the old `write` grants into these actions (backup `quality_rbac_i6_backup`) and gave `quality_manager`
`production:production_orders:read`. Records carry an `actions` list computed by the server for the current user.

---

## Specifications and measurements (QUAL-SPEC-001)

Rules: `quality/domain/specifications.py`. Writers: `application/specification_service.py` (parameters, specifications) and
`application/measurement_service.py` (a check's plan and readings).

- **Test parameters** (`quality_test_parameters`): code, Arabic and English names, kind (`numeric` in a unit, or `attribute`
  judged conforming / not conforming), unit, default method / equipment. "Add the standard parameters" adds the strapping-band set
  once (width, thickness, net roll weight, roll length, break strength, elongation, color, embossing, winding, surface, core / packaging).
  The kind never changes after creation.
- **Product specifications** (`quality_specifications`, the TDS): number (e.g. `ROF-TDS-PP-001`), revision, title, product (as written on
  production orders), grade. Document control: `draft` → activate → `active` (one per number, partial unique index) → `superseded` when a
  newer revision is activated. Only a draft is edited; "new revision" copies the lines into a draft with revision + 1.
- **Lines** (`quality_specification_lines`), one per parameter:
  - numeric: target `fixed`, `order_line` (the order line's specification key, e.g. `width_mm`) or `none`; lower = minimum, else
    target − tolerance; upper = maximum, else target + tolerance; either side may be open; readings required per parameter;
  - attribute: requirement and acceptance wording;
  - method / equipment overrides the parameter's.
- **Measurement plan** (`quality_check_measurements`): a new inspection takes its product's specification in force automatically when
  exactly one exists; otherwise the inspector applies one (`POST /quality-checks/{id}/plan`). Lines are copied with their limits resolved
  for the lot (the order line's values, else the order's, or the sample's requested specification), and the check keeps
  `specification_code` / `specification_revision`. Later revisions never change it. A plan is replaced only before anything is measured
  (`MEASUREMENTS_STARTED`); a lot lacking a value the specification needs answers `LOT_SPEC_VALUE_MISSING`.
- **Any specification in force** can be applied (QUAL-SPEC-002): `GET /quality-checks/{id}/specifications` lists those for the order's
  product first (`matches_product`), then the others, with the lot values each still needs (`missing_keys`). Automatic application still
  happens only for exactly one specification of the product.
- **Missing lot values**: when the order line lacks a value a specification takes from it (e.g. `width_mm`), the inspector enters it with
  the plan (`lot_values`); the order line's own values always win. Entered values are kept on the check (`quality_checks.lot_values`,
  migration `f6a1b2j0`) and printed in the inspection report.
- **Reinspection of closed orders**: a `reinspection` may be opened on a closed order as well (its retained samples — e.g. a certificate
  requested after shipment); other types still need the order running, held or completed. The order stays closed.
- **Readings** (`PUT /quality-checks/{id}/measurements/{mid}`, permission `quality_checks:measure`): numeric readings → count, minimum,
  maximum, mean and the verdict (`pass` when every reading lies within the limits, `fail` otherwise, `recorded` when there are no limits,
  `pending` below the required count); attributes → conforming / not conforming with an observation.
- **Closing**: a check with a plan closes only when everything is measured (`MEASUREMENTS_INCOMPLETE`), and never as `accepted` with a
  failed parameter (`ACCEPTED_WITH_FAILED_MEASUREMENT`); conditional accept or rejected remain possible.
- The inspection report (Q1) shows the plan, limits, readings and verdicts, and the reference specification.
- Migration `f6a1b2i8` creates the tables and grants `measure` to every role that may update checks (same scope) and the
  specification permissions to the organization admin, factory manager and quality manager (read also to the viewer).

## Certificates of Analysis (QUAL-COA-001)

Rules: `quality/domain/certificates.py`. Writer: `application/certificate_service.py`. Document: `reporting/certificate.py`
(`quality.certificate`, not listed in the center) with `templates/coa_*.html|css`, external corporate identity.

- **Source**: a closed inspection whose result is `accepted` or `conditional_accept`, with a measurement plan and no failed parameter
  (`CHECK_NOT_CLOSED`, `CHECK_NOT_CERTIFIABLE`, `CERTIFICATE_NEEDS_MEASUREMENTS`, `CERTIFICATE_HAS_FAILED_MEASUREMENT`).
  `GET /quality-certificates/sources?check_id=` says whether it is certifiable and lists the lot's customers (the production
  allocations of the line, read through the shared metadata).
- **Draft**: copies and freezes the inspection code and result, the specification number and revision, and every measurement
  (limits, readings summary, verdict). Defaults: customer (the lot's only customer), batch `PO-…-L<line>`, product = specification title,
  grade, production date (order completion), inspection date, quantity = accepted quantity (it can only go down), sample size.
  Completed before issue: customer PO, delivery note, packages, sampling reference, retained sample, deviation (required for a
  conditional accept), remarks.
- **Issue** (`certificates:issue`): numbered `<prefix><NNNN>` from `quality_settings` under a row lock — numbers are given only on issue,
  so drafts never consume one. The prefix and last number are set once to continue from paper certificates and never go back.
  An issued certificate is final.
- **Revoke** (`certificates:revoke`) with a reason, printed on the document. **Replace**: a new draft copying the certificate; issuing it
  revokes the old one ("Superseded by …") and prints "Supersedes …".
- **Document**: identification, specification and actual results (mean, range and number of readings, or the attribute verdict),
  sampling and release, declaration, prepared-by / approved-by, electronic-issue statement. Drafts carry "DRAFT — NOT VALID" and
  "PENDING RELEASE APPROVAL"; revoked ones "REVOKED". English by default, Arabic on request. Nothing is stored.
- Migration `f6a1b2i9` creates the tables and grants the certificate permissions to the organization admin, factory manager and
  quality manager (read also to the viewer). Its downgrade refuses while issued or revoked certificates exist.

## Quality report center (QUAL-REPORT-001)

`/quality-reports` uses the shared reporting core (same layout, identity, languages and "nothing is stored" rule as production).
`app/quality/reporting` registers four reports — Q1 check report, Q2 checks summary, Q3 rejections and dispositions, Q4 defects —
each behind `reports:quality:<key>` (`quality/domain/report_permissions.py`) plus the read permission of its data.
Lookups (`/reports/quality/lookups/{checks,orders,products}`) need the data's read permission. Production orders are read through
the shared metadata. Migration `f6a1b2i7` adds the permissions and grants them to organization_admin, factory_manager, quality_manager
and viewer. The check page opens Q1 with the check fixed; R1 includes the order's checks and rejections.

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
- Cross-module reads (orders, lines, samples, user names) go through `Base.metadata.tables` in `application/support.py` — no Production or Commercial model imports
- `created_by_user_id` / `checked_by_user_id` / `detected_by_user_id` / `rejected_by_user_id` use `ForeignKey("foundation_users.id")` at DB level only — no import of the Foundation `User` model into Quality code

---

## Implemented routes

All routes require a valid Bearer token. All results are scoped to the caller's `organization_id`.

See [docs/api/quality.md](../api/quality.md) for the full endpoint list.
