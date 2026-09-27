# ERD Notes — Sprint 3

8 new tables added in one Alembic migration. All primary keys are UUIDs. Foundation, Sprint 1, and Sprint 2 tables: see [sprint-1.md](sprint-1.md) and [sprint-2.md](sprint-2.md).

---

## Production tables (Sprint 3)

```
production_work_centers
  id                UUID PK
  organization_id   UUID FK → foundation_organizations   index
  code              VARCHAR(64)   NOT NULL
  name              VARCHAR(255)  NOT NULL
  center_type       ENUM(extrusion, rewinding, packing, quality_station, generic)   NOT NULL
  status            ENUM(active, inactive, maintenance)   NOT NULL   DEFAULT 'active'
  location          VARCHAR(255)  nullable
  notes             TEXT          nullable
  created_at        TIMESTAMPTZ
  updated_at        TIMESTAMPTZ
  UNIQUE (organization_id, code)

production_shift_definitions
  id                UUID PK
  organization_id   UUID FK → foundation_organizations       index
  work_center_id    UUID FK → production_work_centers        index
  code              VARCHAR(64)   NOT NULL
  name              VARCHAR(255)  NOT NULL
  shift_type        ENUM(morning, evening, night, custom)    NOT NULL
  start_time        TIME          NOT NULL
  end_time          TIME          NOT NULL
  duration_hours    NUMERIC(5,2)  NOT NULL   -- auto-calculated, never caller input
  crosses_midnight  BOOLEAN       NOT NULL   -- auto-calculated: end_time <= start_time (D5)
  status            ENUM(active, inactive)   NOT NULL   DEFAULT 'active'
  created_at        TIMESTAMPTZ
  updated_at        TIMESTAMPTZ
  UNIQUE (organization_id, code)

production_orders
  id                          UUID PK
  organization_id             UUID FK → foundation_organizations         index
  production_order_number     VARCHAR(64)   NOT NULL                     -- auto: PO-YYYYNNNN
  commercial_order_id         UUID          nullable                     -- plain ref, NO FK (module boundary)
  work_center_id              UUID FK → production_work_centers          index
  shift_definition_id         UUID FK nullable → production_shift_definitions   -- named shift_definition_id (D1)
  product_type                VARCHAR(120)  NOT NULL
  target_spec_json            JSON          nullable
  planned_quantity            NUMERIC(14,2) NOT NULL
  unit                        VARCHAR(32)   NOT NULL
  priority                    ENUM(low, normal, high, urgent)            DEFAULT 'normal'   -- D8
  status                      ENUM(draft, planned, in_progress, completed, on_hold, cancelled)   DEFAULT 'draft'
  planned_start_date          DATE          nullable
  planned_end_date            DATE          nullable
  actual_start_date           DATE          nullable
  actual_end_date             DATE          nullable
  notes                       TEXT          nullable
  created_by_user_id          UUID FK → foundation_users
  created_at                  TIMESTAMPTZ
  updated_at                  TIMESTAMPTZ
  UNIQUE (organization_id, production_order_number)

production_order_items
  id                      UUID PK
  production_order_id     UUID FK → production_orders   index  (cascade delete)
  line_no                 INTEGER       NOT NULL
  target_spec_json        JSON          nullable
  planned_quantity        NUMERIC(14,2) nullable
  unit                    VARCHAR(32)   nullable
  notes                   TEXT          nullable
  created_at              TIMESTAMPTZ
  updated_at              TIMESTAMPTZ
  -- NO organization_id: tenant isolation cascaded via parent order JOIN

production_shift_reports
  id                    UUID PK
  organization_id       UUID FK → foundation_organizations         index
  work_center_id        UUID FK → production_work_centers          index   -- required (D2)
  shift_definition_id   UUID FK nullable → production_shift_definitions    -- shift_definition_id (D1)
  production_order_id   UUID FK nullable → production_orders       index
  report_date           DATE          NOT NULL
  shift_started_at      TIMESTAMPTZ   nullable
  shift_ended_at        TIMESTAMPTZ   nullable   -- auto-set on SUBMITTED when null
  status                ENUM(open, submitted, approved)   NOT NULL   DEFAULT 'open'
  summary               TEXT          nullable
  notes                 TEXT          nullable
  created_by_user_id    UUID FK → foundation_users
  created_at            TIMESTAMPTZ
  updated_at            TIMESTAMPTZ

production_outputs
  id                          UUID PK
  organization_id             UUID FK → foundation_organizations         index
  production_order_id         UUID FK → production_orders                index
  work_center_id              UUID FK → production_work_centers          index   -- required (D2)
  shift_report_id             UUID FK nullable → production_shift_reports
  production_order_item_id    UUID FK nullable → production_order_items
  output_date                 DATE          NOT NULL
  recorded_at                 TIMESTAMPTZ   nullable
  quantity_produced           NUMERIC(14,2) NOT NULL   -- gt=0 enforced (B8)
  unit                        VARCHAR(32)   NOT NULL
  output_status               ENUM(recorded, verified, posted)   NOT NULL   DEFAULT 'recorded'
  notes                       TEXT          nullable
  created_by_user_id          UUID FK → foundation_users
  created_at                  TIMESTAMPTZ
  updated_at                  TIMESTAMPTZ
  -- NOTE: approved_qty / rejected_qty / rework_qty intentionally excluded — Quality module scope

production_downtime_events
  id                    UUID PK
  organization_id       UUID FK → foundation_organizations         index
  work_center_id        UUID FK → production_work_centers          index   -- required (D2)
  shift_report_id       UUID FK nullable → production_shift_reports
  production_order_id   UUID FK nullable → production_orders       index
  start_time            TIMESTAMPTZ   NOT NULL
  end_time              TIMESTAMPTZ   nullable
  duration_minutes      INTEGER       nullable   -- auto-calculated (D3); NULL when end_time is NULL
  category              ENUM(machine, setup, material, operator, quality, planned, other)   NOT NULL
  reason_code           VARCHAR(255)  nullable   -- free-text, no FK (D6)
  status                ENUM(open, closed)   NOT NULL   -- auto-derived (D4); absent from API input
  created_by_user_id    UUID FK → foundation_users
  created_at            TIMESTAMPTZ
  updated_at            TIMESTAMPTZ

production_waste_records
  id                          UUID PK
  organization_id             UUID FK → foundation_organizations         index
  production_order_id         UUID FK → production_orders                index
  work_center_id              UUID FK → production_work_centers          index   -- required (D2)
  shift_report_id             UUID FK nullable → production_shift_reports
  production_order_item_id    UUID FK nullable → production_order_items
  waste_date                  DATE          NOT NULL
  quantity_wasted             NUMERIC(14,2) NOT NULL   -- gt=0 enforced (B9)
  unit                        VARCHAR(32)   NOT NULL
  waste_category              ENUM(startup_loss, process_defect, material_defect, machine_fault, rejected_output, other)   NOT NULL
  reason_code                 VARCHAR(255)  nullable   -- free-text, no FK (D6)
  notes                       TEXT          nullable
  created_by_user_id          UUID FK → foundation_users
  created_at                  TIMESTAMPTZ
  updated_at                  TIMESTAMPTZ
  -- NOTE: no status field by design (D7) — WasteRecord is a static fact record
```

