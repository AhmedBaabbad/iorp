# Authorization review — 2026-10-07

## Scope and evidence

Reviewed the actual FastAPI dependency tree, permission catalogs, system-role templates, lifecycle handlers/services, scoped access policy, role governance, reporting dispatch and corresponding frontend controls.

Initial review inventory: **398 API routes, 222 permission codes, 14 system-role templates**. The workspace continued to evolve during dashboard development; the latest exported snapshot contains **407 routes, 227 codes and 11 role templates**. Test counts below describe their corresponding runs, not an assertion that every later workspace change received the same manual review. Reproducible inventory and role matrix:

- `backend/artifacts/export_authorization_inventory.py`
- `backend/artifacts/authorization-route-inventory.json`
- `backend/artifacts/authorization-role-matrix.json`

The route inventory includes Commercial, Production, Quality, Shipping, Procurement, Workforce, Master Data, Foundation/organization administration, reporting, authentication and Platform. A catalog declaration alone is not treated as enforcement: tests send real HTTP requests with authenticated users lacking permissions and require 403.

## Findings fixed

| Severity | Finding | Correction |
|---|---|---|
| High | Unsupported team scope expanded to organization scope; own access accepted ownerless records. | Team falls back to own; ownerless records are denied; queries without ownership metadata return no rows. Missing grant metadata defaults to own. |
| High | Customer/follow-up writes could mutate records outside the user's read scope. | Tenant-scoped record lookup followed by the read-scope ceiling; inaccessible records return 404. Ordinary mutation permissions remain mandatory. |
| High | Generic update permission authorized quote and sales-order decisions. | Dedicated quote issue/accept/reject/expire/revise and order confirm/cancel/revise permissions. Allowed actions filtered on creation and retrieval responses. |
| High | Sample PATCH could perform lifecycle/decision changes using only update. | Checks each changed status/decision; creation in a noninitial state also requires the corresponding permission. UI filters choices and disables unauthorized decisions. |
| High | Demand release/cancellation shared generic update. | Dedicated release/cancel checks, both on the endpoint and for the requested target; UI buttons use the same codes. |
| Medium | Follow-up cancellation/reopening shared update. | Explicit cancel/reopen permissions and matching controls. |
| Medium | Certificate issuance allowed changing global quality settings. | Independent `quality:settings:update` permission. |
| High | Completing an NCR corrective action accepted report update as an alternative to the explicit complete permission. | Removed the alternative in endpoint, service action presentation and frontend. Cancelling an action now requires NCR cancellation permission. |
| Medium | Closing a roster and preparing/reopening/rescheduling shipments shared update. | `production:shift_rosters:close` and `shipping:shipments:ready/reopen/reschedule`, including backend action maps and UI. |

## Enforcement retained and verified

| Area | Enforcement |
|---|---|
| Production | Order release/start/hold/complete/close/cancel; run start/pause/complete/cancel; planning allocation/release; member management; result create/update/delete/correct; waste and downtime mutation/close. |
| Quality | Inspection start/measure/close/cancel; rejection decide/execute; specification activation; certificate issue/revoke; NCR verification and cancellation. |
| Procurement | Supplier approval/status decisions; goods receipt receive/cancel; purchase-order action gates; settings maintenance. |
| Shipping | Dispatch/delivery/cancel, return approve/receive/cancel, plus newly separated preparation actions. |
| Workforce and Master Data | Resource-specific read/create/update/delete where supported; separate product/settings/list maintenance. |
| Administration | Role/permission assignment restrictions, root protection, organization isolation, separate platform identities/policies. |
| Reporting | Registered report definition permission checked on preview and PDF requests; report lookup gates; dashboard metrics filtered by their source permissions. |

Authentication, password recovery, self-profile, bootstrap and health are intentional special boundaries, explicitly allowlisted in the route coverage test. Platform permissions use a separate policy and now expose metadata for the inventory. They are not mistaken for unguarded business endpoints.

Some permissions intentionally cover a coherent group of work: NCR update covers containment/root-cause preparation/submission and editing its draft items; NCR verification judges effectiveness and closes the report; cancellation also covers cancelling its corrective actions. Supplier approval covers the supplier approval outcome. These are explicit backend guards, not public actions. Ordinary status transitions remain subject to domain state-machine rules after authorization.

## Migrations and roles

