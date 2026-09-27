# ORG-ROOT-002 Implementation Report

## Diagnosis

| Question | Before this task | Resolution |
|---|---|---|
| Q1: tenant `token_version` | Missing from `foundation_users` | Added as non-null integer with default `0` and an Alembic migration |
| Q2: tenant JWT claim | Missing | Login now embeds the user's current version |
| Q3: password change | Endpoint existed without policy/session invalidation | Current-password verification, role-aware policy, and version increment are enforced |
| Q4: platform access to tenant credentials | No supported credential recovery path | Platform uses `UserCredentialInterface`; it does not import Foundation |
| Q5: CLI pattern | Existing commands use `argparse`/`getpass` | Added an interactive `getpass` recovery command |

Platform accounts already had an independently validated `token_version`. Passwords use Passlib with bcrypt.

## Security behavior

- Tenant JWT validation rejects a JWT whose version is lower than its user's database version.
- Every tenant self-service password change increments only that user's version.
- Organization Root passwords require at least 12 characters; other tenant passwords require 8.
- A password cannot equal the account email, equal the current password, or differ from its confirmation.
- Platform Root recovery and CLI recovery do not require the old tenant password and invalidate all earlier tenant sessions.
- Password hashes remain confined to the credential persistence layer and are never returned.

## Cross-module boundary

`app.core.interfaces.user_credentials.UserCredentialInterface` exposes only root lookup and password-reset operations. `FoundationUserCredentials` implements it, dependency injection supplies it, and Platform consumes the protocol without importing `app.foundation`.

## CLI

From the backend environment:

```console
python -m app.cli.reset_org_root_password
```

With Docker:

```console
docker exec -it iorp-backend python -m app.cli.reset_org_root_password
```

The command lists organizations, accepts the code case-insensitively, obtains both password entries through `getpass`, repeats invalid password input, and never prints the password.

## Frontend and localization

- `/admin/change-password` supports tenant self-service and signs the user out after success.
- The authenticated user menu links to the page.
- Platform organization actions expose a Root-only recovery dialog.
- All new visible Arabic and English copy resides in the corresponding `auth.json`, `navigation.json`, and `platform.json` locale files.

## Verification

- ORG-ROOT-002 focused scenarios: `5 passed` (grouped coverage for T01-T25 and T32-T35).
- Existing organization-root and platform-isolation suites: `43 passed`.
- Translation parity/UTF-8 scan: all 15 Arabic/English JSON pairs passed.
- TypeScript: passed with `npx tsc --noEmit`.

## Follow-ups

- T26-T31 require a dedicated CLI harness that injects a test session factory and captures `getpass`/console output.
- The repository-wide backend baseline contains unrelated pre-existing failures; focused security suites remain green.
