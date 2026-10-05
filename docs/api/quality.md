# API Reference — Quality Module

All endpoints require `Authorization: Bearer <token>`. All results are automatically scoped to the caller's `organization_id` from the JWT — callers never pass `organization_id` in request bodies.

Base prefix: `/api/v1/quality`

---

## Auto-generated and auto-set fields

The following fields are **never accepted in request bodies**. They are set by the service and appear only in responses:

| Field | Entity | Value |
|-------|--------|-------|
| `inspection_code` | QualityCheck | Auto-generated `QI-YYYY-NNNN` on creation |
| `status` (initial) | QualityCheck | Always `open` on creation |
| `result` (initial) | QualityCheck | Always `null` on creation |
| `organization_id` | All entities | From JWT `TenantContext` |
| `checked_by_user_id` | QualityCheck | From JWT `TenantContext` |
| `detected_by_user_id` | QualityDefect | From JWT `TenantContext` |
| `disposition_status` (initial) | QualityRejection | Always `pending` on creation (D9) |
| `rejected_by_user_id` | QualityRejection | From JWT `TenantContext` |
| `report_number` | NonConformanceReport | Auto-generated `NCR-YYYY-NNNN` on creation (locked quality counter) |
| `status` (initial) | NonConformanceReport | Always `draft` on creation |
| `detected_by_user_id` | NonConformanceReport | From JWT `TenantContext` |
| `line_no` (auto) | NonConformanceItem | `(max_line_no or 0) + 1` when not provided (D13) |

---

## Quality Checks

Prefix `/api/v1/quality/quality-checks`. Errors are `{"detail": {"code": ...}}`.

| Method | Path | Permission | Notes |
|--------|------|------------|-------|
| POST | `` | checks:create | `check_type`, `check_datetime`, order (+line) or `sample_id`, optional `qty_inspected`, `notes` |
| GET | `` | checks:read | Filters: `production_order_id`, `check_type`, `status`, `result`, `date_from`, `date_to`, `search` |
| GET | `/lookups/orders` | checks:create or rejections:create | Orders that can be inspected, with their lines |
| GET | `/lookups/samples` | checks:create | Samples |
| GET | `/{id}` | checks:read | With `history`, `rejections`, `actions` |
| PATCH | `/{id}` | checks:update | While open / under inspection |
| POST | `/{id}/start` | checks:start | open → under_inspection |
| POST | `/{id}/close` | checks:close | `result`, the three quantities, `notes`, `rejection_reason`; opens a pending rejection for a rejected quantity |
| POST | `/{id}/cancel` | checks:cancel | `reason` required |

Codes: `PRODUCTION_ORDER_REQUIRED`, `SAMPLE_REQUIRED`, `ORDER_NOT_INSPECTABLE`, `ORDER_ITEM_NOT_FOUND`, `CHECK_IS_FINAL`, `CHECK_NOT_OPEN`,
`QUANTITY_INSPECTED_REQUIRED`, `QUANTITY_NEGATIVE`, `QUANTITY_BALANCE`, `ACCEPTED_WITH_REJECTED_QUANTITY`, `REJECTED_WITHOUT_QUANTITY`, `REASON_REQUIRED`.

## Quality Defects

Defects are nested under their parent quality check.

### `POST /quality-checks/{check_id}/defects`
Add a defect to a quality check. `check_id` from the URL is validated against the caller's org — returns `400` if the check does not exist in this org (D5).

**Body:**
```json
{
  "defect_date": "2026-07-03",
  "defect_category": "thickness",
  "severity": "major",
  "defect_count": 15,
  "description": "Film thickness deviation: measured 0.3mm, target 0.5mm.",
  "notes": "optional",
  "production_order_id": "<uuid>"
}
```

`defect_count` defaults to `1` if omitted (D6). Must be `> 0`.
`defect_category` must be one of 11 values — see enum reference in [docs/modules/quality.md](../modules/quality.md) (D7).

Returns `201`.

### `GET /quality-checks/{check_id}/defects`
List defects for a specific quality check.

### `GET /quality-defects`
List all defects for the current org (flat list across all checks).

**Query filters:** `defect_category`, `severity`, `production_order_id`, `defect_date`

### `GET /quality-defects/{defect_id}`
Get a single defect by ID.

### `PATCH /quality-defects/{defect_id}`
Update a defect. All fields optional.

---

| GET | `/{id}/specifications` | checks:measure | Specifications in force for the inspected product |
| POST | `/{id}/plan` | checks:measure | `specification_id`; copies the lines with limits resolved for the lot |
| PUT | `/{id}/measurements/{measurement_id}` | checks:measure | `readings` (numeric) or `attribute_result` + `observation` |

