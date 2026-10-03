# API Reference — Production Module

All endpoints require `Authorization: Bearer <token>`. All results are automatically scoped to the caller's `organization_id` from the JWT — callers never pass `organization_id` in request bodies.

Base prefix: `/api/v1/production`

---

## Work Centers

### `POST /work-centers`
Create a work center.

**Body:**
```json
{
  "code": "WC-001",
  "name": "Extrusion Line 1",
  "center_type": "extrusion",
  "status": "active",
  "location": "Hall A",
  "notes": "optional"
}
```
`center_type` required. `status` defaults to `active`. Returns `201`.

### `GET /work-centers`
List work centers for the current org.

**Query filters:** `status`, `center_type`

### `GET /work-centers/{id}`
Get a single work center. Returns `404` if not found or belongs to a different org.

### `PATCH /work-centers/{id}`
Update a work center. All fields optional.

---

## Shift Definitions

### `POST /shift-definitions`
Create a shift definition. `crosses_midnight` and `duration_hours` are always auto-calculated — do not include them in the request.

**Body:**
```json
{
  "work_center_id": "<uuid>",
  "code": "SHIFT-MORN",
  "name": "Morning Shift",
  "shift_type": "morning",
  "start_time": "07:00:00",
  "end_time": "15:00:00",
  "status": "active"
}
```
`work_center_id` must belong to the same org. Returns `201`.

**Auto-calculated fields in response:**
- `crosses_midnight`: `true` when `end_time <= start_time` (night shifts)
- `duration_hours`: decimal hours between start and end, mod 24h

### `GET /shift-definitions`
List shift definitions.

**Query filters:** `work_center_id` (returns `404` if work center not found), `status`

### `GET /shift-definitions/{id}`
Get a single shift definition.

### `PATCH /shift-definitions/{id}`
Update a shift definition. `crosses_midnight` and `duration_hours` are recalculated on every update.

---

## Production Orders

### `POST /production-orders`
Create a production order.

**Body:**
```json
{
  "work_center_id": "<uuid>",
  "product_type": "Steel Rod 14mm",
  "planned_quantity": "5000.00",
  "unit": "kg",
  "planned_start_date": "2026-07-01",
  "planned_end_date": "2026-07-07",
  "shift_definition_id": "<uuid>",
  "commercial_order_id": "<uuid>",
  "priority": "normal",
  "notes": "optional"
}
```
`production_order_number` is auto-generated (`PO-YYYYNNNN`) if not provided. `priority` defaults to `normal`. Returns `201`.

### `GET /production-orders`
List production orders.

**Query filters:** `work_center_id`, `status`, `priority`, `planned_start_date`

### `GET /production-orders/{id}`
Get a single production order.

### `PATCH /production-orders/{id}`
Update a production order. All fields optional.

---

## Production Order Items

Items are nested under their parent order.

### `POST /production-orders/{order_id}/items`
Add an item to a production order.

**Body:**
```json
{
  "target_spec_json": {"width_mm": 500, "thickness_mm": 0.8},
  "planned_quantity": "3000.00",
  "unit": "kg",
  "line_no": 1,
  "notes": "optional"
}
```
`line_no` auto-assigns if not provided. Returns `400` if order status is `cancelled`.

### `GET /production-orders/{order_id}/items`
List items for a production order.

### `GET /production-orders/{order_id}/items/{item_id}`
Get a single item.

### `PATCH /production-orders/{order_id}/items/{item_id}`
Update an item. All fields optional.

### `DELETE /production-orders/{order_id}/items/{item_id}`
Delete an item. Returns `204`.

---

## Shift Reports (removed)

The hand-written shift report was removed (migration `f6a1b2h1`). Shift and order reports will be computed from the actual records: rosters, outputs, waste, downtime and quality. There is no `/shift-reports` endpoint, and records no longer carry `shift_report_id`.

## Production Order Final Result

The final result records **what happened to the produced quantity** of a production order (PROD-OUTPUT-001). It is cross-industry and belongs to the order only. It has no work center, shift, roster, run or workforce fields, and no status of its own.

