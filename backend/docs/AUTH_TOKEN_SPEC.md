# IORP Authentication Token Specification

Status: implemented by ORG-AUTH-003. This document is normative and must change with the implementation.

## 1. Purpose and threat model

IORP uses signed JWT access tokens and stateful, rotating JWT refresh tokens. The design prevents platform/tenant token confusion, cross-tenant access, long-lived stolen access, refresh replay, and continued access after password, account, or organization lifecycle changes. Missing, malformed, legacy, incorrectly scoped, or incorrectly typed tokens fail closed.

## 2. Identity boundaries

`account_type=tenant` represents a `foundation_users` identity and requires `organization_id`. `account_type=platform` represents a `system_platform_accounts` identity and forbids `organization_id`. Neither identity type is inferred from a route or another claim. Every protected dependency validates the explicit type and current database identity.

## 3. Claims

| Claim | Access | Refresh | Tenant | Platform |
|---|---:|---:|---:|---:|
| `sub` account UUID | required | required | required | required |
| `account_type` | required | required | `tenant` | `platform` |
| `token_type` | `access` | `refresh` | required | required |
| `jti` unique UUID | required | required | required | required |
| `token_version` integer | required | required | required | required |
| `iat`, `nbf`, `exp` | required | required | required | required |
| `iss`, `aud` | required | required | required | required |
| `organization_id` | required | required | required | forbidden |

Passwords, password hashes, refresh-token plaintext, and authorization catalogs are never claims. Platform role is an optional access-token hint; current database authorization remains authoritative.

## 4. Expiry policy

- Tenant access: 15 minutes (`TENANT_ACCESS_TOKEN_MINUTES`, 1–60).
- Platform access: 10 minutes (`PLATFORM_ACCESS_TOKEN_MINUTES`, 1–30).
- Tenant refresh: 7 days (`TENANT_REFRESH_TOKEN_DAYS`, 1–30).
- Platform refresh: 24 hours (`PLATFORM_REFRESH_TOKEN_HOURS`, 1–168).
- Validation clock skew: 30 seconds (`JWT_CLOCK_SKEW_SECONDS`, 0–120).

`JWT_ISSUER` and `JWT_AUDIENCE` must match. Existing access tokens are never extended.

## 5. Login, refresh, and logout

Login validates credentials and account/organization state, creates an access token and refresh session, returns only the access token, and places the refresh JWT in an HttpOnly cookie scoped to the corresponding API path.

Refresh flow:

1. Browser sends the HttpOnly cookie to the tenant or platform refresh endpoint.
2. API verifies signature, issuer, audience, expiry, token type, identity scope, current status, organization state, and exact `token_version`.
3. API locks the stored session row, creates one successor in the same `family_id`, and revokes the presented row.
4. API returns a new access token and replaces the cookie.

Reusing a rotated token produces `TOKEN_REUSED`, revokes every active member of the family, records `refresh_token_reuse_detected`, and requires a new login.

Logout revokes the presented refresh session and clears its cookie. Tenant endpoints are `/api/v1/auth/{login,refresh,logout}`; platform endpoints are `/api/v1/platform/{login,refresh,logout}`.

## 6. Persistence and revocation

`core_auth_sessions` stores only SHA-256 of refresh `jti`, plus family, scope, account, expiry, replacement, and revocation metadata. It never stores the raw JWT. `core_auth_security_events` records security events without token plaintext.

Exact `token_version` mismatch invalidates both access and refresh tokens. Password change/reset and account lock/deactivation increment the version and revoke active stored sessions. Suspending, deactivating, or archiving an organization revokes its tenant sessions. Reactivation never restores them.

## 7. Browser policy

Refresh tokens use `HttpOnly`, configured `Secure`, configured `SameSite`, and a tenant/platform API path. They never appear in response JSON, localStorage, sessionStorage, application logs, or JavaScript. The frontend coordinates concurrent 401 responses through one refresh promise and retries each request once. Failed refresh clears the correct access state and redirects to the correct translated login screen.

Production must use HTTPS with `REFRESH_COOKIE_SECURE=true`. `SameSite=none` also requires Secure. Local HTTP development may explicitly use Secure=false.

## 8. Error contract

Authentication failures use non-enumerating messages and one of: `INVALID_TOKEN`, `TOKEN_EXPIRED`, `TOKEN_TYPE_INVALID`, `TOKEN_REVOKED`, `TOKEN_REUSED`, `SESSION_INVALIDATED`, `ACCOUNT_INACTIVE`, `ORGANIZATION_UNAVAILABLE`, or `RATE_LIMIT_EXCEEDED`.

## 9. Configuration

`JWT_ISSUER`, `JWT_AUDIENCE`, `TENANT_ACCESS_TOKEN_MINUTES`, `PLATFORM_ACCESS_TOKEN_MINUTES`, `TENANT_REFRESH_TOKEN_DAYS`, `PLATFORM_REFRESH_TOKEN_HOURS`, `JWT_CLOCK_SKEW_SECONDS`, `REFRESH_COOKIE_NAME`, `REFRESH_COOKIE_SECURE`, `REFRESH_COOKIE_SAMESITE`, and `IORP_REFRESH_RATE_LIMIT` are validated at startup. Secrets belong only in runtime configuration.

## 10. Migration and compatibility

Migration `f6a1b2f5` creates the session and event tables. Tokens issued before ORG-AUTH-003 lack mandatory claims and are rejected immediately; deployment therefore requires users to sign in again. No indefinite compatibility switch exists.

## 11. Example payloads

Tenant access (illustrative values only):

```json
{"sub":"00000000-0000-0000-0000-000000000001","account_type":"tenant","token_type":"access","organization_id":"00000000-0000-0000-0000-000000000002","jti":"00000000-0000-0000-0000-000000000003","token_version":4,"iat":0,"nbf":0,"exp":0,"iss":"iorp-api","aud":"iorp-web"}
```

Platform refresh omits organization scope:

```json
{"sub":"00000000-0000-0000-0000-000000000004","account_type":"platform","token_type":"refresh","jti":"00000000-0000-0000-0000-000000000005","token_version":2,"iat":0,"nbf":0,"exp":0,"iss":"iorp-api","aud":"iorp-web"}
```

## 12. Security event coverage

The implementation records `access_token_issued`, `refresh_token_issued`, `refresh_token_rotated`, `refresh_token_revoked`, `refresh_token_reuse_detected`, `session_revoked`, `all_sessions_revoked`, and `token_validation_failed`. Events contain available account/scope, hashed JTI, IP, user-agent, time, and reason. Validation failure responses deliberately avoid sensitive identity information.