---

## Relationships summary (Sprint 3 additions)

```
foundation_organizations       1──* production_work_centers
foundation_organizations       1──* production_shift_definitions
foundation_organizations       1──* production_orders
foundation_organizations       1──* production_shift_reports
foundation_organizations       1──* production_outputs
foundation_organizations       1──* production_downtime_events
foundation_organizations       1──* production_waste_records

production_work_centers        1──* production_shift_definitions
production_work_centers        1──* production_orders
production_work_centers        1──* production_shift_reports
production_work_centers        1──* production_outputs
production_work_centers        1──* production_downtime_events
production_work_centers        1──* production_waste_records

production_orders              1──* production_order_items         (cascade delete)
production_orders              1──* production_shift_reports
production_orders              1──* production_outputs
production_orders              1──* production_downtime_events
production_orders              1──* production_waste_records

production_shift_definitions   1──* production_shift_reports
production_shift_definitions   1──* production_orders              (optional)

production_shift_reports       1──* production_outputs             (optional)
production_shift_reports       1──* production_downtime_events     (optional)
production_shift_reports       1──* production_waste_records       (optional)

production_order_items         1──* production_outputs             (optional)
production_order_items         1──* production_waste_records       (optional)

foundation_users               1──* production_orders              (created_by_user_id — DB FK only)
foundation_users               1──* production_shift_reports       (created_by_user_id — DB FK only)
foundation_users               1──* production_outputs             (created_by_user_id — DB FK only)
foundation_users               1──* production_downtime_events     (created_by_user_id — DB FK only)
foundation_users               1──* production_waste_records       (created_by_user_id — DB FK only)
```

---

## Boundary note

`production_orders.commercial_order_id` stores a UUID reference to a commercial order. There is **no FK constraint** at the database level — this is intentional to maintain module boundary separation (ADR-004). The value is not validated during insert.

---

## Migration chain

| Migration | Description |
|-----------|-------------|
| `ec914090210c` | Foundation tables (organizations, users, roles, permissions) |
| `b41f7a2c9d13` | `commercial_customers` |
| `c72a8bb29d44` | `commercial_customer_interactions` |
| `d83be9fa7120` | `commercial_follow_ups` |
| `7f3a9c2e` | `commercial_samples` |
| `4b8e2a91` | `commercial_sample_evaluations` |
| `9c1d4f70` | `commercial_quotes` + `commercial_quote_items` |
| `2a6b8d3f` | `commercial_orders` + `commercial_order_items` |
| `3c7f1a9b` | Unique constraint on `(customer_id, sample_code)` |
| `6f2a8c1d` ← HEAD | All 8 production tables |

Run `alembic upgrade head` from `backend/` to apply all migrations.
