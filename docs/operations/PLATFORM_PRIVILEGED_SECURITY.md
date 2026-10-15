# Platform privileged access — Batch 3

Applies only to Platform accounts. Tenant authentication is unchanged. No production rollout is performed by this change.

## Configuration and controlled rollout

1. Apply the additive migration `f6a1b2o7` on a disposable database first. Keep the existing backup and key recovery procedure. Do not downgrade/drop enrolled factor tables.
2. Install the declared PyOTP and cryptography dependencies. Reference: [PyOTP security checklist](https://pyauth.github.io/pyotp/) and [Fernet/MultiFernet](https://cryptography.io/en/stable/fernet/).
3. Generate a separate Fernet key offline with `Fernet.generate_key()`. Supply it through the deployment secret manager as `PLATFORM_MFA_KEYS`; never reuse the JWT signing key, commit a key, or put a key in a support ticket. Back up keys separately from the encrypted database, with restricted access and tested recovery.
4. Leave `PLATFORM_MFA_REQUIRED=false` during enrollment. Every **enrolled** account must already present TOTP or an unused recovery code at login, regardless of this flag. Step-up is enforced on organization and administrator mutation endpoints during the optional rollout too; unenrolled administrators verify their current password.
5. Open `/platform/security`. Reauthenticate, add the one-time setup key to a TOTP authenticator (30-second period, six digits, SHA-1 standard), save the ten recovery codes in a private password manager, and confirm with a current TOTP. Setup expires in ten minutes. Confirmation invalidates all existing sessions. The one-time key and recovery codes must not be captured in screenshots, browser recordings or telemetry.
6. Verify login, a sensitive action, recovery-code consumption, and the offline operator recovery procedure on disposable accounts. Enroll at least two administrators with independently stored recovery material.
7. Only after operator sign-off, explicitly configure `PLATFORM_MFA_REQUIRED=true` and restart. Unenrolled accounts can then access only their enrollment/status endpoints. This flag is **not** enabled by migration, tests or this delivery.

Keys are newest-first comma-separated Fernet keys. Encryption uses the first; decryption accepts all configured keys. Keep old keys until every existing ciphertext has been deliberately re-encrypted and backups have passed retention. Removing an old key early makes those factors unavailable; recovery codes/offline recovery remain the fallback. No automatic key rotation is claimed.

## Daily behavior

- Login uses password plus TOTP/recovery code for enrolled accounts. Successful TOTP counters cannot be reused, including concurrently; recovery codes are high-entropy, hashed, single-use values.
- Verification locks for 15 minutes after five failed factor attempts, with request throttling as an additional control. Synchronized server clocks are required. Allow at most one adjacent time step for clock skew.
- Sensitive actions prompt for current password and a fresh factor when enrolled. The grant lasts two minutes and is bound to account, session, HTTP method, path, and JSON payload. It is consumed once before executing the action; a failed action requires fresh authorization.
- Existing Platform session expiration remains authoritative. There is no background keepalive added by this feature. On expiration the UI returns to login; unsent changes may need re-entry.
- Replacing recovery codes or disabling MFA revokes sessions and outstanding grants. The replacement codes are shown once; the UI requires acknowledgement before returning to login.

## Recovery without permanent administrator lockout

1. Lost authenticator: sign in using the password plus one unused recovery code. Use another unused recovery code for the step-up prompt to disable the old factor, sign in, and enroll a new authenticator. Mandatory rollout still blocks ordinary administration until re-enrollment.
2. No usable codes, lost encryption key, or inaccessible authenticator: this is a server-operator incident, **not** a public reset endpoint. Verify the administrator's identity independently, obtain a second operator's approval, record an incident ID, and use a restricted server console:

   `python -m app.cli.recover_platform_mfa --account-id <UUID> --reason "Incident ID and independently verified recovery reason"`

   The command requires exact email confirmation, removes only that account's factor, invalidates all its sessions/grants, and atomically writes an operator-recovery audit entry. It does not change the password, roles, status or tenant accounts. It never prints a secret. Re-enroll immediately; preserve and review the operator access log alongside the application audit.
3. This command was tested against isolated fixtures only. Its production execution requires an explicit operational decision and authorized access. Do not run it as a routine support action.

## Deployment security and rollback

Production disables `/docs`, `/redoc` and `/openapi.json`, requires explicit HTTPS CORS origins and Secure cookies, and adds conservative response headers. No restrictive CSP is enforced: compatibility with existing Next.js inline scripts and report previews requires a separate report-only evaluation first.

The MFA migration adds two tables and preserves their data on downgrade (downgrade deliberately refuses). Prefer forward fixes. If application rollback is necessary, block external Platform access at the reverse proxy first: an older application does not enforce MFA or step-up. Preserve keys and factor tables, invalidate sessions through an authorized maintenance procedure, verify the recovery point, and restore Platform access only with tested security enforcement. Tenant workflows can remain available independently.

TOTP is not phishing-resistant. Hardware-backed authentication is a possible later enhancement, not part of this batch. Factor and step-up throttling supplements existing login controls; deployment-level rate limiting remains useful for multi-worker installations. Expired step-up rows require normal operational retention planning.
