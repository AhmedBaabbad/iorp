# PROD-PLAN-003 — Planning queue lifecycle and allocation release

The planning queue is a derived view over `production_demands`. Nothing is moved or deleted when a demand is fully planned.

## Allocation lifecycle

| Status | Meaning |
|---|---|
| `active` | Reserves demand quantity. Default. |
| `released` | History only; never counts as planned. Keeps `released_at`, `released_by_user_id`, `release_reason`. |

Migration `f6a1b2g8` adds the columns. Existing rows become `active`. A check constraint enforces `active ⇔ released_at IS NULL`. Downgrade is refused while released rows exist.

## Quantities (per demand item, never stored)

- `active_allocated_quantity` = sum of `active` allocations
- `released_allocated_quantity` = sum of `released` allocations
- `remaining_quantity` = `required_quantity − active_allocated_quantity`
- `planning_state`: `0` → `ready_for_planning`, `0 < a < required` → `partially_planned`, `a = required` → `planned`

Over-allocation returns `409 ALLOCATION_QUANTITY_CONFLICT` (`reason: OVER_ALLOCATION`).

## Demand header status

Recomputed after every allocation, release and cancellation. `draft` and `cancelled` are never overwritten. Clients cannot set `partially_planned` or `planned` (`409 status_derived_from_allocations`).

## Release and cancellation

| Order status | Release / cancel allowed |
|---|---|
| `draft` | yes |
| `released` | yes, unless execution records exist (started run, shift report, output, downtime, waste) |
| `in_progress` | no — `409 ORDER_EXECUTION_STARTED` |
| `completed` | no — `409 ORDER_COMPLETED` |
| `cancelled` | already released |

- `POST /api/v1/production/allocations/{id}/release` `{ "reason": "..." }` — permission `production:planning:release_allocation`. The order's `planned_quantity` is reduced to its remaining active allocations. The last active allocation of an open order cannot be released (`409 LAST_ACTIVE_ALLOCATION`); cancel the order instead.
- `POST /api/v1/production/production-orders/{id}/cancel` `{ "reason": "..." }` — permission `production:orders:cancel`. In one transaction: cancels the order, releases every active allocation, and resyncs every affected demand. `PATCH status=cancelled` is rejected.

## Planning queue

`GET /api/v1/production/planning/demands?view=active|planned|all` (default `active`). Filtering and pagination run in the database.

**Status picker (later).** The planning screen and the demands list share one control, «الحالات المعروضة»: a dropdown of status checkboxes, with «إظهار الكل» and «الافتراضي».
- **Planning default:** «جاهز للتخطيط» and «مخطط جزئياً». With exactly that selection the screen is the planning queue (`view=active`): sequence order, reordering and allocation.
- **Other selections:** read-only, using `view=all&statuses=...`.
- **Demands list default:** finished demands, fully planned and cancelled, are hidden.
- **API:** both endpoints accept repeated `statuses` and return `hidden_by_status`, the number of demands left out, which the screen reports.
- **Saving the choice:** it is kept per screen in the browser, and in the page URL (`?statuses=`) when it differs from the default. Older `?view=planned|all` links still open the matching statuses.

- `active`: status `ready_for_planning`/`partially_planned` and at least one item with remaining > 0
- `planned`: status `planned`
- `all`: every demand in the organization

## Concurrency

Every writer takes the organization mutex (`production_demand_counters`, year 0) first, then row locks (`FOR UPDATE`) on the demand item, order and allocations. Quantity is re-summed inside the lock. The order-status PATCH and run start/creation also lock the order row (`FOR UPDATE`). Without that, either could interleave with a cancellation, leaving an order that is running with only released allocations. `tests/test_production_allocation_postgres.py` proves all of this on PostgreSQL (`RUN_POSTGRES_TESTS=1`).

## Frontend

- Planning queue tabs (`active` default, `planned`, `all`) are kept in the URL (`?view=`).
- Release and cancel ask for a reason in an in-page dialog. They are only offered for `draft`/`released` orders, and the server remains the authority.
- Tests: `npm test` in `frontend/` runs `node --test tests/*.test.mjs` (pure rules) and `vitest run` (component tests in `tests/components/`, jsdom).
