# Production Module

**Status:** Sprint 3 — Baseline Complete (all 8 entities)

The production module owns the operational chain: scheduling work centers and shifts, running production orders, recording output, tracking machine downtime, and logging waste. All data is org-scoped via `TenantContext` (ADR-001). No imports from `app.commercial` or `app.foundation` models are allowed — only `app.core.*` and `app.production.*` (ADR-004).

---

## Entities and domain objects

### WorkCenter
The physical or logical production unit (machine, line, station). Root entity — no outbound FKs.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → foundation_organizations | Tenant scope |
| code | String(64) | Unique per org |
| name | String(255) | |
| center_type | Enum `extrusion/rewinding/packing/quality_station/generic` | |
| status | Enum `active/inactive/maintenance` | Default `active` |
| location | String(255) nullable | |
| notes | Text nullable | |

### ShiftDefinition
A named, recurring shift time template, independent of any work center (PROD-EXEC-FOUNDATION-001). The pre-existing work-center link is archived in `production_legacy_shift_centers` for downgrade only. `crosses_midnight` and `duration_hours` are always auto-calculated — never caller inputs.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → foundation_organizations | Tenant scope |
| code | String(64) | Unique per org |
| name | String(255) | |
| shift_type | Enum `morning/evening/night/custom` | |
| start_time | Time | HH:MM:SS |
| end_time | Time | HH:MM:SS |
| duration_hours | Numeric(5,2) | Auto-calculated — never a caller input |
| crosses_midnight | Boolean | Auto-calculated: `end_time <= start_time → True` (D5) |
| status | Enum `active/inactive` | Default `active` |

**Auto-calculation (D5):** `crosses_midnight = (end_time <= start_time)`. Applied on create and recalculated on every update that touches `start_time` or `end_time`.

### ProductionOrder
A manufacturing work order. Links to a WorkCenter and optionally a ShiftDefinition and a CommercialOrder (by plain UUID reference — no cross-module FK).

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → foundation_organizations | Tenant scope |
| production_order_number | String(64) | Auto-generated if not provided: `PO-YYYYNNNN` |
| commercial_order_id | UUID nullable | Plain reference — no FK to Commercial module |
| work_center_id | UUID FK → production_work_centers | |
| shift_definition_id | UUID FK nullable → production_shift_definitions | FK name is `shift_definition_id`, not `shift_id` (D1) |
| product_type | String(120) | |
| target_spec_json | JSON nullable | |
| planned_quantity | Numeric(14,2) | |
| unit | String(32) | |
| priority | Enum `low/normal/high/urgent` | Default `normal` (D8) |
| status | Enum `draft/planned/in_progress/completed/on_hold/cancelled` | Default `draft` |
| planned_start_date | Date nullable | |
| planned_end_date | Date nullable | |
| actual_start_date | Date nullable | |
| actual_end_date | Date nullable | |
| notes | Text nullable | |
| created_by_user_id | UUID FK → foundation_users (DB-level only) | |

**Auto-number (B2):** If `production_order_number` is not provided, the service auto-generates `PO-{year}{sequence:04d}` where sequence is `count(existing orders in year) + 1`.

**Boundary note:** `commercial_order_id` is stored as a plain UUID. The service does not validate it against any Commercial entity — this is intentional to preserve module boundaries (ADR-004).

### ProductionOrderItem
A line item within a production order. No `organization_id` — tenant isolation is cascaded through the parent order.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| production_order_id | UUID FK → production_orders | |
| line_no | Integer | Auto-assigned if not provided |
| target_spec_json | JSON nullable | |
| planned_quantity | Numeric(14,2) nullable | |
| unit | String(32) nullable | |
| notes | Text nullable | |

**Guard (B5):** Items cannot be added to a cancelled production order. The service raises `ValueError` → HTTP 400.

**Tenant isolation:** Uses `get_by_id_with_parent_org(organization_id, item_id)` — JOINs ProductionOrder and filters by `ProductionOrder.organization_id`.

### ShiftReport
Records a completed or active shift on a work center. Links to the order being worked on.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → foundation_organizations | Tenant scope |
| work_center_id | UUID FK → production_work_centers | Required (D2) |
| shift_definition_id | UUID FK nullable → production_shift_definitions | FK name `shift_definition_id` (D1) |
| production_order_id | UUID FK nullable → production_orders | |
| report_date | Date | |
| shift_started_at | DateTime(tz) nullable | |
| shift_ended_at | DateTime(tz) nullable | Auto-set to `utc_now()` when status → SUBMITTED if not provided |
| status | Enum `open/submitted/approved` | Default `open` |
| summary | Text nullable | |
| notes | Text nullable | |
| created_by_user_id | UUID FK → foundation_users (DB-level only) | |