Table: `production_result_entries`, migration `f6a1b2h3`.

Permissions:
- `production:results:read`
- `production:results:create`, `production:results:update`, `production:results:delete`: each while the order is completed.
- `production:results:correct`: corrections once the order is closed.

Closing uses `production:production_orders:close`. Each entry's `actions` lists only what the user's permissions allow.

### Editability, derived from the order status
| Order status | Result |
|---|---|
| `draft`, `released`, `in_progress`, `on_hold`, `cancelled` | not available: writes fail with `409 RESULT_NOT_AVAILABLE` |
| `completed` | entries can be created, edited and deleted |
| `closed` | locked: create, edit and delete fail with `409 RESULT_LOCKED`; only corrections are allowed |

Every write locks the order row and re-reads its status. An entry therefore cannot land after the order closes, and concurrent writes cannot push `customer_good` past the allocation.

### Dispositions and loss
| Disposition | Meaning | `counts_as_loss` |
|---|---|---|
| `customer_good` | good, fulfils customer demand | always false |
| `stock_good` | good, beyond demand or made for stock | always false |
| `sample` | samples and tests | **must be sent** (`422 SAMPLE_LOSS_FLAG_REQUIRED`); stays `sample` either way |
| `scrap` | unusable final loss | always true |
| `rework` | not final-good, possibly recoverable | always false |

The server sets the fixed flags whatever the request sends. A database check constraint enforces the same rule.

**Customer cap:** `customer_good` may not exceed the active customer allocation.
- The scope is per item when the allocations carry order items (planning orders), otherwise the whole order in that unit.
- Going over fails with `422 CUSTOMER_GOOD_EXCEEDS_ALLOCATION`. The detail has `allocated_quantity`, `customer_good_quantity`, `requested_quantity` and `excess_quantity`. Record the excess as `stock_good`.
- With no allocation the request fails with `422 NO_CUSTOMER_ALLOCATION`.
- The cap is checked on create, on edit (the entry's own quantity is excluded), and on positive corrections.

**Item:**
- For a single-item order the item is auto-assigned.
- For a multi-item order it is required (`422 ORDER_ITEM_REQUIRED`).
- An item from another order fails with `422 ORDER_ITEM_NOT_IN_ORDER`.
- Orders without items (legacy) record against the order.

**Unit:** always the item's unit (or the order's, when it has no items). A different `unit` fails with `422 UNIT_MISMATCH`. There is no conversion. `secondary_quantity` and `secondary_unit` are informational, sent together (`422 SECONDARY_MEASURE_INCOMPLETE`), and totalled per secondary unit.

### Summary formulas (computed, never stored)
The summary is computed per item, and per unit for the whole order. Different units are never added together.
```
customer_good   = Σ customer_good          stock_good   = Σ stock_good
good_total      = customer_good + stock_good
samples_total   = Σ sample                 samples_loss = Σ sample where counts_as_loss
scrap_total     = Σ scrap                  rework_total = Σ rework
loss_total      = scrap_total + samples_loss
total_output    = good_total + samples_total + scrap_total + rework_total
fulfillment_pct = customer_good / allocated_qty × 100   (null unless allocated_qty > 0)
yield_pct       = good_total / total_output × 100       (null unless total_output > 0)
loss_pct        = loss_total / total_output × 100       (null unless total_output > 0)
variance_qty    = good_total − planned_qty
```
All sums include correction entries with their sign. Percentages have 2 decimals.

### Corrections
Corrections are allowed only on a closed order; otherwise the request fails with `409 CORRECTION_REQUIRES_CLOSED_ORDER`.
- A correction is a new row with `entry_type = correction` and `corrects_entry_id` pointing at the original.
- It keeps the original's disposition, item, unit and loss flag.
- It carries a signed non-zero delta and a mandatory `correction_reason`.
- The original is never changed.
- The original's effective total (original plus its corrections) can never go below 0 (`422 CORRECTION_MAKES_TOTAL_NEGATIVE`).
- Corrections are made against originals only (`422 CORRECT_THE_ORIGINAL`).

