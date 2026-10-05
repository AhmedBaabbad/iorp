# Quality Module

**Status:** QUAL-001 lifecycle and close gate; QUAL-REPORT-001 report center; QUAL-SPEC-001 specifications and measurements; QUAL-COA-001 certificates of analysis; QUAL-RET-001 returned goods; QUAL-NCR-002 non-conformance reports redesigned. Defects unchanged

The quality module owns the inspection and non-conformance chain: recording quality checks, logging defects, formalizing rejections, and opening non-conformance cases with line items. All data is org-scoped via `TenantContext` (ADR-001). No imports from `app.production`, `app.commercial`, or `app.foundation` models are allowed — only `app.core.*` and `app.quality.*` (ADR-004).

**NCR placement (D10, confirmed in QUAL-NCR-002):** non-conformance reports are a quality instrument for every source (supplier material, production, warehouse, customer returns), so they stay in `backend/app/quality/`. Suppliers, purchase orders and goods receipt belong to a future procurement module; the report keeps a supplier by name (and `supplier_id` for it) until then.

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
`QualityDefect` intentionally has no status field in v0.1. A defect is a static factual observation — it was found, measured, and recorded. It does not have a lifecycle. Defect resolution tracking belongs to the downstream `QualityRejection` and the non-conformance report's corrective actions.

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

### NonConformanceReport (QUAL-NCR-002)

One report per non-conformance, whatever its source — incoming material from a supplier (granules, masterbatch, cores, cartons,
film…), a supplier's service, production, the warehouse, a customer return — worked through the stages of a corrective action
(`domain/ncr.py`, single writer `application/ncr_service.py`, routes `api/routes_ncr.py`).

```
open ─contain(what was done at once)→ investigation ─investigate(root cause)→ action ─submit→ verification ─verify(effective)→ closed
                                       investigation ─investigate(no action needed, why)→ closed          (a minor, isolated case)
                                                                                 verification ─verify(not effective, why)→ action
any stage before closed ─cancel(reason)→ cancelled
```

| Group | Fields |
|-------|--------|
| Identity | `report_number` (NCR-YYYY-NNNN from the quality counter, kind `NCR`), `report_date`, `source_type`, `report_type`, `severity` (minor/major/critical), `status`, `title`, `description`, `reference_code` |
| Sources (plain references, ADR-004) | `quality_check_id`, `quality_rejection_id`, `production_order_id`, `return_id`, `customer_id` / `customer_name`, `supplier_id` (procurement, later) / `supplier_name`, `supplier_reference` |
| Follow-up | `owner_user_id`, `due_date` (overdue when past and not final) |
| Containment | `containment`, `contained_at/by` |
| Investigation | `root_cause_category` (6M: man, machine, material, method, measurement, environment), `root_cause_method` (5 Whys, fishbone, other), `root_cause`, `action_required`, `no_action_justification`, `investigated_at/by` |
| Verification | `verification_attempts`, `verification_notes`, `verified_at/by`, `closed_at`, `cancel_reason` |
| With the supplier | `supplier_action` (none, notify, return the goods, SCAR), `supplier_response`, `supplier_responded_at` |
| Cost (optional) | `cost_material`, `cost_labor`, `cost_scrap`, `cost_transport`, `cost_other` (total shown), `claim_amount`, `claim_status` (none, claimed, accepted, rejected, recovered) |

Details, items, costs and the supplier's answer are edited until the report is closed or cancelled (`NCR_IS_FINAL`); the status
only moves through the stage endpoints (a status in an update is refused, 422).

### NonConformanceItem

What a report affects (a material lot, a product batch): `item_name`, `item_reference` (lot/batch), `quantity_affected` with a `unit`
from the shared catalogue, `issue_description`, and the decision on it — `disposition` (return to supplier, use as is under a
concession, sort and re-inspect, rework, second grade, recycle, scrap «هالك», hold) with `disposition_notes`. Scoped through its report.

### NCRAction (`quality_ncr_actions`) and NCRAttachment (`quality_ncr_attachments`)

Corrective actions of a report: `kind` (correction, corrective, preventive), `description`, an owner (a user, or someone outside the
system by name — e.g. the supplier), `due_date`, `status` (open, done with its `evidence`, cancelled with a reason), overdue when
past due and open. They are added while investigating or acting; the report goes to verification only when none is open and at
least one is done (`ACTIONS_STILL_OPEN`, `ACTION_REQUIRED`). `/corrective-actions` lists them across reports (`GET /quality/ncr-actions`,
`mine`, `overdue`, `status`). Photos and documents (images or PDF, 10 MB, at most 20) are kept with the report.

### Document

`quality.ncr` (opened from the report, not listed): the company's identity, numbered sections (report, source, description, affected
items and decisions, containment, root cause, actions, verification, with the supplier, cost and claim) and three signature boxes;
Arabic or English; "CANCELLED" on a cancelled report. It can be sent to the supplier. Nothing is stored.

