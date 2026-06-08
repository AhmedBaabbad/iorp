# ERD Notes — Sprint 1

9 tables implemented across 4 Alembic migrations. All primary keys are UUIDs.

---

## Foundation tables

```
foundation_organizations
  id              UUID PK
  name            VARCHAR(255)
  code            VARCHAR(64)   UNIQUE
  status          ENUM(active, inactive)
  industry_type   VARCHAR(120)  nullable
  timezone        VARCHAR(64)
  created_at      TIMESTAMPTZ
  updated_at      TIMESTAMPTZ

foundation_users
  id              UUID PK
  organization_id UUID FK → foundation_organizations
  full_name       VARCHAR(255)
  email           VARCHAR(255)
  phone           VARCHAR(50)   nullable
  password_hash   VARCHAR(255)
  status          ENUM(active, inactive, suspended)
  last_login_at   TIMESTAMPTZ   nullable
  created_at      TIMESTAMPTZ
  updated_at      TIMESTAMPTZ
  UNIQUE (organization_id, email)

foundation_roles
  id              UUID PK
  organization_id UUID FK → foundation_organizations
  name            VARCHAR(120)
  code            VARCHAR(64)
  description     TEXT          nullable
  created_at      TIMESTAMPTZ
  updated_at      TIMESTAMPTZ
  UNIQUE (organization_id, code)

foundation_permissions
  id              UUID PK
  code            VARCHAR(120)  UNIQUE  -- e.g. "commercial:customers:write"
  name            VARCHAR(120)
  module_name     VARCHAR(80)
  action_name     VARCHAR(80)

foundation_role_permissions
  id              UUID PK
  role_id         UUID FK → foundation_roles
  permission_id   UUID FK → foundation_permissions
  UNIQUE (role_id, permission_id)

foundation_user_roles
  id              UUID PK
  user_id         UUID FK → foundation_users
  role_id         UUID FK → foundation_roles
  UNIQUE (user_id, role_id)
```

---

## Commercial tables (Sprint 1)

```
commercial_customers
  id                      UUID PK
  organization_id         UUID FK → foundation_organizations
  customer_code           VARCHAR(64)
  name                    VARCHAR(255)
  sector                  VARCHAR(120)  nullable
  city                    VARCHAR(120)  nullable
  country                 VARCHAR(120)  nullable
  status                  ENUM(active, inactive)
  relationship_stage      ENUM(lead, prospect, customer)
  priority_level          ENUM(low, medium, high)
  opportunity_source      VARCHAR(120)  nullable
  estimated_consumption   NUMERIC(14,2) nullable
  assigned_sales_user_id  UUID FK → foundation_users  nullable
  notes                   TEXT          nullable
  created_at              TIMESTAMPTZ
  updated_at              TIMESTAMPTZ
  UNIQUE (organization_id, customer_code)

commercial_customer_interactions
  id                  UUID PK
  customer_id         UUID FK → commercial_customers
  interaction_type    ENUM(call, visit, whatsapp, email, meeting)
  interaction_date    TIMESTAMPTZ
  subject             VARCHAR(255)
  summary             TEXT         nullable
  outcome             VARCHAR(255) nullable
  next_step_hint      VARCHAR(255) nullable
  created_by_user_id  UUID FK → foundation_users
  created_at          TIMESTAMPTZ

commercial_follow_ups
  id               UUID PK
  customer_id      UUID FK → commercial_customers
  interaction_id   UUID FK → commercial_customer_interactions  nullable
  assigned_user_id UUID FK → foundation_users
  due_date         TIMESTAMPTZ
  priority         ENUM(low, medium, high)
  status           ENUM(pending, completed, cancelled)
  reason           VARCHAR(255)
  notes            TEXT        nullable
  completed_at     TIMESTAMPTZ nullable
  created_at       TIMESTAMPTZ
```

---

## Relationships summary

```
foundation_organizations 1──* foundation_users
foundation_organizations 1──* foundation_roles
foundation_roles         *──* foundation_permissions   (via role_permissions)
foundation_users         *──* foundation_roles         (via user_roles)

foundation_organizations 1──* commercial_customers
foundation_users         1──* commercial_customers     (assigned_sales_user_id, optional)
commercial_customers     1──* commercial_customer_interactions
commercial_customers     1──* commercial_follow_ups
commercial_customer_interactions 1──* commercial_follow_ups  (interaction_id, optional)
foundation_users         1──* commercial_customer_interactions  (created_by_user_id)
foundation_users         1──* commercial_follow_ups            (assigned_user_id)
```

---

## Planned tables (not yet implemented)

| Table | Sprint |
|-------|--------|
| `commercial_samples` | Sprint 2 |
| `commercial_sample_evaluations` | Sprint 2 |
| `commercial_quotes` | Sprint 2 |
| `commercial_orders` | Sprint 3 |
| Production module tables | Future |
| Quality module tables | Future |
