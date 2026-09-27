# Tenant Isolation Security Audit — IORP v0.1

Date: 2026-08-05  
Status: remediated and independently regression-tested

## Security contract

Tenant scope comes exclusively from the authenticated `TenantContext.organization_id`.
Tenant mutation schemas never use a caller-supplied organization identifier as scope.
For user-controlled resource identifiers, a nonexistent identifier and an identifier
owned by another tenant both return the same generic response:

```json
{"detail": "<Resource> not found."}
```

The status is `404`. Cross-tenant existence is never disclosed through a `403`, a
`CROSS_ORG_*` code, or a tenant-specific message. Authorization failures unrelated
to resource existence continue to use `403`.

## Repository inventory audited

- `foundation/infrastructure/repositories.py`
- `commercial/infrastructure/repositories.py`
- `workforce/infrastructure/repositories.py`
- `production/infrastructure/repositories.py`
- `quality/infrastructure/repositories.py`
- `platform/infrastructure/repositories.py` (identity-boundary review; not tenant-scoped)

Tenant-facing scoped lookups reviewed include User, Role, Permission, UserRole,
RolePermission, Customer, FollowUp, Interaction, Sample, SampleEvaluation, Quote,
CommercialOrder, WorkforceMember, WorkCenter, ShiftDefinition, ProductionOrder,
ProductionOrderItem, ShiftReport, ProductionOutput, DowntimeEvent, WasteRecord,
QualityCheck, QualityDefect, QualityRejection, NonConformanceReport, and
NonConformanceItem.

## Tenant route inventory audited

- Dashboard: `routes_dashboard.py`
- Foundation: `routes_auth.py`, `routes_users.py`, `routes_roles.py`,
  `routes_permissions.py`, `routes_organizations.py`
- Commercial: `routes_customers.py`, `routes_followups.py`,
  `routes_interactions.py`, `routes_samples.py`, `routes_sample_evaluations.py`,
  `routes_quotes.py`, `routes_orders.py`
- Workforce: `routes_workforce.py`
- Production: `routes_work_centers.py`, `routes_shift_definitions.py`,
  `routes_production_orders.py`, `routes_production_order_items.py`,
  `routes_shift_reports.py`, `routes_production_outputs.py`,
  `routes_downtime_events.py`, `routes_waste_records.py`
- Quality: `routes_quality_checks.py`, `routes_quality_defects.py`,
  `routes_quality_rejections.py`, `routes_non_conformance_reports.py`,
  `routes_non_conformance_items.py`

Platform routes were reviewed separately. Their organization path parameters are
intentional because they are protected by platform identity and permissions.

## Findings and fixes

### HIGH — role assignment existence disclosure

Previously, assigning or removing a role owned by another organization returned
`403` with `CROSS_ORG_ROLE_*`, proving that the UUID existed. User and Role are now
loaded through organization-scoped SQL queries. Wrong-tenant and nonexistent IDs
both return the same `404` body.

### HIGH — load-then-check tenant lookups

Foundation user/role/permission access and commercial eligibility checks previously
used global `db.get()` followed by an organization comparison. Scoped repository
methods now place both entity ID and `organization_id` in SQL `WHERE` clauses.

### MEDIUM — child entity queries trusted a validated parent

ProductionOrderItem and NonConformanceItem child queries previously depended only
on a parent UUID validated earlier by the service. Their queries now join the parent
and include its `organization_id`, providing defense in depth at query level.

### MEDIUM — tenant organization ID in legacy logo path

The hidden compatibility route `/organizations/{organization_id}/logo` was removed.
The supported tenant route is `/organization/logo` and derives scope solely from
the authenticated tenant. Platform logo routes retain organization path parameters.

### MEDIUM — incomplete UUID and override coverage

The isolation suite now includes invalid UUID, literal null UUID, query override,
body override, legacy path removal, exact wrong-tenant/nonexistent response parity,
and cross-tenant role assignment/removal cases. Parameterization brings the combined
tenant/platform isolation matrix above 65 real HTTP cases.

### Existing bulk-operation fix

Customer and follow-up reassignment validate both source and replacement users with
organization-scoped lookups. Their UPDATE statements also contain organization scope.

## Cross-entity validation

- Customer → Sales Owner: active same-tenant eligible User query.
- FollowUp → Assignee: active same-tenant eligible User query.
- FollowUp → Interaction: tenant-scoped customer/interaction query.
- WorkforceMember → User: tenant-scoped User query.
- UserRole → User and Role: both joined/scoped before assignment or removal.
- RolePermission → Role and Permission: both joined/scoped.
- Quality → Production references: raw SQL includes production table organization ID.
- ProductionOrderItem → ProductionOrder: joined organization filter.
- NonConformanceItem → NonConformanceReport: joined organization filter.

## Selection and identity isolation

User, role, permission, workforce, eligible-sales-owner, and eligible-assignee lists
are tenant-scoped. Eligible identity queries require active tenant Users. Platform
accounts use separate tables and tokens and cannot appear in tenant selectors.

## Mutation schema policy

Foundation and Workforce use `extra="forbid"` where their established API contract
supports rejection. Other established schemas retain Pydantic's safe extra-field
ignore behavior to avoid a breaking business-contract change. In both cases an
`organization_id` supplied by a client is never used for scope; tests accept only
`422` rejection or creation inside the authenticated organization.

## Verification

Commands:

```powershell
python -c "import app.main"
python -m pytest tests/test_tenant_isolation.py tests/test_platform_isolation.py tests/test_module_boundaries.py -q
python -m pytest tests/production/test_production_order_items.py tests/quality/test_non_conformance_items.py tests/test_role_assignment_safety.py tests/test_role_governance.py -q
python -m pytest tests/production/test_sprint3_baseline.py tests/quality/test_sprint4_baseline.py tests/commercial/test_customers.py tests/commercial/test_customer_sales_owner.py tests/commercial/test_follow_ups.py -q
python -m pytest -q
```

Recorded result after remediation:

- Import: passed.
- Isolation/platform/boundary suite: `81 passed`.
- Expanded tenant-isolation module: `67 passed in 85.56s`.
- Focused production-item, NCR-item, role-assignment, and role-governance regression suite: `85 passed in 165.14s`.
- Representative sprint modules: `58 passed, 7 failed in 65.42s`. The failures are
  pre-existing contract drift outside this security patch: six legacy customer tests
  authenticate users without the now-required RBAC permissions, and one Sprint 3
  baseline assertion expects a caller-supplied work-center code although the current
  API generates that code. None exercises a lookup changed by this patch.
- Full suite: `799 collected`; `727 passed`, `38 failed`, `33 errors`, `1 xfailed`
  in `882.82s` (`14:42`). Most failures/errors are the same legacy commercial
  fixture drift (the shared `auth_headers` user has no RBAC grants and receives
  `403`); the run also includes unrelated stale behavioral assertions. The complete
  suite therefore does not meet the release gate, and this report makes no full-pass
  claim.

## Residual risk

No known tenant-facing unscoped lookup or cross-tenant existence leak remains in the
audited paths. The repository is not release-ready until the unrelated legacy-test
contract drift above and any complete-suite failures are reconciled. New modules must
preserve the query-level scoping and generic-404 contract, and add non-vacuous
two-organization HTTP tests before release.
