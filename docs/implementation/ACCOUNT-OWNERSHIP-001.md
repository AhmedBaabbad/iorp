# ACCOUNT-OWNERSHIP-001

Implemented 2026-10-14. Policy: ../adr/ADR-010-account-ownership.md.

## Backend
- foundation/application/services.py rejects administrative personal edits, keeps self-service, validates/persists owner timezone, blocks activation of archived accounts.
- foundation/application/email_change.py implements password reauthentication, both-mailbox verification, hashed short-lived secrets, transactional audit, session/reset-token invalidation.
- foundation/api/routes_auth.py exposes authenticated rate-limited request/confirmation.
- foundation/api/routes_users.py requires lifecycle reasons, adds archive/restore and a named deactivate endpoint, removes the misleading hard-delete alias. Historical DELETE requests now also require a reason.
- foundation/api/schemas.py and infrastructure/models.py expose only safe account fields; verification secrets are not in responses.
- foundation/domain/audit_labels.py localizes the new audit actions.

## Frontend
- admin-users/components/AdminUserForm.tsx creates invitations only and offers invitation language.
- admin-users/components/AdminUsersList.tsx and AdminUserDetail.tsx remove personal-edit controls and expose archive/restore, reasons, archive filtering, timezone and account policy.
- app/admin/users/[id]/edit/page.tsx redirects old bookmarks to user detail.
- admin-users/api/admin-users-api.ts, admin-users/types/index.ts update lifecycle contracts.
- auth/email-change-form.tsx adds the owner email-verification flow; auth/my-profile-page.tsx adds owner timezone.
- types/auth.ts, hooks/useFormatter.ts use the personal timezone with organization fallback.
- Arabic/English administration, profile and tenant-audit dictionaries updated.

## Database
f6a1b2o6 applied locally after f6a1b2o5. Nullable account fields and one verification table; existing records preserved. PostgreSQL isolated-schema upgrade/downgrade test passed, including refusal to downgrade populated policy data.

## Validation
- account-ownership-tests.log: 60 passed (account policy, profile and lifecycle suites).
- PostgreSQL migration test: 1 passed.
- Frontend email change and effective permissions: 4 passed.
- TypeScript and Arabic/English translation validation passed (32 pairs).
- Password-reset regression: 9 passed (backend/account-password-regression.log).
- No real emails sent during tests. No browser visual QA or production build claimed.

## Boundaries
- Physical deletion is deliberately unavailable; unused invitations are cancelled by deactivation and may then be archived, preserving the creation audit.
- Root identity remains protected by the existing root policy. No new bypass was introduced.
- Workforce official identity remains in the workforce module; this change does not duplicate employee data into login records.
- NOT IMPLEMENTED: optional avatar upload, a separate email-verification timestamp displayed for historical accounts, automated lost-mailbox recovery, or automatic retention/erasure jobs. Existing accounts are not falsely marked as email-verified.
