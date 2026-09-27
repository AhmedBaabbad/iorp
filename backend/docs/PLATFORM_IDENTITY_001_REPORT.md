# PLATFORM-IDENTITY-001 Report

## Diagnosis

| Question | Initial state | Implemented state |
|---|---|---|
| Platform role | `is_root` boolean only | Formal `root`/`admin` role with compatibility flag |
| Permission catalog | None | Isolated `platform:*` catalog and role mapping |
| Route authorization | Authentication only | Granular permission dependencies on platform routes |
| Account management | None | List, read, create, update, deactivate, and password reset APIs |
| Last Root protection | None | Deactivation and demotion protection plus bootstrap-root delete protection |

The compatibility `is_root` database column is retained and synchronized to avoid data loss and preserve existing deployments. Authorization treats an existing `is_root=true` account as Root while the migration backfills its formal role.

## Isolation and identity

- Platform accounts remain exclusively in `system_platform_accounts` and have no `organization_id`.
- Platform permission values all start with `platform:` and never use tenant permissions.
- Cross-table tenant email lookup is provided through `UserCredentialInterface`; Platform does not import Foundation.
- JWTs now carry the platform role and independent token version.
- Root has inherent access to the complete catalog; Admin receives only the documented limited role mapping.

## Migration

Run:

```console
cd backend
alembic upgrade head
```

Migration `f6a1b2e2` creates the enum/role column and backfills existing Root and Admin accounts from `is_root`.

## Frontend

Platform Root can open `/platform/administrators` from the dashboard to create accounts, change roles, reset passwords, and deactivate accounts. The original bootstrap Root is marked as protected. All new visible copy is sourced from aligned Arabic and English `platform.json` files.

## Verification

- Platform identity plus existing isolation/bootstrap/recovery suites: `32 passed`.
- Arabic/English JSON parity and UTF-8: all 15 locale pairs passed.
- TypeScript check: passed.
- Next.js production build: passed, including `/platform/administrators`.

Existing repository-wide lint warnings and npm audit notices are outside this task and did not fail the build.
