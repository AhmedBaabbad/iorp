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
| `report_number` | NonConformanceReport | Auto-generated `NCR-YYYY-NNNN` on creation |
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

## Non-Conformance Reports

### `POST /non-conformance-reports`
Open a non-conformance case. `report_number` and `status` are always auto-set.

**Body:**
```json
{
  "report_date": "2026-07-03",
  "source_type": "incoming_material",
  "report_type": "material_non_conformance",
  "title": "Non-conforming LLDPE granules — Batch B-44",
  "description": "Moisture content measured at 0.12%, spec max is 0.05%.",
  "reference_code": "BATCH-B-44",
  "quality_check_id": "<uuid>",
  "quality_rejection_id": "<uuid>"
}
```

`title` and `description` are both required.
`quality_check_id` and `quality_rejection_id` are optional plain UUID references — org ownership validated when provided.

Returns `201` with `status = "draft"` and auto-generated `report_number = "NCR-YYYY-NNNN"` (D11).

### `GET /non-conformance-reports`
List NCR reports.

**Query filters:** `source_type`, `report_type`, `ncr_status`, `report_date`

Note: the filter parameter is `ncr_status` (not `status`) to avoid shadowing the FastAPI `status` import.

### `GET /non-conformance-reports/{id}`
Get a single NCR report. Returns `404` if not found or belongs to a different org.

### `PATCH /non-conformance-reports/{id}`
Update an NCR report. To advance the status lifecycle:

```json
{ "status": "open" }
```

```json
{ "status": "under_review" }
```

```json
{ "status": "closed" }
```

**Re-open guard:** Once a report is `closed`, it cannot be reopened — returns `400` if `status` is patched to any non-closed value on a closed report.

---

## Non-Conformance Items

Items are nested under their parent NCR report.

### `POST /non-conformance-reports/{report_id}/items`
Add an item to an NCR report.

**Guard (D12):** Returns `400` if the parent report status is `closed`. Org check fires first — a foreign-org `report_id` returns `404` before the status is even checked.

**Body:**
```json
{
  "item_name": "LLDPE Granules — Grade A",
  "issue_description": "Moisture content measured at 0.12%, specification max is 0.05%.",
  "quantity_affected": "500.00",
  "unit": "kg",
  "item_reference": "BATCH-B-44-GRD-A",
  "line_no": 1,
  "notes": "optional"
}
```

`item_name` and `issue_description` are required.
`quantity_affected` is nullable — may be unknown at case open.
`line_no` is optional — auto-assigns as `(max_line_no or 0) + 1` if absent (D13).

Returns `201`.

### `GET /non-conformance-reports/{report_id}/items`
List items for a specific NCR report.

### `GET /non-conformance-items/{item_id}`
Get a single NCR item by ID.

### `PATCH /non-conformance-items/{item_id}`
Update an NCR item. All fields optional.

**Guard (D12):** Returns `400` if the parent report is `closed` — update is also blocked.

---

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