### Close guard
Closing is checked in the existing transition service; see [PRODUCTION-ORDER-LIFECYCLE.md](../PRODUCTION-ORDER-LIFECYCLE.md). It needs result entries, one per item for multi-item orders. Otherwise, send `{"action": "close", "zero_output": true, "reason": "..."}`.

### Endpoints
| Method | Path | Order status | Permission |
|---|---|---|---|
| GET | `/production-results?status=completed\|closed` | lists completed and closed orders | `results:read` |
| GET | `/production-orders/{id}/result` | any | `results:read` |
| POST | `/production-orders/{id}/result/entries` | completed | `results:write` |
| PATCH | `/production-orders/{id}/result/entries/{entryId}` | completed | `results:write` |
| DELETE | `/production-orders/{id}/result/entries/{entryId}` | completed | `results:write` |
| POST | `/production-orders/{id}/result/entries/{entryId}/corrections` | closed | `results:correct` |

`GET /production-orders/{id}/result` returns:
- `order`, `available`, `editable`, `locked` and `allocation_level` (`item`/`order`/`none`).
- `items`: each with a `summary`.
- `totals`: one per unit.
- `entries`: originals with their `corrections`, `effective_quantity` and allowed `actions`.
- `close_check`: `ready`, `has_entries` and `missing_item_ids`.
- `actions`.

`GET /production-results` returns one row per completed or closed order: `id`, `number`, `status`, `product_type`, `entry_count`, `correction_count`, `ready_to_close` and `totals` (per unit, same formulas). The frontend shows it as «المخرجات الإنتاجية». Writes return the same shape as the order result, recomputed. The organization always comes from the signed-in user. A body with `organization_id` is rejected (`422`), and another organization's order is `404`.

**Body (create):**
```json
{
  "production_order_item_id": "<uuid, optional for single-item orders>",
  "disposition": "sample",
  "quantity": "12.500",
  "counts_as_loss": false,
  "secondary_quantity": "3.2",
  "secondary_unit": "kg",
  "reason_code": "LAB_TEST",
  "notes": "optional"
}
```
**Body (correction):** `{ "quantity": "-5", "secondary_quantity": "-0.4", "correction_reason": "Scale drift" }`

---

## Production Outputs (removed)

The earlier design, a quantity recorded per work center and shift, was removed entirely by migration `f6a1b2h5`. An order's outcome is its [final result](#production-order-final-result).

What was removed:
- the `production_outputs` table and its `/production-outputs` endpoints (they now answer `404`);
- the `production:production_outputs:*` permissions;
- the quality columns `production_output_id` (on checks, defects and rejections).

The migration refuses to run while any output row or quality reference exists, so recorded data is never dropped by accident.

A work center cannot be deleted (`409`) while its orders have final-result entries, or while waste records or downtime events are recorded on it. `GET /work-centers/{id}/delete-summary` reports `production_results_count`, `waste_records_count` and `downtime_records_count`, and the UI disables the delete button when any is non-zero.

---

## Downtime Events

**Machine downtime** (PROD-DOWNTIME-001; migration `f6a1b2h7`) is a period in which a work center (machine) did not produce. The event belongs to the **work center**. The production order and run it interrupted are optional context, because a machine also stops when nothing is scheduled on it.

Permissions: `production:downtime_events:{read,create,update,delete,close}`. Ending an ongoing stop needs `close`, not `update`.

### Rules
- **Open and closed.** A stop without `end_time` is open (ongoing). `POST /downtime-events/{id}/close` ends it, now unless an `end_time` is given. `status`, `duration_minutes` (to the hundredth) and `planned` are derived, never accepted from the body.
- **One stop at a time per machine.** Periods on a work center never overlap, and only one can be open (`409 DOWNTIME_OVERLAP`, with the conflicting event). Writes lock the work center row, so two operators cannot record overlapping stops together.
- **Times.** `start_time` and `end_time` need a timezone. They cannot be in the future (`START_IN_FUTURE`, `END_IN_FUTURE`), and the end must be after the start (`END_BEFORE_START`). Filters by date use the factory's local day.
- **Machine, order and run.**
  - A run gives the machine and the order. A different machine is `WORK_CENTER_MISMATCH`, a different order is `RUN_NOT_IN_ORDER`, and a cancelled run is `RUN_CANCELLED`.
  - Without a run, `work_center_id` is required (`WORK_CENTER_REQUIRED`).
