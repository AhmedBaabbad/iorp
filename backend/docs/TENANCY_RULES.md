# Tenancy Rules — IORP v0.1

## Multi-Tenancy Architecture

IORP uses a shared database and shared schema. Tenant isolation is enforced by `organization_id`, obtained only from the authenticated tenant JWT and exposed as `TenantContext.organization_id`. Client input never selects the active tenant.

## Rule Set A: Data Isolation

1. Every tenant query filters by `organization_id`, directly or through an owner join.
2. The active `organization_id` comes from the authentication dependency, never body, query, path, header, or cookie input.
3. Body fields named `organization_id` are ignored by schemas that allow unknown fields; create services still assign the authenticated organization. Schemas using `extra="forbid"` reject them.
4. Tenant-scoped uniqueness includes `organization_id`, for example `(organization_id, email)` and `(organization_id, employee_code)`.
5. Cross-entity references are resolved through organization-scoped repositories or checked with `validate_same_organization`.

```python
customer = customers.get_by_id(tenant.organization_id, customer_id)
validate_same_organization(user.organization_id, tenant.organization_id, "user")
```

## Rule Set B: Identity Isolation

1. Platform accounts and tenant users use separate tables and models.
2. Platform JWTs cannot pass `get_current_user`; tenant JWTs cannot pass `get_current_platform_account`.
3. Tenant enumerations query `foundation_users` only.
4. Operational assignments accept Foundation user IDs only and validate organization ownership.
5. Tenant identities cannot access platform administration.

## Rule Set C: Organization Boundary

1. Reads and mutations are scoped to the authenticated organization and cross-tenant IDs resolve as not found or are rejected.
2. Tenant update schemas do not permit changing a user's organization.
3. Role assignment validates both user and role against the same organization.
4. Workforce user linking validates the Foundation user against the member organization.
5. Customer sales owners must be eligible users in the customer organization.
6. Follow-up assignees must be eligible users in the owning customer's organization.

## Rule Set D: Authentication Boundary

1. New JWTs contain `account_type`: `platform` or `user`.
2. Tenant JWTs contain `organization_id`; platform JWTs do not.
3. Dependencies validate `account_type` before resolving identity; invalid types return 401.
4. Platform and tenant token versions are checked on every protected request. Password changes increment only the affected account's version, invalidating its previous sessions.
5. Users of inactive organizations are denied login and authenticated access.

## Enforcement

- Compile time/static: module import and schema boundary tests.
- Runtime: scoped repositories, identity-specific dependencies, and `validate_same_organization`.
- Test time: `test_tenant_isolation.py` and `test_platform_isolation.py`.

## Future: Row-Level Authorization

- Currently, a granted permission provides organization-wide record access.
- A future permission scope may narrow that access to owned or team records.
- `organization_id` isolation always remains the foundation; row-level filtering is additive and never replaces it.
- The v0.1 default policy is pass-through and is intentionally not wired into existing flows.
- See [AUTHORIZATION_EVOLUTION.md](AUTHORIZATION_EVOLUTION.md) for the architecture and audit.

## Developer Checklist: Adding a New Feature

- [ ] New model has `organization_id` directly or through a documented parent.
- [ ] New repository methods filter by `organization_id`.
- [ ] New service receives scope from authenticated context.
- [ ] New tenant route uses `get_current_user`/derived tenant dependency.
- [ ] New create/update schema does not accept `organization_id` as scope.
- [ ] Cross-entity references validate the same organization.
- [ ] Platform Root cannot appear in tenant selection queries.
- [ ] A cross-tenant test covers new reads and references.
- [ ] Platform and tenant permission namespaces are not mixed.