### Opened by other flows

A customer return's quality decision may open one (`customer_return`, the return, its inspection, rejection, production order and
customer, with the rejected quantity as its item) through `NCRService.open_report`.

Migration `f6a1b2j6` turned the status into text (`draft` → open, `under_review` → investigation), added the columns and tables,
seeded the NCR counter from the numbers already issued, and granted the new permissions; its downgrade refuses once reports have
actions, files or later stages.

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
| NCR status (text, `domain/ncr.py`) | `open` / `investigation` / `action` / `verification` / `closed` / `cancelled` |

---

## Production order close gate (QUAL-001)

Production asks the composition-root guards before closing an order (`app/core/interfaces/order_close_guards.py`; quality registers
`rejection_service.close_blockers` in `main.py`, so production never imports quality). Under the order lock it raises
`409 {"code": "CLOSE_BLOCKED", "blockers": [{"code", "count"}]}` when the order has:

- checks still `open` or `under_inspection` → `QUALITY_CHECKS_OPEN`
- rejections `pending`, or `decided` as `hold` → `QUALITY_REJECTIONS_UNRESOLVED`

The order page shows a quality section with these counts, and the status panel lists the blockers.
Inspections of returned goods (`return_line_id` set) and their rejections (`return_id` set) are left out: the goods were produced
and shipped long before (QUAL-RET-001).

## Permissions

Per action, one source: `quality/domain/permissions.py`, mirrored by `frontend/src/lib/quality-permissions.ts`
(`tests/quality-permissions.test.mjs` keeps them identical). Every quality route declares one; screens hide what the user cannot do.

| Resource | Actions |
|----------|---------|
| `quality:quality_checks` | read, create, update, start, close, cancel, measure |
| `quality:rejections` | read, create, update, decide, execute |
| `quality:quality_defects` | read, create, update |
| `quality:ncr_reports` | read, create, update (details, items, containment, root cause, actions), verify (effectiveness, closes), cancel |
| `quality:ncr_actions` | read, complete (corrective actions, for the departments that own them) |
| `quality:specifications` | read, create, update, activate (test parameters and product specifications) |
| `quality:certificates` | read, create, update, issue, revoke (certificates of analysis) |

Non-conformance (QUAL-NCR-002): quality and factory managers hold all; production, maintenance and procurement managers read
reports and complete their actions; the warehouse also opens reports; the safety manager keeps read/create/update and completes actions;
the viewer reads. Migration `f6a1b2i6` split the old `write` grants into these actions (backup `quality_rbac_i6_backup`) and gave `quality_manager`
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

## Returned goods (QUAL-RET-001)

Goods a customer sent back (shipping returns, SHIP-004) that the warehouse received **for quality**: always when the return reason
puts the goods in question (quality issue or defect, not to specification, transit damage, other), and whenever the warehouse
sends them. Other returns go back to stock on receipt without quality. Contract between the modules (no imports, ADR-004):

| Quality reads from shipping (`support.ShippingReads`) | Shipping reads from quality (`support.QualityReads`) |
|-------------------------------------------------------|------------------------------------------------------|
| `shipping_returns` (received, `quality_required`), `shipping_return_lines`, `shipping_shipments`, `shipping_shipment_lines` (`production_order_id`) | `quality_checks` and `quality_rejections` by `return_id` |

- **`/quality-returns`** lists them; **one inspection per returned line** (`POST /quality/returns/lines/{line_id}/inspection`):
  type `issue_triggered`, the quantity that came back, the line's unit, its production order (so the specification in force applies
  as the plan, as for any lot), the line's width and thickness as `lot_values`; `return_id` / `return_line_id` keep the source.
  `RETURN_NOT_AWAITING_QUALITY`, `RETURN_LINE_ALREADY_INSPECTED`.
- It is measured like any inspection, then **closed by the return decision** (`POST /quality/quality-checks/{id}/return-decision`,
  needs `quality_checks:close` and `rejections:decide`; the plain close answers `RETURN_INSPECTION_NEEDS_DECISION`): the inspected
  quantity is split (`RETURN_SPLIT_MISMATCH` otherwise) between back to stock (accepted), second grade (`use_as_is`, with the
  concession's approver and notes), rework, recycle (`return_to_process`), scrap (هالك) and hold. Each rejected part becomes a
  rejection already **decided**, executed later as usual; the result is accepted when nothing is rejected, else rejected.
  `open_ncr` adds a draft NCR (`customer_return`, reference = the return number).
- **Containment** (`GET /quality/quality-checks/{id}/batch-shipments`): every delivery note that carried the same production order
  (ready, dispatched, delivered…), with a warning for those ready to leave.
- Shipping shows the outcome on the return: back in stock, awaiting, inspecting, decided (parts still to carry out) or done.
- Migration `f6a1b2j5` adds the return references (and `shipping_returns.quality_required`); no new permissions.

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