- **Linked order.** A stop can be linked while the order is in progress, on hold or completed; otherwise `ORDER_NOT_RUNNING`. Once the order is closed, its stops are locked (`DOWNTIME_LOCKED`).
- **Work center deletion.** A work center with recorded downtime cannot be deleted (`409`). Records are kept, never removed as a side effect.

### Causes: planned stops vs. availability losses
| `category` | English | Arabic | `planned` |
|---|---|---|---|
| `breakdown` | Breakdown | عطل | false |
| `changeover_setup` | Changeover and setup | تغيير المنتج والضبط | false |
| `material_shortage` | Material shortage | نقص المواد | false |
| `waiting_labor` | Waiting for operator | انتظار المشغّل | false |
| `quality_issue` | Quality issue | مشكلة جودة | false |
| `utilities` | Utilities (power, air, water) | المرافق | false |
| `other` | Other | أخرى | false |
| `planned_maintenance` | Planned maintenance | صيانة مخططة | true |
| `break_meeting` | Break or meeting | استراحة أو اجتماع | true |
| `no_orders` | No orders scheduled | لا يوجد عمل مجدول | true |

Planned stops are outside planned production time and do not reduce availability. Every other cause is an availability loss. That includes **changeover**, which is scheduled but is still time the machine could have produced, as in the usual OEE convention.

Plant detail goes in `reason_code`. The migration mapped the earlier values:
- `machine` → `breakdown`
- `material` → `material_shortage`
- `manpower` → `waiting_labor`
- `quality` → `quality_issue`
- `setup` → `changeover_setup`

It also recomputed durations from the stored times.

### Endpoints
| Method | Path | Notes |
|---|---|---|
| POST | `/downtime-events` | `201`; no `end_time` means an open stop |
| GET | `/downtime-events` | filters `work_center_id`, `production_order_id`, `production_run_id`, `category`, `planned`, `status`, `date_from`, `date_to` |
| GET | `/downtime-events/summary` | same filters; report figures |
| GET | `/downtime-events/{id}` | |
| PATCH | `/downtime-events/{id}` | re-checks overlap and period; `end_time: null` reopens |
| POST | `/downtime-events/{id}/close` | `{ "end_time"?: "..." }` |
| DELETE | `/downtime-events/{id}` | `204` |

Every event carries `labels`: the machine and order names, `run_date`, `created_by_name`, `closed_by_name`, `elapsed_minutes` for an open stop, and `actions` (`close` / `edit` / `delete`).

**Summary (for reports):**
- `count`, `total_minutes`, `planned_minutes` and `unplanned_minutes`, over closed stops;
- `open_count` and `open_minutes_so_far`;
- `mttr_minutes`: the mean length of a closed breakdown;
- `by_category`: cause, planned, count and minutes;
- `by_work_center`: machine, count, minutes and availability-loss minutes.

The order page shows this summary for the order's stops.

**Body (create):**
```json
{
  "work_center_id": "<uuid>",
  "production_order_id": "<uuid, optional>",
  "production_run_id": "<uuid, optional; gives machine and order>",
  "start_time": "2026-09-29T08:00:00Z",
  "end_time": null,
  "category": "breakdown",
  "reason_code": "HYD-PUMP",
  "notes": "optional"
}
```

---

## Waste Records

**Operational waste** (PROD-WASTE-001; migration `f6a1b2h6`) is material lost while a production order runs: start-up, changeover, trim, a machine fault. It is not the order's scrap:
- **Waste:** material lost during operation, possibly many events per order, each with cause, place and run. It is used for root-cause analysis per machine, shift and cause.
- **Scrap:** defective *finished product*, recorded once in the order's [final result](#production-order-final-result). It drives the order's loss KPIs.

