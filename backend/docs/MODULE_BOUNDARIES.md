# Module Boundaries — IORP v0.1

## Architecture Decision

This project follows ADR-002 (Modular Monolith) and ADR-004 (Domain Ownership). Each module is physically separated and independently testable. Platform-wide identities and bootstrap state belong to `platform`; organization-scoped identities and authorization belong to `foundation`.

## Module Map

| Module | Scope | Table Prefix | Auth Dependency |
|---|---|---|---|
| `platform/` | Platform-wide | `system_` | `get_current_platform_account` |
| `foundation/` | Per-organization | `foundation_` | `get_current_user` |
| `commercial/` | Per-organization | `commercial_` | `get_current_user` |
| `production/` | Per-organization | `production_` | `get_current_user` |
| `quality/` | Per-organization | `quality_` | `get_current_user` |
| `workforce/` | Per-organization | `workforce_` | `get_current_user` |
| `masterdata/` | Per-organization (products, specification templates, VAT and currency) | `masterdata_` | `get_current_user` |
| `core/` | Shared infrastructure and contracts | — | — |

## Dependency Rules

```text
platform ───────► core ◄─────── foundation
                                  ▲
commercial ─────► core ───────────┤
production ─────► core ───────────┤
quality ────────► core ───────────┤
workforce ──────► core ───────────┘

composition root (main.py/dependencies.py) ─► platform + foundation + operational modules
```

- `platform` and `foundation` never import one another.
- Operational modules never import `platform`.
- Cross-module calls target a protocol in `core/interfaces`.
- Master data (ADR-005) is reached only through `core/interfaces/product_catalog.py`; legacy product types are rewritten by
  each module's holder registered in `core/interfaces/product_types.py`. Foundation reads only its permission codes.
- Sales orders reach production only through `core/interfaces/sales_order_source.py` (SALES-001): commercial answers with
  read-only snapshots of its confirmed orders; production answers how much of each line its demands took, and names the
  permission to send an order to production. Neither imports the other; both are registered at the composition root.
- `dependencies.py` is the composition root that binds a protocol to its owning implementation.
- Platform and tenant permission namespaces and authentication dependencies are distinct.

## Communication Between Modules

`core/interfaces` contains immutable data-transfer records and `Protocol` contracts only. The module that owns the data implements the contract. For example, `FoundationOrganizationQueries` implements `OrganizationProvisioningInterface`; platform services receive that interface through dependency injection and never import Foundation models or repositories.

## Authorization Policy

- Authorization decisions beyond simple permissions use `AuthorizationPolicy`, defined in `core/interfaces/`.
- v0.1 provides `DefaultOrganizationPolicy`, an organization-wide pass-through with no active route or service wiring.
- Future scope-aware policies are selected by `get_authorization_policy()` in the composition root.
- Do not hard-code ownership authorization in repositories. When row-level access is implemented, apply a policy to an already tenant-scoped query.
- See [AUTHORIZATION_EVOLUTION.md](AUTHORIZATION_EVOLUTION.md) for the audit and evolution plan.

## Known Cross-Module Database References

| Source Table | Column | Target Table | Reason | Migration Plan |
|---|---|---|---|---|
| `system_bootstrap_state` | `first_organization_id` | `foundation_organizations` | Records which organization was created during bootstrap | Convert to a plain UUID when `platform/` is extracted as a separate service |

This foreign key is an accepted and documented database coupling. It preserves referential integrity in the modular monolith and must not be copied as a general cross-module integration pattern.

## Adding a New Module

1. Create `domain`, `application`, `infrastructure`, and `api` packages.
2. Give every owned table the module prefix and organization scope where applicable.
3. Define required cross-module contracts in `core/interfaces` before writing consumers.
4. Implement each contract in the module that owns the data.
5. Bind implementations only in the composition root.
6. Use tenant authentication unless the module is explicitly platform-wide.
7. Extend `test_module_boundaries.py` and run the complete suite.

## Enforcement

`tests/test_module_boundaries.py` parses Python imports with `ast`, audits SQLAlchemy table names, checks route authentication separation, verifies interface protocols, imports modules independently, and exercises the bootstrap status endpoint. These tests run with the normal backend test suite and prevent boundary regressions.
