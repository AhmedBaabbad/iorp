# ORG-ROOT-001 — Diagnosis and Implementation Report

## Diagnosis

| Area | Before ORG-ROOT-001 | Result |
|---|---|---|
| B01 / Q1 — User model | No `is_organization_root` column | Added a non-null, indexed boolean with application default `false` |
| B02 — User schemas | Create/update accepted identity, status, phone and role codes; no root field | Root flag remains absent from create/update and is exposed only in read responses |
| B03 / Q2 — User service | Follow-up-aware deactivation existed; no protected-user concept | Root deletion, deactivation and identity mutation are enforced in the service |
| B04 — User repository | Tenant list/get helpers; no root query | Added tenant-scoped remaining-root count |
| B05 / Q3 — Bootstrap | Provisioned the first organization admin without a root marker | Provisioned admin is now an Organization Root |
| B06 / Q4 — Provisioning | Organization, roles, permissions and admin were created in one transaction | Same atomic flow retained; admin is created with root flag before commit |
| B07 / Q5 — Password change | Only Platform Account had a change-password endpoint | Added normal tenant self-service endpoint; no recovery/session invalidation UI was added |
| B08 — Deactivation | Open follow-ups block deactivation | Existing guard retained after the stronger root guard |
| B09 — Permissions | Permissions came only from roles | Root receives all non-`platform:*` catalog permissions inherently |
| B10 — Authentication | Current user is loaded from DB on every request | Root status is read from DB; no mutable root claim is trusted from JWT |
| F01–F04 — User UI | No root distinction or protection-aware controls | Badge/notices/read-only identity and hidden deactivate action added |
| F05 — Password UI | No tenant password-change UI | Deferred to ORG-ROOT-002 as required; backend self-service flow is available |
| F06–F07 — i18n/permission UI | JSON namespaces and permission guards already existed | All new copy uses `administration.users`; automated ar/en parity and UTF-8 scan added |

## Enforcement

- `FoundationService` owns all root invariants, so route bypass does not bypass protection.
- `require_permission` and `require_any_permission` allow an Organization Root only for non-platform permissions.
- Root permissions returned by `/auth/me` and user detail are all catalog permissions except `platform:*`.
- Provisioning sets `is_organization_root=True` in the Foundation-owned transaction used by both bootstrap and Platform organization creation.
- The migration selects the earliest user per organization using `created_at, id`, giving every organization with users exactly one initial root.

## Frontend Translation Rule

All new visible Organization Root text is stored in both:

- `frontend/src/i18n/locales/ar/administration.json`
- `frontend/src/i18n/locales/en/administration.json`

`npm run i18n:check` parses every Arabic/English JSON pair, rejects mojibake markers, and requires identical leaf-key sets. Components use `t()` for the new content and do not contain Arabic or English copy for this feature.

## Follow-ups

1. Build the tenant password-change UI and recovery flow in ORG-ROOT-002.
2. Add tenant token-version/session invalidation in ORG-ROOT-002.
3. If direct database writes must be defended, add a PostgreSQL deferred constraint trigger ensuring every organization retains a root; application provisioning and service operations already enforce this invariant.

## Verification Results

- T01–T25: `25 passed`.
- Final focused regression (Organization Root, follow-up deactivation, bootstrap, platform provisioning, auth, admin, and module boundaries): `71 passed`, `2 warnings`.
- TypeScript: `npx tsc --noEmit` passed.
- Translation/UTF-8 rule: `i18n check passed: 15 Arabic/English JSON file pairs are valid and aligned.`
- Full-suite baseline before ORG-ROOT-001: `324 passed`, `37 failed`, `33 errors`.
- Full-suite run during implementation: `346 passed`, `40 failed`, `33 errors`; the three additional failures were legacy assertions expecting `204` from user deactivation. Those assertions were updated to the required JSON contract and pass in the final focused regression. The remaining 37 failures and 33 errors match the previously documented Commercial, Production, and Workforce baseline gaps.
- `git diff --check` reported no whitespace errors (only repository line-ending warnings).
