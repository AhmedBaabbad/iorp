# Permanent user deletion without business history

This supersedes only permanent-deletion eligibility in USERS-OFFBOARD-E. The
transfer, deactivation and archiving workflow and its permissions are unchanged.
No migration is needed; all detached actor columns are already nullable.

Root and self are unconditional blockers. A usable password, login/presence or
account status is not itself history. Detail eligibility is advisory: DELETE
locks the user with `FOR UPDATE` and repeats the complete reference inventory in
the same transaction. Business references and unknown events fail closed.

## Explicit personal security-event allowlist

- `tenant.login_success`
- `tenant.login_failed`
- `tenant.token_refreshed`
- `tenant.session_revoked`
- `tenant.refresh_token_reuse_detected`
- `tenant.password_changed`
- `tenant.password_reset_via_email` (also activation acceptance)
- `tenant.auto_locked`
- `tenant.auto_lock_expired`
- `tenant.mfa_setup_started`
- `tenant.mfa_enabled`
- `tenant.mfa_disabled`
- `tenant.mfa_verification_failed`
- `tenant.mfa_recovery_codes_regenerated`
- `tenant.mfa_recovery_code_used`

`tenant.sessions_ended` is personal only for `ended_by_user` or `session_limit`.
Every exemption also requires the same organization, object/null JSON, and no
foreign subject under the explicit target keys (including nested `metadata`).
Arrays, scalars, contradictory target IDs and unknown event names block deletion.

Current MFA endpoints/models belong to **platform accounts**, not tenant users.
The six tenant MFA names above are an explicit event contract tested with
synthetic records; no tenant MFA feature or platform-deletion rule was added.

## Personal audit/activity allowlist

`user.password_changed`, `user.password_reset`, `user.email_change_requested`,
`user.email_changed`, and `user.updated` require `entity_type=user` and this user's
own entity ID. `user.updated` additionally permits only profile changes to
`full_name`, `phone`, `preferred_locale`, or `timezone`; status/role changes are
not profile edits. There is no wildcard exemption such as `user.*`.

These rows remain with `actor_id=NULL` and the existing name/email snapshot, or a
snapshot filled from the deleted user if empty. Their payloads are preserved.

## Actions on the user versus actions by the user

- Role-removal `user_id` is a subject UUID without an FK: preserve it unchanged.
  `removed_by` referring to this user on somebody else's removal blocks deletion.
  A self-removal's nullable actor FK is detached and counted, not its subject ID.
- Audit/activity entity IDs describing an administrator's action on the user
  remain as historical subject identifiers; they are not the user's actor history.
- Existing security writers store the subject in `actor_id` for
  `tenant.account_locked`/`tenant.account_unlocked` (with another `performed_by`)
  and `tenant.sessions_ended`/`ended_by_admin` (with administrator attribution).
  Detach the subject identity; an actual `performed_by` administrator acting on
  another subject remains a blocker even after that subject was deleted.
- Administrator session termination now also records `performed_by` as a UUID,
  alongside the existing name, to retain unambiguous actor attribution.

## Owned rows, tokens and polymorphic records

Only four tables are explicitly private: own role bindings, password-reset
tokens, pending email changes, and inbox notifications. A future CASCADE FK is
not automatically disposable. Assigning another user's role, authored
announcements, approvals, workforce links and every business-module FK remain
blockers. Cross-organization references also block.

All tenant `core_auth_sessions` rows, including old rotations and revoked rows,
are deleted in the transaction. Access-token validation requires the user and a
live session; refresh requires the stored session and active user. Tests verify
that existing access/refresh tokens fail immediately after deletion.

Legacy `core_auth_security_events` use polymorphic `account_id`: only explicit
tenant personal events with matching scope/subject are detached, retaining the
email/name snapshots. Unknown scopes fail closed; explicit platform-account
records are not tenant-user records.

The mandatory `user.deleted_permanently` event records deleted user ID, name,
email, reason, deleting actor and per-table deleted/detached counts. No password,
hash, refresh token or secret is included. Audit failure or a concurrent FK
conflict rolls back all cleanup. Conflict responses retain translated table-type
keys and also provide raw `table_names` for diagnosis.

The users list still performs no eligibility scans. Details use the shared
Dialog with required reason and exact trimmed full-name confirmation, translated
blocker lists, and a permission-respecting offboarding handoff.
