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

## Production Outputs

### `POST /production-outputs`
Record produced quantity.

**Body:**
```json
{
  "production_order_id": "<uuid>",
  "work_center_id": "<uuid>",
  "production_order_item_id": "<uuid>",
  "output_date": "2026-07-02",
  "recorded_at": "2026-07-02T11:00:00Z",
  "quantity_produced": "850.00",
  "unit": "kg",
  "notes": "optional"
}
```
`work_center_id` required (D2). `quantity_produced` must be `> 0` — returns `422` if zero or negative (B8). Returns `201`.

### `GET /production-outputs`
List production outputs.

**Query filters:** `production_order_id`, `work_center_id`, `output_date`, `output_status`

### `GET /production-outputs/{id}`
Get a single production output.

### `PATCH /production-outputs/{id}`
Update a production output.

---

## Downtime Events

### `POST /downtime-events`
Record a downtime event. `status` and `duration_minutes` are always auto-derived — never include them in the request.

**Body (open downtime — no end_time):**
```json
{
  "work_center_id": "<uuid>",
  "start_time": "2026-07-02T13:30:00Z",
  "category": "machine",
  "reason_code": "Hydraulic pump pressure drop",
  "production_order_id": "<uuid>"
}
```

**Body (closed downtime — with end_time):**
```json
{
  "work_center_id": "<uuid>",
  "start_time": "2026-07-02T09:00:00Z",
  "end_time": "2026-07-02T09:45:00Z",
  "category": "setup",
  "reason_code": "Die head cleaning"
}
```

`work_center_id` required (D2). A `422` is returned if `end_time <= start_time`. Returns `201`.

**Auto-derived fields in response (D3/D4):**
- `status`: `open` when `end_time` is absent; `closed` when `end_time` is present
- `duration_minutes`: `null` when open; `int((end_time - start_time).total_seconds() // 60)` when closed

### `GET /downtime-events`
List downtime events.

**Query filters:** `work_center_id`, `production_order_id`, `status`, `category`, `start_date`

### `GET /downtime-events/{id}`
Get a single downtime event.

### `PATCH /downtime-events/{id}`
Update a downtime event. Passing `end_time` transitions status to `closed` and calculates `duration_minutes`. Removing `end_time` transitions status back to `open`.

---

## Waste Records

### `POST /waste-records`
Record a waste/scrap event. WasteRecord has no status field.

**Body:**
```json
{
  "production_order_id": "<uuid>",
  "work_center_id": "<uuid>",
  "production_order_item_id": "<uuid>",
  "waste_date": "2026-07-02",
  "quantity_wasted": "25.00",
  "unit": "kg",
  "waste_category": "startup_loss",
  "reason_code": "Film tear during startup",
  "notes": "optional"
}
```
`work_center_id` required (D2). `quantity_wasted` must be `> 0` — returns `422` if zero or negative (B9). Returns `201`.

### `GET /waste-records`
List waste records.

**Query filters:** `production_order_id`, `work_center_id`, `waste_category`, `waste_date`

### `GET /waste-records/{id}`
Get a single waste record.

### `PATCH /waste-records/{id}`
Update a waste record.

---

## Common error codes

| Code | Meaning |
|------|---------|
| 400 | Business rule violation (e.g. adding item to cancelled order) |
| 401 | Missing or expired token |
| 404 | Entity not found or belongs to a different org |
| 422 | Pydantic validation failure (e.g. quantity ≤ 0, end_time ≤ start_time) |