### ProductionOutput
Records actual produced quantity for a production order on a specific work center and shift.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → foundation_organizations | Tenant scope |
| production_order_id | UUID FK → production_orders | |
| work_center_id | UUID FK → production_work_centers | Required (D2) — may differ from order's planned WC |
| production_order_item_id | UUID FK nullable → production_order_items | Cascaded tenant check if provided |
| output_date | Date | |
| recorded_at | DateTime(tz) nullable | |
| quantity_produced | Numeric(14,2) | Must be `> 0` (B8, Pydantic `Field(gt=0)`) |
| unit | String(32) | |
| output_status | Enum `recorded/verified/posted` | Default `recorded` |
| notes | Text nullable | |
| created_by_user_id | UUID FK → foundation_users (DB-level only) | |

**Quality note:** `approved_qty`, `rejected_qty`, and `rework_qty` are intentionally excluded. These belong to the future Quality module.

### DowntimeEvent
Records a period of unplanned or planned machine downtime. `status` and `duration_minutes` are always auto-derived — never caller inputs.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → foundation_organizations | Tenant scope |
| work_center_id | UUID FK → production_work_centers | Required (D2) |
| production_order_id | UUID FK nullable → production_orders | |
| start_time | DateTime(tz) | |
| end_time | DateTime(tz) nullable | |
| duration_minutes | Integer nullable | Auto-calculated (D3) |
| category | Enum `machine/setup/material/operator/quality/planned/other` | |
| reason_code | String(255) nullable | Free-text — no enum or lookup (D6) |
| status | Enum `open/closed` | Auto-derived — absent from Create/Update schemas (D4) |
| created_by_user_id | UUID FK → foundation_users (DB-level only) | |

**Auto-derivation (D3/D4):**
- `status = OPEN` when `end_time is None`; `CLOSED` when `end_time` is set
- `duration_minutes = NULL` when `end_time is None`; `int((end_time - start_time).total_seconds() // 60)` when set
- Both fields are recalculated on every update — callers cannot pass them

### WasteRecord
Records scrapped material during production. Static fact record — no status field (D7).

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → foundation_organizations | Tenant scope |
| production_order_id | UUID FK → production_orders | |
| work_center_id | UUID FK → production_work_centers | Required (D2) |
| production_order_item_id | UUID FK nullable → production_order_items | |
| waste_date | Date | |
| quantity_wasted | Numeric(14,2) | Must be `> 0` (B9, Pydantic `Field(gt=0)`) |
| unit | String(32) | |
| waste_category | Enum `startup_loss/process_defect/material_defect/machine_fault/rejected_output/other` | |
| reason_code | String(255) nullable | Free-text — no enum or lookup (D6) |
| notes | Text nullable | |
| created_by_user_id | UUID FK → foundation_users (DB-level only) | |

**No status (D7):** WasteRecord has no status field by design. It is a factual record of material lost — not a workflow entity. Costing and scrap inventory posting are deferred post-Sprint 3.

---

## Enum reference

| Enum | Values |
|------|--------|
| WorkCenterType | `extrusion` / `rewinding` / `packing` / `quality_station` / `generic` |
| WorkCenterStatus | `active` / `inactive` / `maintenance` |
| ShiftType | `morning` / `evening` / `night` / `custom` |
| ShiftDefinitionStatus | `active` / `inactive` |
| ProductionOrderStatus | `draft` / `planned` / `in_progress` / `completed` / `on_hold` / `cancelled` |
| ProductionOrderPriority | `low` / `normal` / `high` / `urgent` |
| ShiftReportStatus | `open` / `submitted` / `approved` |
| ProductionOutputStatus | `recorded` / `verified` / `posted` |
| DowntimeCategory | `machine` / `setup` / `material` / `operator` / `quality` / `planned` / `other` |
| DowntimeStatus | `open` / `closed` |
| WasteCategory | `startup_loss` / `process_defect` / `material_defect` / `machine_fault` / `rejected_output` / `other` |

---

## Execution: rosters, runs and actual teams (PROD-EXEC-FOUNDATION-001)

- **ShiftRoster** — the planned team of a shift over a dated period (`effective_from` … `effective_to`, open-ended when null). Periods of one shift never overlap. A worker is on at most one roster at a time across all shifts; moving a worker to another shift means closing or replacing the old roster, so history is never overwritten.
- Roster membership is frozen once the roster is effective or referenced by a run; changes go through a dated **replacement** (`POST /shift-rosters/{id}/replace`), which closes the old period the day before.
- **Backdated rosters** — `POST /shift-rosters` accepts a past `effective_from` so historical teams can be backfilled into gaps. The overlap rules still apply, so existing history cannot be overwritten this way.
- **ProductionRun** — one execution of a production order on a required work center, with an optional shift and optional roster. Runs are only created or started for orders in `draft`, `released` or `in_progress`.
- **ProductionRunMember** — the actual team, keyed by `WorkforceMember` (never `User`). Loading a roster copies active members once; later roster changes never touch the run. Only active workers can join a roster or run.
- Participation times are recorded once a run starts: members are stamped with the run start, cannot start before it, and open participations are closed when the run completes or is cancelled. A replacement is recorded by ending one participation and adding another; a worker may rejoin later with a new, non-overlapping participation (at most one open participation per worker per run).
- Every roster and run mutation writes a tenant activity-log entry (`shift_roster.*`, `production_run.*`) with the acting User as `actor_id`.

