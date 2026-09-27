# Platform Administrative Audit Log

## Purpose

`core_auth_security_events` is the append-only source of truth for sensitive platform administration, authentication, authorization, and session-security events. The implementation extends the existing ORG-AUTH-003 security-event store instead of creating a second competing log.

## Event contract

Every event has an immutable UUID, occurrence time, event type, category, outcome, severity, and actor type. Optional snapshots preserve the actor name/email and target display text as they appeared when the operation happened. Request and correlation IDs connect events to HTTP activity. Organization ID scopes tenant-related targets without making the audit row tenant-owned.

Allowed categories are `identity`, `organization`, `authentication`, `authorization`, `security`, `configuration`, and `audit`. Outcomes are `success`, `failure`, or `denied`; severities are `info`, `warning`, or `critical`; actor types are `platform`, `tenant`, `system`, or `anonymous`.

## Security rules

- The service is append-only. The HTTP API intentionally exposes only list, detail, and CSV export endpoints; no update or delete endpoint exists.
- Read access requires `platform:audit:read`. CSV export separately requires `platform:audit:export`, reserved for the platform root by the current role policy.
- Passwords, secrets, tokens, cookies, authorization headers, API keys, and credentials are recursively removed from changes and metadata before persistence.
- Structured payloads have depth, item-count, string-length, and total-size bounds.
- CSV cells beginning with spreadsheet formula characters are prefixed to prevent formula injection.
- Request IDs supplied by clients are accepted only from a conservative 64-character alphabet; otherwise the server generates a UUID.
- Audit rows are platform-governance records and are never returned by tenant endpoints.

## HTTP API

- `GET /api/v1/platform/audit-logs` supports pagination, ordering, full-text-like search, and filters for event/category/outcome/severity/actor/organization/target/request/correlation/time range.
- `GET /api/v1/platform/audit-logs/{id}` returns one event.
- `GET /api/v1/platform/audit-logs/export.csv?locale=ar|en` exports at most 10,000 filtered rows and records the export itself.

## Retention and operations

The proposed retention period is 365 days. Rows are not automatically deleted in v0.1. Any future purge must be a protected, tested, auditable CLI/job unavailable to tenant users. Database roles used by the application should not receive direct `UPDATE` or `DELETE` privileges on this table. Monitor critical events and repeated denied outcomes, and treat gaps in event ingestion as an operational incident.

## Supported event types and current coverage

Current platform flows emit account creation/update/role change/deactivation/password reset, platform login success/failure, organization creation and lifecycle changes, organization-root password reset, permission denial, bootstrap completion, audit export, and JWT issue/rotation/revocation/reuse events. Reserved codes for future existing flows include account activation, organization provisioning/profile outcomes, configuration/policy changes, and explicit cross-scope-token rejection. Adding a new event requires a stable snake-case code, the closest allowed category, a documented severity/outcome, central sanitization, and tests for both persistence and redaction.

## Transaction and privacy semantics

Call `record()` before committing the sensitive operation so an audit-write failure aborts that transaction. Failure events that must survive a business rollback require a deliberately separate transaction; they must never be fire-and-forget. Snapshots should contain only the minimum identity and target context needed for investigation. Avoid personal or business payloads in metadata and changes; record identifiers and changed safe fields only. A database administrator can still alter storage directly, so this implementation is append-only through application boundaries, not cryptographically tamper-proof.

Example safe change: `{"status": {"before": "active", "after": "suspended"}}`. A password event records only `{"password_changed": true, "sessions_invalidated": true}`.
