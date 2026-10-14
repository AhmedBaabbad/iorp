# ADR-010 — Account ownership and administrative access

Date: 2026-10-14

Personal details are changed through authenticated self-service only. Tenant administrators create initial invitations and administer access, roles, locks, deactivation and archival. The previous admin PATCH path rejects personal changes in the application service; the edit page redirects to detail. Existing organization-root identity protection remains in force.

A login account is distinct from a workforce record. Do not copy department, official identity, title or employee number into foundation_users. Existing workforce linking remains the source of that relationship. Optional account timezone belongs to the user; organization timezone remains the default. Avatar upload is not part of this change.

Changing email requires the current password, independent proof from both mailboxes, a 15-minute expiry, hashed verification secrets, rate limiting and an authenticated confirmation. The update invalidates existing sessions and outstanding reset links and is audited in the same transaction. A new request replaces the old one. Root identity changes and lost-mailbox recovery have no administrative bypass in this release.

Lifecycle commands require a nonblank reason. Existing dependency checks and root/self protections remain. Deactivation revokes access and retains historical actor IDs. Archive is only available after deactivation; restore leaves the account inactive and activation is a separate authorized action. Archive state is not a new authentication status. Administrative lists can include archived accounts explicitly; existing operational active-only selectors exclude them.

No physical deletion is exposed: unused invitations may be cancelled through deactivation and then archived. Audit history itself is a meaningful association, even when there are no production documents. Neither retirement nor reassignment rewrites historical attribution. The former misleading /hard alias is removed. DELETE remains a compatibility alias for deactivation with a required reason; new clients use POST /deactivate. External clients must supply the reason.

Permissions reuse users:read, users:write (creation), users:deactivate (including archive), users:activate (including archive restoration), users:lock, and users:reset_password. No role names authorize operations. Physical deletion, automated retention erasure, photo storage, and automated lost-mailbox recovery are NOT IMPLEMENTED.

Migration f6a1b2o6 follows f6a1b2o5. It adds nullable timezone, archived_at, account_change_reason and a temporary email-verification table. No existing user rows are removed or rewritten. Downgrade refuses to discard populated new fields or pending verification records.
