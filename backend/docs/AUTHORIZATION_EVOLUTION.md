# Authorization Evolution — IORP

## Purpose and invariants

**Phase 1 (row-level read scoping) is COMPLETE as of ORG-RBAC-004.** This
document originally prepared IORP for row-level authorization without
activating it (ORG-RBAC-004-PREP); it now also records what was actually
built when that preparation was activated.

Row-level authorization is additive: it narrows an already tenant-scoped
query, but never replaces tenant filtering or the existing permission check.
Scope applies to READ operations only (list + get); create/update/delete
remain permission-based, unscoped, exactly as before.

## Current state (v0.2)

### Permission model

- A user has a permission or does not (binary, unchanged), **and**, for
  permissions where ownership is meaningful, the specific role-permission
  grant additionally carries a **scope**: `own`, `team`, or `organization`.
- Scope lives on the junction row (`foundation_role_permissions.scope`), not
  on the permission definition -- the same permission can be granted at
  different scopes by different roles (e.g. `sales_rep` gets
  `commercial:customers:read` at `own`; `commercial_manager` gets the same
  permission at `organization`).
- Default scope is `organization` for every existing and new grant unless
  explicitly overridden -- v0.1 behavior is preserved everywhere it wasn't
  deliberately narrowed.
- A user holding the same permission through multiple roles at different
  scopes gets the **broadest** one (`organization` > `team` > `own`).
- `team` is a recognized enum value with **no implementation**: it fails
  open to `organization` and logs a warning (`ScopedAuthorizationPolicy`).
- Organization Root bypasses scope entirely (checked before any scope logic
  runs), exactly as it already bypassed nothing being scoped in v0.1.
- Code pattern: `module:resource:action`.
- Enforcement: `require_permission()` (existence) + `ScopedAuthorizationPolicy`
  (row-level narrowing, read-only) in `app/dependencies.py`.

| Permission | Owner field | Scopable | Current default |
|---|---|---|---|
| `commercial:customers:read` | `sales_owner_user_id` | Yes | `organization` (except `sales_rep`: `own`) |
| `commercial:follow_ups:read` | `assigned_user_id` | Yes | `organization` (except `sales_rep`: `own`) |
| `commercial:interactions:read` | `created_by_user_id` | Yes | `organization` (except `sales_rep`: `own`) |
| `workforce:members:read` | — | No | `organization` (no owner field; always org-wide) |
| `foundation:users:read`, `roles:read`, etc. | — | No | `organization` (administration resources; always org-wide) |
| Production/Quality `*:read` | creator fields exist (`created_by_user_id`, `checked_by_user_id`, etc.) | **Not yet** | `organization` -- see "Deferred" below |

Special cases:

- Organization Root bypasses tenant RBAC and row-level scope, and retains full tenant access.
- Platform Root belongs to a separate identity and authorization system, untouched by this work.
- Follow-up `scope=mine` (a query parameter) is a separate UI convenience filter, not this
  authorization scope -- it composes additively with the RBAC scope (both apply as AND-ed
  `WHERE` predicates), so a `scope=own`-permissioned user cannot see more by passing `scope=all`.

### Deferred: Production and Quality read scoping