- `backend/alembic/versions/2026_11_04_0900_f6a1b2k6_action_permissions.py`: 18 new codes.
- `backend/alembic/versions/2026_11_04_1000_f6a1b2k7_execution_permissions.py`: 4 new codes.
- Both applied to the configured development PostgreSQL database, now at `f6a1b2k7`.
- Only appropriate system-role grants added: organization administrator; relevant commercial, production/factory, quality and shipping/warehouse managers. Existing custom roles receive **no automatic new decision rights**.
- Upgrade added 117 and 45 system-role grants respectively in this database. No business records were migrated/deleted.
- Downgrade removes only grants recorded as inserted by that migration. It retains permission catalog rows and later custom-role grants to avoid data loss.
- SQLite behavioral migration tests and PostgreSQL transactionally rolled-back upgrade/downgrade checks preserve the original grant IDs and reject grants to custom roles. PostgreSQL helper: `backend/artifacts/check_action_migration_postgres.py` (run before applying the selected revision).

## Important file groups

- Policy: `backend/app/core/authorization/{scoped_policy,scope_resolver}.py`; `backend/app/commercial/application/services.py`.
- Catalog: `backend/app/foundation/domain/{permission_catalog,system_roles}.py`; Commercial `domain/action_permissions.py`; Production/Quality/Shipping `domain/permissions.py`.
- Commercial: `api/routes_{quotes,orders,samples,followups}.py`; `application/quote_service.py`.
- Operations: Production `api/routes_{demands,execution}.py`; Quality `api/routes_{certificates,ncr}.py`, `application/ncr_service.py`; Shipping `api/routes_shipments.py`.
- Frontend: permission constants under `src/lib`; samples, followups, production-demands, production-execution, quality-certificates and ncr-reports feature controls.
- Regression coverage: `backend/tests/test_all_route_authorization.py`, `test_sensitive_action_permissions.py`, `test_permission_scopes.py`, production RBAC tests and targeted module suites; frontend permission parity and sample form tests.
- Architecture decision update: `backend/docs/AUTHORIZATION_EVOLUTION.md` supersedes the earlier writes-unscoped decision for customer/follow-up mutations.

## Boundaries and remaining limitations

- **NOT IMPLEMENTED:** actual team-membership authorization. Team scope is safely restricted to own records until such a model exists.
- Own/team scope is supported only for resources explicitly marked scopable in the current catalog. Other resources use organization isolation and action permissions; the dashboard does not introduce owner/team semantics of its own.
- This review does not claim exhaustive verification of every possible role combination, every tenant-data path or all browser journeys. Route denial tests do not replace tenant isolation and state-machine tests; those were also run for the relevant suites.
- No custom role was automatically assigned the new rights. Administrators must explicitly select the needed rights in their role configuration.
- Tests skipped by existing opt-in conditions are reported separately and are not counted as passing.

## Test evidence

- Combined route/catalog/scope/architecture/production RBAC run: **464 passed, 4 skipped** (244.26s).
- Final route denial, dedicated action and production RBAC rerun: **385 passed, 4 skipped** (81.87s); `authorization-route-tests.log`.
- Quality, shipping, procurement, workforce, role governance, platform isolation/identity and sales-order lifecycle: **238 passed, 8 skipped** (430.03s); `authorization-modules-tests.log`.
- Final Commercial and tenant isolation: **254 passed, 3 skipped** (510.62s); `authorization-commercial-tests.log`.
- Follow-ups, shipments, NCR/CAPA and sensitive actions after the operational changes: **80 passed, 2 skipped** (91.10s); `authorization-actions-tests.log`.
- Previously opt-in PostgreSQL production RBAC migration tests explicitly enabled: **4 passed, 12 deselected** (58.35s); `authorization-postgres-tests.log`.
- k6/k7 PostgreSQL upgrade/downgrade transactional checks passed; original grant IDs preserved. Post-upgrade comparison found **zero missing new grants** against actual system-role templates.
- Frontend: **24 component tests passed** (samples, certificates, demand visibility, NCR); **8 permission parity tests passed**. TypeScript passed. Targeted ESLint passed after removing two unused imports.

The groups overlap: these numbers must not be added as a count of distinct tests. Remaining skips are optional PDF review artifact generation (requires `REPORT_SAMPLES_DIR`); the production PostgreSQL skips in the general run were subsequently executed explicitly. No failing tests remain in these runs.
