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

### `POST /quality-checks`
Create a quality check. `inspection_code`, `status`, and `result` are always auto-set.

**Body:**
```json
{
  "check_datetime": "2026-07-03T08:00:00Z",
  "check_type": "in_process_inspection",
  "qty_inspected": 100,
  "qty_accepted": 85,
  "qty_rejected": 15,
  "production_order_id": "<uuid>",
  "production_output_id": "<uuid>",
  "shift_report_id": "<uuid>",
  "notes": "optional"
}
```

`check_type` must be one of: `in_process_inspection` / `finished_product_inspection` / `sample_inspection` / `reinspection` / `issue_triggered` / `general`. **Do not use measurement method names** (visual, dimension, tensile, weight) — these are not valid values (D4).

`qty_accepted + qty_rejected` must equal `qty_inspected` — returns `422` if not satisfied (D2).

All three quantity fields are required and must be `>= 0` with `qty_inspected > 0`.

Returns `201`.

### `GET /quality-checks`
List quality checks for the current org.

**Query filters:** `check_type`, `check_status`, `result`, `production_order_id`, `shift_report_id`, `check_date`

### `GET /quality-checks/{id}`
Get a single quality check. Returns `404` if not found or belongs to a different org.

### `PATCH /quality-checks/{id}`
Update a quality check. All fields optional. Partial quantity updates (e.g., only `qty_accepted`) are re-validated by the service after merging with existing values.

**Closing a check (setting `status = "closed"`):**
`result` must be set — either in this PATCH or already set from a prior update. Returns `400` if closing without a result. This is enforced in the service, not the schema, because the schema cannot see existing state.

---

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

### `POST /quality-rejections`
Create a quality rejection. `disposition_status` is always auto-set to `pending` — do not include it in the body.

**Body:**
```json
{
  "rejection_date": "2026-07-03",
  "rejection_reason": "dimension_failure",
  "rejection_notes": "Batch rejected — thickness deviation exceeds tolerance.",
  "disposition": "rework",
  "quantity_rejected": 15,
  "unit": "pcs",
  "quality_check_id": "<uuid>",
  "quality_defect_id": "<uuid>",
  "production_output_id": "<uuid>"
}
```

`rejection_notes` is **required** (`Field(min_length=1)`) — returns `422` if absent, `400` if whitespace-only (D8 — Quality PRD BR-02).

`quality_check_id` and `quality_defect_id` are both optional. If both are provided, `quality_defect_id` must belong to `quality_check_id` — returns `400` if not.

`disposition_status` is absent from this schema — the service auto-sets it to `pending`.

Returns `201`.

### `GET /quality-rejections`
List quality rejections.

**Query filters:** `rejection_reason`, `disposition`, `disposition_status`, `quality_check_id`, `production_output_id`, `rejection_date`

### `GET /quality-rejections/{id}`
Get a single rejection. Returns `404` if not found or belongs to a different org.

### `PATCH /quality-rejections/{id}`
Update a rejection. To mark the disposition as executed:

```json
{ "disposition_status": "executed" }
```

---

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