Production (`created_by_user_id` on `ProductionOrder`, `ShiftReport`,
`ProductionOutput`, `DowntimeEvent`, `WasteRecord`) and Quality
(`checked_by_user_id`/`detected_by_user_id`/`rejected_by_user_id` on
`QualityCheck`/`QualityDefect`/`QualityRejection`) both have creator-style
columns, but this task deliberately did **not** mark their read permissions
`scopable=True` or wire query filtering for them. Reasoning: unlike
`sales_owner_user_id` (an explicit, reassignable "who owns this" field) and
`assigned_user_id`, production/quality creator fields are "who logged this"
audit provenance, not an ownership assignment -- and this task's own
constraints frame production/quality scoping as conditional ("if owner
fields exist, apply same pattern") rather than a required deliverable, unlike
the fully-specified commercial (customers/follow-ups) scope. Marking a
permission `scopable=True` without wiring the filter would be actively
misleading (a role editor could silently promise filtering that never
happens). This is recorded here as the next Phase-1-adjacent follow-up, not
as Phase 2/3 work.

## Extensibility audit

### Repository readiness

All listed methods execute SQLAlchemy statements internally and return materialized
results, not composable queries. A future policy therefore must be called inside
the repository after tenant and request filters are assembled and before database
execution.

| Repository | Method | Extra filters today | Returns | Readiness and future change |
|---|---|---|---|---|
| `CustomerRepository` | `list_by_organization()` | No | `list[Customer]` | Medium: apply policy to `select(Customer)` before `db.scalars`; owner is `sales_owner_user_id`. |
| `FollowUpRepository` | `list_filtered()` | `FollowUpListFilters` | `(items, total)` | High: `_base_org_statement()` and `_apply_filters()` already expose one pre-execution statement; apply ownership before both count and page queries. |
| `FollowUpRepository` | `list_by_customer()` | Customer only | `list[FollowUp]` | Medium: add the same policy filter before execution to avoid bypass through the nested endpoint. |
| `WorkforceRepository` | `list_workforce_members()` | Dictionary of domain/paging filters | `list[WorkforceMember]` | Structurally easy but not scope-able: no ownership field, so remain organization-wide. |
| `UserRepository` | `list_by_organization()` | No | `list[User]` | Structurally easy but users are an organization-wide administration resource; self-service must use separate endpoints, not OWN filtering. |
| `ProductionOrderRepository` | `list_by_organization()` | Status, work center, priority | `list[ProductionOrder]` | Medium: `created_by_user_id` exists, but product semantics must decide whether creator means owner before applying a policy. |
| `QualityCheckRepository` | `list_by_organization()` | Type, status, result, order, shift, date | `list[QualityCheck]` | Medium: `checked_by_user_id` is a plausible responsible user; confirm whether inspection responsibility equals authorization ownership. |

### Service decision points

| Service | Method | Current access decision | Future injection location |
|---|---|---|---|
| `CustomerService` | `list_customers()` | Route permission plus repository organization filter | Pass context/policy to repository; query-filter on `sales_owner_user_id`. |
| `FollowUpService` | `list_follow_ups()` / `list_follow_ups_for_customer()` | Route permission, organization join, optional request filter | Query-filter in both repository paths on `assigned_user_id`; never post-filter paged results. |
| `FoundationService` | `list_users_for_tenant()` | Route permission plus repository organization filter | Keep organization-wide; a future self profile policy belongs to its dedicated record flow. |
| `WorkforceService` | `list_workforce_members()` | Route permission plus repository organization filter | Keep organization-wide unless a real ownership concept is introduced. |
| `ProductionOrderService` | `list_production_orders()` | Route permission plus organization filter | Query-filter before execution after ownership semantics are approved. |
| `QualityCheckService` | `list_quality_checks()` | Route permission plus organization filter | Query-filter before execution after ownership semantics are approved. |

The correct pattern is query-filtering. Pre-filtering with a trusted context can
prepare policy inputs, but the resulting predicate must be added to SQL. Loading
all rows and post-filtering would leak counts, break pagination, and waste memory.

### Ownership inventory

| Entity | Candidate owner field | Meaning | Scope-able now? |
|---|---|---|---|
| Customer | `sales_owner_user_id` | User responsible for the customer | Yes |
| FollowUp | `assigned_user_id` | User responsible for the follow-up | Yes |
| CustomerInteraction | `created_by_user_id` | User who recorded the interaction | Yes, if creator-based visibility is desired |
| WorkforceMember | None | Organization-managed employee record | No; organization-wide |
| User | Self (`id`) | Login identity, not a business-record owner | No; organization-wide administration |
| Role | None | Organization-wide authorization definition | No; organization-wide |
| ProductionOrder | `created_by_user_id` | Creator, not yet a formally defined owner | Pending domain decision |
| QualityCheck | `checked_by_user_id` | Inspector who performed the check | Pending domain decision |

### Barriers

| Area | Barrier | Severity | Required future change |
|---|---|---|---|
| Materialized repository APIs | List methods return results, so callers cannot compose predicates | Medium | Apply the policy inside repositories or expose a private statement builder. |
| Customer and user lists | Hard-coded organization queries lack a filter object/statement builder | Easy | Build the statement, call policy, then execute. |
| Follow-up pagination | Total and item queries must share an identical authorization predicate | Easy | Apply policy to `base` before deriving count and paged statements. |
| Nested list endpoints | Customer-specific follow-ups/interactions can become alternate access paths | Medium | Apply record policy consistently to every list and single-record path. |
| Counts and dashboards | Aggregates in repositories and `dashboard/api/routes_dashboard.py` assume organization-wide data | Hard | Centralize scoped base statements and derive counts/aggregates from them. |
| Reports/exports | Future bulk outputs can bypass ordinary list filters | Hard | Require the same policy context and query-filter pipeline for every export. |
| Production ownership | Creator exists but business ownership is undefined | Medium | Record a domain decision before mapping `created_by_user_id` to OWN. |
| Quality ownership | Inspector exists but responsibility/manager visibility is undefined | Medium | Define inspection ownership and supervisor/team semantics first. |
| Team scope | No authoritative team hierarchy or membership model exists | Hard | Introduce manager hierarchy, explicit teams, or departments before enabling TEAM. |
| Single-record reads | `get_by_id()` methods only enforce tenant scope | Medium | Call `can_access_record()` after tenant-scoped lookup, or add owner predicate to SQL. |

## Architecture available in v0.2

```text
app/core/interfaces/authorization_policy.py
  ├─ AuthorizationPolicy Protocol
  ├─ AuthorizationContext (now carries is_organization_root, populated from TenantContext)
  └─ AccessScope

app/core/authorization/scoped_policy.py
  └─ ScopedAuthorizationPolicy  -- ACTIVE. own/team/organization row filtering.
     (default_policy.py / DefaultOrganizationPolicy retained, unused, for reference.)

app/core/authorization/scope_resolver.py
  └─ resolve_effective_scope()  -- broadest-scope-wins resolution across a user's roles.

app/dependencies.py
  ├─ get_authorization_policy() -> ScopedAuthorizationPolicy (wired)
  └─ build_auth_context(db, tenant, permission_code) -> AuthorizationContext (route helper)

app/foundation/domain/permission_catalog.py
  ├─ PermissionDefinition.scopable / .owner_field
  └─ SCOPABLE_PERMISSIONS: dict[code, owner_field]

app/foundation/domain/system_roles.py
  └─ SYSTEM_ROLE_SCOPE_OVERRIDES / scope_for()  -- only sales_rep is narrowed from
     the organization-wide default, for customers/follow_ups/interactions:read.
```

`ScopedAuthorizationPolicy.apply_query_filter()` resolves the query's primary
mapped entity via `query.column_descriptions[0]["entity"]` and applies
`getattr(entity, owner_field) == context.user_id` -- this only works for
queries that `select(Model)` directly (as every wired repository method does);
aggregate queries (`select(func.count(...))`) must be restructured as
`select(Model)...` wrapped in `select(func.count()).select_from(stmt.subquery())`
before filtering (see `routes_dashboard.py`'s `customers_count`).

Wired read paths: `CustomerRepository.{list_by_organization,get_by_id}`,
`FollowUpRepository.{list_filtered,get_by_id}`,
`CustomerInteractionRepository.{list_for_customer,get_for_customer}`, and the
dashboard's `customers_count`. Corresponding routes in `routes_customers.py`,
`routes_followups.py`, `routes_interactions.py`, `routes_dashboard.py`.

The example in `core/authorization/examples/own_records_policy.py` is what
`ScopedAuthorizationPolicy` was actually modeled on (same
`column_descriptions`-based entity resolution) -- it remains documentation-only
and is not imported by the real policy.

## Evolution roadmap

### Phase 1 — permission scopes (v0.2) -- COMPLETE

Introduced `own`, `team`, and `organization` on the `foundation_role_permissions`
junction row (not the permission definition), for commercial customers,
follow-ups, and interactions reads. `team` exists as a value with no filtering
implementation (fails open to `organization`, logs a warning). Production and
Quality read scoping was deliberately deferred (see "Deferred" above) rather
than half-wired.

### Phase 2 — team definition (v0.3)

Define team semantics first: manager/report hierarchy, explicit membership, or
department membership. TEAM must not be activated until exactly one authoritative
definition and its cross-organization safeguards exist.

### Phase 3 — dynamic policies (v1.0)

Allow organization-configurable policies such as sales ownership and manager
visibility. Validate and store policy configuration; never evaluate arbitrary
client expressions or replace tenant predicates.

## Wiring checklist for a future scoped release

1. Create a policy implementing `AuthorizationPolicy`.
2. Resolve an effective scope from trusted server-side grants.
3. Change `get_authorization_policy()` to provide that policy.
4. Inject policy/context through routes and services.
5. In every applicable repository, build the tenant-scoped statement first,
   apply the policy with a statically selected owner field, then execute it.
6. Derive pages, totals, dashboards, reports, and exports from the same statement.
7. For single records, enforce the policy without revealing cross-tenant existence.
8. Keep Organization Root bypass, Platform isolation, permission checks, and
   role-assignment protections as independent controls.

## What will NOT break

- Existing binary permission checks remain mandatory and are not replaced by a policy.
- Tenant isolation by `organization_id` remains the first predicate on every tenant query.
- Organization Root retains organization-wide access through an explicit policy bypass.
- Platform identities remain isolated from tenant RBAC and row-level policies.
- Cross-organization reference validation and role-assignment safety remain independent controls.
- The v0.1 default policy continues returning queries unchanged until scoped authorization is deliberately wired.

## What will need changes

- Permission grants need a trusted representation of effective scope.
- Applicable repository list/count methods need one shared, policy-filtered base statement.
- Single-record services need policy enforcement after tenant-safe lookup or inside the SQL predicate.
- Route and service composition needs to pass `AuthorizationContext` and the selected policy.
- Dashboards, reports, exports, totals, and pagination must derive from the same filtered query.
- The role-permission administration UI will need a scope selector and localized scope labels.
- TEAM scope requires an authoritative hierarchy or membership model before activation.
- Automated tests must cover owned, team, organization, root-bypass, and cross-tenant cases.

## Decision log

| Decision | Rationale | Date |
|---|---|---|
| Binary organization-wide permissions in v0.1 | Sufficient for initial launch and matches existing behavior | Sprint 4 |
| Policy contract in `core/interfaces` | Gives modules a shared abstraction without cross-module imports | Sprint 4 |
| No database or endpoint wiring in this preparation | Prevents behavior, performance, and API changes | Sprint 4 |
| Query filtering is the future enforcement mechanism | Preserves pagination, totals, and database efficiency | Sprint 4 |
| Default policy is pass-through | Reproduces current organization-wide behavior exactly | Sprint 4 |
| Scope wired for commercial customers/follow-ups/interactions only; production/quality deferred | Owner semantics for creator-style production/quality columns are undefined; marking them scopable without wiring filtering would mislead the role editor | ORG-RBAC-004 |
| `sales_rep` is the only system role narrowed to `own`; every other existing grant stays `organization` | Satisfies "adding scope must not break existing behavior" literally -- only the intended new behavior changes | ORG-RBAC-004 |
| Superseded: writes were permission-based only in ORG-RBAC-004 | The October 2026 full authorization review explicitly requested restricting exposed operations. Customer/follow-up mutations now also respect the record's read-scope ceiling; inaccessible records return 404. Ordinary action permission is still required. | Authorization audit 2026-10-07 |
| Missing grants default to own; team is restricted to own until membership is implemented; unassigned records are not own | Fail closed instead of silently widening access to the entire organization. These rules apply only to resources declared scopable. | Authorization audit 2026-10-07 |
| Business decisions have dedicated permission gates | Quote/order/sample/follow-up decisions, demand transitions, roster closing and shipment preparation transitions no longer inherit generic update. Completing corrective actions requires its existing explicit permission. | Authorization audit 2026-10-07 |
| `is_organization_root` added to `TenantContext` (previously only on `CurrentUserContext.user`) | `AuthorizationContext` requires it and routes only depended on the lighter `TenantContext`; avoided adding a second dependency to every scoped route | ORG-RBAC-004 |