**Permissions.** `production:shifts:{read,create,update,delete}`, `production:shift_rosters:{read,create,update,manage_members}`, `production:runs:{read,create,update,start,pause,complete,cancel,manage_members}`. Migrations copy existing grants: `shift_definitions:read` → `shifts:read`, `shift_definitions:write` → `shifts:create/update/delete`, `runs:update` → `runs:pause/cancel`. Migration `f6a1b2i0` later granted roster and run permissions to the organization administrator, factory manager and production manager system roles (and read to viewer); custom roles keep what an administrator gave them.

**Database-level guarantees.** Same-organization links and roster-period overlap are enforced in the service layer (tenant-scoped lookups, shift row lock), not by composite foreign keys or an `EXCLUDE` constraint. That keeps the schema portable to SQLite test runs; revisit if other writers bypass the service.

---

## Permissions (PROD-RBAC-001)

`app/production/domain/permissions.py` is the only place a production permission code is written. The catalog, the system roles, routes, services and the frontend (`frontend/src/lib/production-permissions.ts`, kept identical by a test) use its names.

| Resource | Actions |
|---|---|
| work_centers | read, create, update, delete |
| shifts | read, create, update, delete |
| shift_rosters | read, create, update, manage_members |
| demands | read, create, update, delete |
| planning | read, sequence, allocate, release_allocation |
| production_orders | read, update, manage_items, create, release, start, hold, complete, close, cancel |
| runs | read, create, update, start, pause, complete, cancel, manage_members |
| results | read, create, update, delete, correct |
| downtime_events | read, create, update, delete, close |
| waste_records | read, create, update, delete |

Reports: `reports:production:{order_full,orders_summary,results_analysis,shift_workforce}`. There is no export history screen; each report prints who prepared it.

- **Order actions.** `ORDER_TRANSITIONS` maps each lifecycle action to a permission. `return_to_draft` needs `release`, and `resume` needs `start`.
- **Per-entity actions.** The `actions` lists returned for results, downtime and waste are computed one permission at a time. A user with only `update` sees `edit` and nothing else.
- **Production manager.** This role holds all 52 production codes and the 5 report codes, listed explicitly; no system role uses a production wildcard. To give a person part of production, create a role in the admin roles screen and tick the actions they need.
- **Every route declares its permission.** It uses `require_permission`, `require_any_permission`, or `permission_checked_in_handler` when the code depends on the request (an order action, a report). A test fails on any production or report route without one.
- **Lookups.** A report lookup needs a report permission plus the read permission of the entity it lists: `production_orders:read` for orders and products, `work_centers:read` for centers, `commercial:customers:read` for customers.
- **Dashboard.** It returns production counts only with `production_orders:read`, and quality counts only with `quality:quality_checks:read`.
- **Migration `f6a1b2h9`.** It replaced the bundled codes; each holder got every replacement with the same scope:

  | Old code | Replaced by |
  |---|---|
  | `work_centers:write` | create, update, delete |
  | `production_orders:write` | update, manage_items |
  | `orders:<action>` | `production_orders:<action>` |
  | `results:write` | create, update, delete |
  | `downtime_events:write` | create, update, delete, close |
  | `waste_records:write` | create, update, delete |
  | `shift_definitions:*` | removed (no route used it) |

  Its backup table makes the downgrade exact.

## Tenant isolation pattern

Three levels of isolation enforce ADR-001:

1. **Entity isolation** — `get_by_id(organization_id, entity_id)` dual filter on all 8 root entities.
2. **Cross-reference validation** — Service layer validates that all FK references (work_center_id, shift_definition_id, production_order_id) belong to the same org before insert.
3. **Cascaded isolation** — `ProductionOrderItem` carries no `organization_id`; the repository JOINs `ProductionOrder` and filters by `ProductionOrder.organization_id`.

`organization_id` is never accepted from the caller — it is always read from `TenantContext` (the authenticated JWT).

---

## Module boundary rules (ADR-004)

- No Python imports from `app.commercial.*` or `app.foundation.infrastructure.models`
- `commercial_order_id` on `ProductionOrder` is a plain `UUID` column with no FK constraint — storing a reference ID only
- `created_by_user_id` uses `ForeignKey("foundation_users.id")` at DB level only — no import of the Foundation `User` model into Production code
- `DowntimeCategory.QUALITY` and `WasteCategory.REJECTED_OUTPUT` are operational classifications — no quality business logic lives in this module

---

## Implemented routes

All routes require a valid Bearer token. All results are scoped to the caller's `organization_id`.

See [docs/api/production.md](../api/production.md) for the full endpoint list.
