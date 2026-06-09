# ERD Notes — Sprint 2

6 new tables added across 5 Alembic migrations. All primary keys are UUIDs. Foundation and Sprint 1 tables: see [sprint-1.md](sprint-1.md).

---

## Commercial tables (Sprint 2)

```
commercial_samples
  id                    UUID PK
  customer_id           UUID FK → commercial_customers
  sample_code           VARCHAR(64)   NOT NULL  index
  product_type          VARCHAR(120)  NOT NULL
  requested_spec_json   JSON          nullable
  quantity_requested    NUMERIC(14,2) nullable
  unit                  VARCHAR(32)   nullable
  request_date          TIMESTAMPTZ   NOT NULL
  status                ENUM(requested, in_preparation, delivered, evaluated, cancelled)
  notes                 TEXT          nullable
  created_by_user_id    UUID FK → foundation_users
  created_at            TIMESTAMPTZ
  updated_at            TIMESTAMPTZ
  UNIQUE (customer_id, sample_code)

commercial_sample_evaluations
  id                    UUID PK
  sample_id             UUID FK → commercial_samples   index
  evaluation_date       TIMESTAMPTZ   NOT NULL
  result_status         ENUM(accepted, rejected, needs_modification)
  comments              TEXT          nullable
  next_action           ENUM(proceed_to_quote, revise_sample, close_request, further_review)
  evaluated_by_user_id  UUID FK → foundation_users
  created_at            TIMESTAMPTZ

commercial_quotes
  id                    UUID PK
  organization_id       UUID FK → foundation_organizations   index
  customer_id           UUID FK → commercial_customers       index
  sample_id             UUID FK → commercial_samples         nullable  index
  quote_number          VARCHAR(64)   NOT NULL
  issue_date            TIMESTAMPTZ   NOT NULL
  valid_until           TIMESTAMPTZ   NOT NULL
  status                ENUM(draft, issued, accepted, rejected, expired)
  currency              VARCHAR(3)    NOT NULL   -- ISO 4217
  subtotal_amount       NUMERIC(14,2) NOT NULL
  discount_amount       NUMERIC(14,2) NOT NULL
  tax_amount            NUMERIC(14,2) NOT NULL
  total_amount          NUMERIC(14,2) NOT NULL
  notes                 TEXT          nullable
  created_by_user_id    UUID FK → foundation_users
  created_at            TIMESTAMPTZ
  updated_at            TIMESTAMPTZ
  UNIQUE (organization_id, quote_number)

commercial_quote_items
  id                    UUID PK
  quote_id              UUID FK → commercial_quotes   index  (cascade delete)
  line_no               INTEGER       NOT NULL
  product_type          VARCHAR(120)  NOT NULL
  requested_spec_json   JSON          nullable
  quantity              NUMERIC(14,2) NOT NULL
  unit                  VARCHAR(32)   NOT NULL
  unit_price            NUMERIC(14,2) NOT NULL
  line_total            NUMERIC(14,2) NOT NULL

commercial_orders
  id                        UUID PK
  organization_id           UUID FK → foundation_organizations   index
  customer_id               UUID FK → commercial_customers       index
  quote_id                  UUID FK → commercial_quotes          nullable  index
  order_number              VARCHAR(64)   NOT NULL
  order_date                TIMESTAMPTZ   NOT NULL
  status                    ENUM(draft, confirmed, cancelled, converted_to_production)
  requested_delivery_date   TIMESTAMPTZ   nullable
  notes                     TEXT          nullable
  created_by_user_id        UUID FK → foundation_users
  created_at                TIMESTAMPTZ
  updated_at                TIMESTAMPTZ
  UNIQUE (organization_id, order_number)

commercial_order_items
  id                    UUID PK
  commercial_order_id   UUID FK → commercial_orders   index  (cascade delete)
  line_no               INTEGER       NOT NULL
  product_type          VARCHAR(120)  NOT NULL
  requested_spec_json   JSON          nullable
  quantity              NUMERIC(14,2) NOT NULL
  unit                  VARCHAR(32)   NOT NULL
  agreed_unit_price     NUMERIC(14,2) nullable
  line_total            NUMERIC(14,2) nullable
```

---

## Relationships summary (Sprint 2 additions)

```
commercial_customers       1──* commercial_samples
commercial_samples         1──* commercial_sample_evaluations
foundation_users           1──* commercial_sample_evaluations  (evaluated_by_user_id)
foundation_users           1──* commercial_samples             (created_by_user_id)

foundation_organizations   1──* commercial_quotes
commercial_customers       1──* commercial_quotes
commercial_samples         1──* commercial_quotes              (sample_id, optional)
commercial_quotes          1──* commercial_quote_items         (cascade delete)
foundation_users           1──* commercial_quotes              (created_by_user_id)

foundation_organizations   1──* commercial_orders
commercial_customers       1──* commercial_orders
commercial_quotes          1──* commercial_orders              (quote_id, optional)
commercial_orders          1──* commercial_order_items         (cascade delete)
foundation_users           1──* commercial_orders              (created_by_user_id)
```

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
| `3c7f1a9b` ← HEAD | Unique constraint on `(customer_id, sample_code)` |

Run `alembic upgrade head` from `backend/` to apply all migrations.
