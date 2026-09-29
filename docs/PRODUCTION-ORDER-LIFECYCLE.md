# Production order status lifecycle

Order status is changed only by `OrderStatusService` (`backend/app/production/application/order_status_service.py`). The rules come from `backend/app/production/domain/order_lifecycle.py`. The generic `PATCH /production-orders/{id}` rejects `status` (422).

## Statuses

| Code | Arabic | Meaning |
|---|---|---|
| `draft` | مسودة | Being prepared; lines and allocations can still change |
| `released` | معتمد | Approved for production; quantities locked |
| `in_progress` | قيد التنفيذ | Production running; `actual_start_at` is set on the first start |
| `on_hold` | موقوف مؤقتاً | Paused for a stated reason |
| `completed` | مكتمل | Production finished; `actual_end_at` is set |
| `closed` | مغلق | Final review done; archived (terminal) |
| `cancelled` | ملغي | Cancelled before production; allocations returned to planning (terminal) |

## Actions

| Action | From → To | Permission | Reason |
|---|---|---|---|
| release | draft → released | `production:orders:release` | — |
| return_to_draft | released → draft | `production:orders:release` | — |
| start | released → in_progress | `production:orders:start` | — |
| hold | in_progress → on_hold | `production:orders:hold` | required |
| resume | on_hold → in_progress | `production:orders:hold` | — |
| complete | in_progress → completed | `production:orders:complete` | — |
| close | completed → closed | `production:orders:close` | optional (confirmation) |
| cancel | draft/released → cancelled | `production:orders:cancel` | required (confirmation) |

- `POST /production-orders/{id}/transitions` `{ action, reason?, expected_version? }` applies an action.
  - A stale `expected_version` returns `409 ORDER_STATUS_CHANGED`.
  - A disallowed pair returns `409 TRANSITION_NOT_ALLOWED`.
  - A missing permission returns `403 ACTION_FORBIDDEN`.
- `GET /production-orders/{id}` includes `lifecycle`: the version, the actual dates, the late flags, and only the actions this user may take now.
- `GET /production-orders/{id}/status-history` returns every transition: from, to, action, trigger (`manual`/`activity`/`schedule`), actor (null means system), reason and time.
- `POST /production-orders/{id}/cancel` remains for existing clients and equals the `cancel` action.

## Dates and automation

- Planned dates never change status. The late flags are computed:
  - `start_overdue`: draft or released, and past the planned start.
  - `finish_overdue`: not yet completed, and past the planned end.
- Date-based start is opt-in. `PRODUCTION_AUTO_START_BY_DATE=true` runs an in-process loop every `PRODUCTION_AUTO_START_INTERVAL_MINUTES`. It moves due `released` orders to `in_progress` with trigger `schedule`. It is idempotent and skips locked rows.
- `OrderStatusService.start_from_activity(order_id, source)` is the extension point for starting an order on its first recorded production activity. It is not wired yet; shift reports and outputs will call it once they are revised.

Migration: `f6a1b2h0` adds the `on_hold`/`closed` enum values, the actual dates, `status_version`, the history table, and the new permissions. The new permissions are granted to every role holding `production:production_orders:write`.