Waste is **never added** to the result's totals. It is shown apart, on the order page, as «هدر التشغيل». Relating the two, together with the material consumed, belongs to a later material-balance report.

Permissions: `production:waste_records:{read,create,update,delete}`.

### Links
- **`production_order_id`:** required, and it cannot change later. A record moved to another order is deleted and recorded there.
- **`production_run_id`:** optional. It must be a run of the same order that is not cancelled (`RUN_NOT_IN_ORDER`, `RUN_CANCELLED`). The run gives the work center, and through it the shift and team.
- **`work_center_id`:** the run's work center. Without a run, the one given, or else the order's. A work center that differs from the run's is rejected (`WORK_CENTER_MISMATCH`).
- **`production_order_item_id`:** optional, and it must belong to the order (`ORDER_ITEM_NOT_IN_ORDER`).

### Editability, derived from the order status (no status of its own)
| Order status | Waste |
|---|---|
| `in_progress`, `on_hold` | record, edit, delete |
| `completed` | record (late entries), edit, delete |
| `closed` | locked: `409 WASTE_LOCKED` |
| `draft`, `released`, `cancelled` | `409 WASTE_NOT_AVAILABLE` |

Writes lock the order row and re-read its status, so nothing lands after the order closes.

### Waste types (cross-industry)
| `waste_category` | English | Arabic |
|---|---|---|
| `startup_setup` | Start-up and setup waste | هالك بدء التشغيل والضبط |
| `changeover` | Changeover waste | هالك تغيير المنتج |
| `process` | Process waste (trim, edges) | هالك العملية (قص وحواف) |
| `material_defect` | Raw material defect | هالك عيب المادة الخام |
| `machine_fault` | Machine fault waste | هالك عطل الماكينة |
| `handling_damage` | Handling and breakage | هالك المناولة والكسر |
| `contamination` | Contamination | هالك التلوث |
| `other` | Other waste | هالك آخر |

Plant-specific detail, such as a roll end or a flute crush, goes in `reason_code`. The migration mapped the earlier plastics-specific values. When the new type drops detail, the old value was kept in `reason_code`: `trim_loss`, `setup_loss`, `rewinding_loss`, `end_of_roll_loss`, and `rejected_output`, which was finished product and is now `other`.

### Endpoints
| Method | Path | Notes |
|---|---|---|
| POST | `/waste-records` | `201` |
| GET | `/waste-records` | filters `production_order_id`, `production_run_id`, `work_center_id`, `waste_category`, `date_from`, `date_to` |
| GET | `/waste-records/summary?production_order_id=` | totals per unit, and per type and unit; `actions` |
| GET | `/waste-records/{id}` | |
| PATCH | `/waste-records/{id}` | not `production_order_id` |
| DELETE | `/waste-records/{id}` | `204` |

Every record carries `labels`: `order_number`, `order_status`, `line_no`, `work_center_name`, `run_date`, `created_by_name`, and `actions` (`edit`/`delete` when this user may). Errors answer `{"code": ...}`.

**Body (create):**
```json
{
  "production_order_id": "<uuid>",
  "production_run_id": "<uuid, optional>",
  "production_order_item_id": "<uuid, optional>",
  "waste_date": "2026-10-01",
  "quantity_wasted": "25.125",
  "unit": "kg",
  "waste_category": "startup_setup",
  "reason_code": "WARM-UP",
  "notes": "optional"
}
```
- `quantity_wasted` must be `> 0`, with up to 3 decimals (`422`); the database checks it too.
- `organization_id` is never accepted from the body (`422`).
- A work center with recorded waste cannot be deleted (`409`).

---

## Common error codes

| Code | Meaning |
|------|---------|
| 400 | Business rule violation (e.g. adding item to cancelled order) |
| 401 | Missing or expired token |
| 404 | Entity not found or belongs to a different org |
| 422 | Pydantic validation failure (e.g. quantity ≤ 0, end_time ≤ start_time) |
