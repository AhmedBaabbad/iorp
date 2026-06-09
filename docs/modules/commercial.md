# Commercial Module

**Status:** Sprint 2 — Slice 2 Complete (samples, evaluations, quotes, orders)

The commercial module owns the CRM-side of the business: customer records, logged interactions, follow-up tasks, physical sample tracking, quoting, and commercial order confirmation. It calls Foundation's application layer to validate user membership (ADR-004). All data is org-scoped via `TenantContext` (ADR-001).

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

## Sprint 2 domain objects

### Sample
A physical sample sent to a customer for trial/evaluation. Unique code per customer.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| customer_id | UUID FK → commercial_customers | |
| sample_code | String(64) | Unique per `(customer_id, sample_code)` |
| product_type | String(120) | |
| requested_spec_json | JSON nullable | Commercial-facing spec only |
| quantity_requested | Numeric(14,2) nullable | |
| unit | String(32) nullable | |
| request_date | DateTime(tz) | |
| status | Enum `requested/in_preparation/delivered/evaluated/cancelled` | Default `requested` |
| notes | Text nullable | |
| created_by_user_id | UUID FK → foundation_users | Set from TenantContext |

**Rules:**
- Status `evaluated` can only be set by creating a `SampleEvaluation` — the PATCH endpoint rejects it directly.
- A cancelled sample cannot receive new evaluations.

### SampleEvaluation
The commercial outcome of a sample trial. Creating one auto-transitions the sample to `evaluated`.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| sample_id | UUID FK → commercial_samples | |
| evaluation_date | DateTime(tz) | |
| result_status | Enum `accepted/rejected/needs_modification` | |
| comments | Text nullable | |
| next_action | Enum `proceed_to_quote/revise_sample/close_request/further_review` | |
| evaluated_by_user_id | UUID FK → foundation_users | Set from TenantContext |

### Quote
A formal quote document linked to a customer. Totals are auto-calculated (subtotal − discount + tax).

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → foundation_organizations | Tenant scope |
| customer_id | UUID FK → commercial_customers | |
| sample_id | UUID FK nullable → commercial_samples | Must belong to same customer |
| quote_number | String(64) | Unique per org |
| issue_date | DateTime(tz) | |
| valid_until | DateTime(tz) | |
| status | Enum `draft/issued/accepted/rejected/expired` | Default `draft` |
| currency | String(3) | ISO 4217, default `SAR` |
| subtotal_amount | Numeric(14,2) | Auto-calculated from items |
| discount_amount | Numeric(14,2) | Default `0` |
| tax_amount | Numeric(14,2) | Default `0` |
| total_amount | Numeric(14,2) | Auto-calculated |
| notes | Text nullable | |
| created_by_user_id | UUID FK → foundation_users | Set from TenantContext |

### QuoteItem
One line of a quote. `line_total` = `quantity × unit_price`.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| quote_id | UUID FK → commercial_quotes | Cascade delete |
| line_no | Integer | |
| product_type | String(120) | |
| requested_spec_json | JSON nullable | |
| quantity | Numeric(14,2) | |
| unit | String(32) | |
| unit_price | Numeric(14,2) | |
| line_total | Numeric(14,2) | Calculated on write |

### CommercialOrder
A customer order, optionally linked to a quote. Requires at least one item.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → foundation_organizations | Tenant scope |
| customer_id | UUID FK → commercial_customers | |
| quote_id | UUID FK nullable → commercial_quotes | Must be `issued` or `accepted` |
| order_number | String(64) | Unique per org |
| order_date | DateTime(tz) | |
| status | Enum `draft/confirmed/cancelled/converted_to_production` | Default `draft` |
| requested_delivery_date | DateTime(tz) nullable | |
| notes | Text nullable | |
| created_by_user_id | UUID FK → foundation_users | Set from TenantContext |

**Rules:**
- A linked quote must belong to the same customer as the order.
- Only quotes in `issued` or `accepted` status can be linked.

### CommercialOrderItem

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| commercial_order_id | UUID FK → commercial_orders | Cascade delete |
| line_no | Integer | |
| product_type | String(120) | |
| requested_spec_json | JSON nullable | |
| quantity | Numeric(14,2) | |
| unit | String(32) | |
| agreed_unit_price | Numeric(14,2) nullable | May not be agreed at creation |
| line_total | Numeric(14,2) nullable | Set when price is agreed |

---

## Implemented routes

All routes require a valid Bearer token. All results are scoped to the caller's `organization_id`.

- Sprint 1 routes: see [docs/api/sprint-1.md](../api/sprint-1.md)
- Sprint 2 routes: see [docs/api/sprint-2.md](../api/sprint-2.md)

---

## Notes and limitations

- **No edit customer UI.** The `PATCH /customers/{id}` API exists but there is no frontend form for it. Per ADR-003 MVP scope freeze.
- **No sample/quote/order frontend.** Backend APIs for Slice 2 are complete. Frontend pages deferred to Sprint 3 per ADR-003.
- `production` and `quality` modules exist as directory scaffolding only — no models, routes, or services implemented.
- RBAC is stored but not enforced. All authenticated users in the same org have the same access. Planned for Sprint 3.
