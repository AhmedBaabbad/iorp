# Commercial Module

**Status:** Sprint 1 — Slice 1 Complete (customers, interactions, follow-ups)

The commercial module owns the CRM-side of the business: customer records, logged interactions, and follow-up tasks. It calls Foundation's application layer to validate user membership (ADR-004). All data is org-scoped via `TenantContext` (ADR-001).

---

## Sprint 1 domain objects

### Customer
A commercial account record. Unique per `(organization_id, customer_code)`.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → foundation_organizations | Tenant scope |
| customer_code | String(64) | Unique per org |
| name | String(255) | |
| sector | String(120) nullable | |
| city | String(120) nullable | |
| country | String(120) nullable | |
| status | Enum `active/inactive` | Default `active` |
| relationship_stage | Enum `lead/prospect/customer` | Default `lead` |
| priority_level | Enum `low/medium/high` | Default `medium` |
| opportunity_source | String(120) nullable | |
| estimated_consumption | Numeric(14,2) nullable | |
| assigned_sales_user_id | UUID FK → foundation_users nullable | Must belong to same org |
| notes | Text nullable | |

### CustomerInteraction
A logged touchpoint (call, visit, WhatsApp, email, meeting).

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| customer_id | UUID FK → commercial_customers | |
| interaction_type | Enum `call/visit/whatsapp/email/meeting` | |
| interaction_date | DateTime(tz) | |
| subject | String(255) | Required |
| summary | Text nullable | |
| outcome | String(255) nullable | |
| next_step_hint | String(255) nullable | Displayed in UI |
| created_by_user_id | UUID FK → foundation_users | Set from TenantContext |

### FollowUp
A next-action task linked to a customer (optionally to a specific interaction).

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| customer_id | UUID FK → commercial_customers | |
| interaction_id | UUID FK nullable → commercial_customer_interactions | |
| assigned_user_id | UUID FK → foundation_users | Must belong to same org |
| due_date | DateTime(tz) | |
| priority | Enum `low/medium/high` | Default `medium` |
| status | Enum `pending/completed/cancelled` | Default `pending` |
| reason | String(255) | Required |
| notes | Text nullable | |
| completed_at | DateTime(tz) nullable | Set on completion |

---

## Implemented routes (Sprint 1)

All routes require a valid Bearer token. All results are scoped to the caller's `organization_id`.

See [docs/api/sprint-1.md](../api/sprint-1.md) for the full endpoint list.

---

## Planned — Sprint 2 and beyond

| Domain object | Sprint |
|---------------|--------|
| `commercial_samples` | Sprint 2 |
| `commercial_sample_evaluations` | Sprint 2 |
| `commercial_quotes` | Sprint 2 |
| `commercial_orders` | Sprint 3 |

---

## Notes and limitations (Sprint 1)

- **No edit customer UI.** The `PATCH /customers/{id}` API exists but there is no frontend form for it. Per ADR-003 MVP scope freeze.
- `production` and `quality` modules exist as directory scaffolding only — no models, routes, or services implemented.