Measurement codes: `SPECIFICATION_NOT_ACTIVE`, `MEASUREMENTS_STARTED`, `LOT_SPEC_VALUE_MISSING` (with `key`), `READING_INVALID`,
`TOO_MANY_READINGS`, `MEASUREMENTS_INCOMPLETE` (with `count`), `ACCEPTED_WITH_FAILED_MEASUREMENT`.

## Test parameters and specifications

Prefix `/api/v1/quality`.

| Method | Path | Permission | Notes |
|--------|------|------------|-------|
| GET | `/quality-test-parameters` | specifications:read or checks:measure | `?active=true` for active ones |
| POST | `/quality-test-parameters` | specifications:create | code, names, kind, unit, method |
| POST | `/quality-test-parameters/standard` | specifications:create | Adds the strapping-band set once |
| PATCH | `/quality-test-parameters/{id}` | specifications:update | Names, unit, method, active, order (not the kind) |
| GET | `/quality-specifications` | specifications:read | Filters: `status`, `product_type`, `search` |
| POST | `/quality-specifications` | specifications:create | Revision 1, draft, with its lines |
| GET | `/quality-specifications/{id}` | specifications:read | With lines and `actions` |
| PATCH | `/quality-specifications/{id}` | specifications:update | Draft only; `lines` replace the current ones |
| POST | `/quality-specifications/{id}/activate` | specifications:activate | The revision in force with the same number becomes superseded |
| POST | `/quality-specifications/{id}/revise` | specifications:create | New draft revision copying the lines |

Codes: `PARAMETER_CODE_TAKEN`, `SPECIFICATION_CODE_TAKEN`, `SPECIFICATION_NOT_DRAFT`, `SPECIFICATION_EMPTY`, `SPECIFICATION_DRAFT_EXISTS`,
`LIMITS_REQUIRED`, `LIMITS_INVALID`, `TARGET_REQUIRED`, `ORDER_SPEC_KEY_REQUIRED`, `REQUIREMENT_REQUIRED`, `TOLERANCE_NEGATIVE`
(line errors carry the parameter code).

## Certificates of Analysis

Prefix `/api/v1/quality`.

| Method | Path | Permission | Notes |
|--------|------|------------|-------|
| GET | `/quality-certificates/sources?check_id=` | certificates:create | `certifiable`, `blocker`, the lot's `customers` |
| GET | `/quality-certificates` | certificates:read | Filters: `status`, `quality_check_id`, `production_order_id`, `search` |
| POST | `/quality-certificates` | certificates:create | `quality_check_id`, optional `customer_id`, `customer_po`; a draft with frozen results |
| GET | `/quality-certificates/{id}` | certificates:read | With measurements, history and `actions` |
| PATCH | `/quality-certificates/{id}` | certificates:update | Draft only |
| POST | `/quality-certificates/{id}/issue` | certificates:issue | Numbers and finalises it |
| POST | `/quality-certificates/{id}/revoke` | certificates:revoke | `reason` |
| POST | `/quality-certificates/{id}/replace` | certificates:create | New draft superseding it |
| GET | `/quality-certificates/{id}/document.pdf?lang=en|ar` | certificates:read | The PDF |
| GET / PATCH | `/quality-settings` | certificates:read / certificates:issue | `coa_prefix`, `coa_last_number` (never backwards) |

Codes: `CERTIFICATE_NOT_FOUND`, `CHECK_NOT_CLOSED`, `CHECK_NOT_CERTIFIABLE`, `CERTIFICATE_NEEDS_MEASUREMENTS`,
`CERTIFICATE_HAS_FAILED_MEASUREMENT`, `CERTIFICATE_NOT_DRAFT`, `CERTIFICATE_NOT_ISSUED`, `QUANTITY_EXCEEDS_ACCEPTED`,
`CUSTOMER_REQUIRED`, `CUSTOMER_NOT_ON_LOT`, `BATCH_REQUIRED`, `DEVIATION_NOTE_REQUIRED`, `CERTIFICATE_NUMBER_BACKWARDS`,
`REPLACEMENT_DRAFT_EXISTS`.

## Quality Rejections

Prefix `/api/v1/quality/quality-rejections`.

