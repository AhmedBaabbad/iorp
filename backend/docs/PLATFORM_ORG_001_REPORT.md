# PLATFORM-ORG-001 Implementation Report

## Diagnosis

| Question | Finding |
|---|---|
| Unified function | Bootstrap and Platform already called the same `FoundationOrganizationQueries.create_organization` implementation through `OrganizationProvisioningInterface`. |
| Transaction | The provider flushes all records; Bootstrap/Platform wrappers own commit/rollback. This preserves one database transaction. |
| Created records | Organization, global permission catalog, five existing default roles, Root user, all admin-role permissions, and Root role assignment. |
| Logo behavior | Logo was validated/saved after the first DB flush and cleaned only for failures inside the provider; an outer commit failure could leave a file. |
| Validation gaps | Root password allowed 8 characters and root email was not checked globally against all tenant/platform identities. |
| API/UI gaps | Create response and detail were minimal; the list lacked industry/timezone/logo representation and no detail view existed. |

## Provisioning flow

The shared Foundation provider remains the single implementation for both entry points. It now performs code/email/logo validation before the first write, creates the complete graph without committing, and returns the saved logo path to its transaction-owning wrapper. Both Bootstrap and Platform wrappers roll back on any failure and delete a saved logo if a later operation or commit fails.

The project uses cleanup approach B because organization, Root, roles, assignments, permissions, and bootstrap state must remain one database transaction. Logo magic bytes accept PNG, JPEG, and WebP, with a 2 MB limit.

## Permission catalog and roles

The actual shared catalog in `app/core/permission_catalog.py` includes Foundation, Commercial, Production, Quality, and Workforce permissions. Permission creation is idempotent by unique code. Existing project behavior creates these roles for every organization:

- `organization_admin`: all catalog permissions.
- `commercial_manager`: all Commercial permissions.
- `production_manager`: all Production permissions.
- `quality_manager`: all Quality permissions.
- `viewer`: permissions ending in `:read`.

The Organization Root receives `organization_admin` explicitly and retains the inherent Root bypass.

## API

- `POST /api/v1/platform/organizations` returns the full organization, Root identity, and roles-created data without password material.
- Duplicate code and email return stable 409 codes.
- Invalid logo returns a stable 400 code.
- List summaries include logo presence, root email, industry, timezone, counts, and timestamps.
- Detail includes Root status/last login and all roles with user counts.

## Frontend

The platform organization area supports uppercase code entry, locale selection, IANA timezone selection, 12-character Root password validation, logo type/size validation and preview, permission-gated creation, redirect to the created detail, enriched list data, and a detail page with Root password recovery and roles.

All new copy is stored in aligned Arabic and English `platform.json` files.

## Verification

- Backend focused regression run: `60 passed`; the final provisioning file including rollback cleanup then passed `6 passed`.
- Translation alignment/UTF-8: all 15 locale pairs passed.
- TypeScript: passed.
- Next.js production build: passed, including `/platform/organizations/[id]`.

The attached task text ends midway through section G, so no later test matrix or required-output section was available in the supplied file.