| Method | Path | Permission | Notes |
|--------|------|------------|-------|
| POST | `` | rejections:create | From a closed check (`quality_check_id`) or for an order (`production_order_id`, optional line) |
| GET | `` | rejections:read | Filters: `production_order_id`, `quality_check_id`, `rejection_reason`, `disposition`, `disposition_status`, dates, `search`; each row has `unresolved` |
| GET | `/{id}` | rejections:read | With `history`, `actions` |
| PATCH | `/{id}` | rejections:update | While pending |
| POST | `/{id}/decide` | rejections:decide | `disposition`, `decision_notes`, `concession_approved_by` (both required for `use_as_is`) |
| POST | `/{id}/execute` | rejections:execute | Optional `execution_notes`; not for `hold` |

Codes: `CHECK_HAS_NO_REJECTED_QUANTITY`, `QUANTITY_REQUIRED`, `QUANTITY_EXCEEDS_CHECK` (with `available`), `NOTES_REQUIRED`, `DEFECT_NOT_FOUND`,
`REJECTION_ALREADY_DECIDED`, `REJECTION_IS_FINAL`, `CONCESSION_DETAILS_REQUIRED`, `DECISION_REQUIRED`, `HOLD_IS_NOT_FINAL`.

## Non-Conformance Reports (QUAL-NCR-002)

Errors answer `{"detail": {"code": ...}}`. The status moves only through the stage endpoints. See `docs/modules/quality.md`.

| Method | Path | Permission |
|--------|------|------------|
| GET | `/non-conformance-reports` (`status`, `source_type`, `severity`, `owner_user_id`, `open_only`, `date_from`, `date_to`, `search`) | ncr_reports:read |
| POST | `/non-conformance-reports` (header, sources, owner, due date, supplier action, costs, `items[]`) | ncr_reports:create |
| GET / PATCH | `/non-conformance-reports/{id}` | ncr_reports:read / ncr_reports:update (until closed or cancelled) |
| GET | `/non-conformance-reports/lookups/users?q=` | ncr_reports:create or update |
| GET | `/non-conformance-reports/{id}/document.pdf?lang=ar|en` | ncr_reports:read |
| POST / PATCH / DELETE | `/non-conformance-reports/{id}/items[/{item_id}]` | ncr_reports:update |
| POST | `/non-conformance-reports/{id}/contain` (`containment`) | ncr_reports:update |
| POST | `/non-conformance-reports/{id}/investigate` (`root_cause_category`, `root_cause_method`, `root_cause`, `action_required`, `no_action_justification`) | ncr_reports:update |
| POST | `/non-conformance-reports/{id}/submit` | ncr_reports:update |
| POST | `/non-conformance-reports/{id}/verify` (`effective`, `notes`) | ncr_reports:verify |
| POST | `/non-conformance-reports/{id}/cancel` (`reason`) | ncr_reports:cancel |
| POST / PATCH | `/non-conformance-reports/{id}/actions[/{action_id}]` (`kind`, `description`, `owner_user_id` or `owner_name`, `due_date`) | ncr_reports:update |
| POST | `/non-conformance-reports/{id}/actions/{action_id}/complete` (`evidence`) | ncr_actions:complete or ncr_reports:update |
| POST | `/non-conformance-reports/{id}/actions/{action_id}/cancel` (`reason`) | ncr_reports:update |
| GET | `/ncr-actions` (`status`, `mine`, `overdue`, `search`) | ncr_actions:read or ncr_reports:read |
| POST / GET / DELETE | `/non-conformance-reports/{id}/attachments[/{attachment_id}]` | ncr_reports:create or update / read / update |

## Common error codes

| Code | Meaning |
|------|---------|
| 400 | Business rule violation (e.g. closing check without result, creating item on closed NCR, cross-org reference) |
| 401 | Missing or expired token |
| 404 | Entity not found or belongs to a different org |
| 422 | Pydantic validation failure (e.g. qty imbalance, missing rejection_notes, defect_count ≤ 0) |

## Most common validation errors

| Field | Rule | HTTP | Where enforced |
|-------|------|------|----------------|
| `qty_accepted + qty_rejected ≠ qty_inspected` | D2 | 422 | Pydantic schema (create); service (update after merge) |
| `rejection_notes` absent or empty | D8 | 422 | Pydantic `min_length=1` |
| `rejection_notes` whitespace-only | D8 | 400 | Service `_validate_rejection_notes` |
| `status = closed` without `result` on QualityCheck | D1 | 400 | Service — schema cannot see existing state |
| Create item on CLOSED NCR report | D12 | 400 | Service `_validate_open_parent_report` |
| `quality_check_id` not in org | D5 | 400 | Service `_validate_quality_check` |
| `quality_defect_id` not in org | — | 400 | Service `_validate_quality_defect_if_present` |
| Defect belongs to different check than referenced | — | 400 | Service `_validate_defect_belongs_to_check` |
| Reopen closed NCR report | — | 400 | Service `update_report` re-open guard |
