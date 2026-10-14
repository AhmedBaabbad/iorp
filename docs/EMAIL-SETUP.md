# IORP password reset email — Hostinger

Sender: `IORP <iorp@rehanh.com>`. Hostinger Email uses `smtp.hostinger.com:465` with implicit TLS; Hostinger Titan accounts use `smtp.titan.email:465` instead. Confirm the account type in hPanel.

Official references:
- https://www.hostinger.com/support/1575756-how-to-get-email-account-configuration-details-for-hostinger-email/
- https://www.hostinger.com/support/5966022-how-to-get-email-account-configuration-details-for-titan-email-at-hostinger/

## Activation

The local configuration has the sender and Hostinger connection details prepared. `EMAIL_MODE=console` intentionally remains until the mailbox password and frontend URL are supplied. Console mode sends no messages. Do not treat a generic forgot-password response as delivery confirmation.

From `backend`, run:

```powershell
python -m app.cli.configure_email --frontend-url http://localhost:3000
```

Use the actual HTTPS application URL instead for a published system. For Titan append `--provider titan`. If the platform uses a separate host, pass `--platform-url https://...`.

The command prompts for the **mailbox password**, authenticates over verified TLS, then saves the configuration locally and enables SMTP. It never prints the password or sends a message. Restart the backend afterward. Do not commit `backend/.env` or put secrets in frontend variables or chat.

If input produces `UnicodeEncodeError`, Python's SMTP login requires ASCII credentials. The setup command now detects unsupported/nonprinting input before connecting and allows three attempts. Switch to an English keyboard and type manually to avoid invisible marks copied from formatted text. It never strips or changes the password. If the actual mailbox password contains non-ASCII characters, change it in the provider panel first. A provider authentication rejection has a separate message and is not retried automatically.

`localhost` links open the recipient's own computer: valid only when testing on the same machine that runs IORP. The email domain is not automatically the application domain.

## Behavior and verification

- Requested UI language (`ar` / `en`) selects the email; tenant preference is the fallback. HTML RTL/LTR and plain text are both included.
- A reset URL is derived only from configured frontend URLs. Production requires HTTPS and disallows localhost.
- Tokens are random, stored as hashes, expire after 30 minutes by default, and are single-use. A new request invalidates older tokens. Failed SMTP delivery invalidates the new token.
- Password changes invalidate existing sessions. Suspended organizations cannot consume previously issued tenant reset tokens.
- Unknown/known addresses receive the same public response. Request rate limiting remains in place; its current in-process implementation requires a shared rate limiter when scaling to multiple workers/instances.
- The frontend reports network/rate-limit failures accurately; these do not make a valid reset link appear expired.
- Reset pages use no-referrer/no-store/noindex headers. Reverse proxy/access logs must also avoid recording reset query strings.

After activation, request a reset for a known test account, check Inbox/Spam, open the link on a device that can reach the application, change the password, and confirm the same link cannot be reused. Repeat in Arabic and English. Verify domain SPF/DKIM/DMARC status in the provider panel; DNS records have not been changed by this task.

No database migration is needed. Real SMTP delivery and inbox receipt remain unverified until credentials are supplied and the live test is performed. SMTP acceptance alone does not guarantee inbox placement.

## Validation (2026-10-13)

- Backend: `test_email_delivery.py`, `test_password_reset.py`, `test_readiness_p0.py`, `test_readiness_reset_postgres.py` with `RUN_POSTGRES_TESTS=1`: **25 passed, 1 failed**. The failure is the separate Alembic metadata registration test: `foundation_approval_delegations` and `foundation_approval_records` are missing from migration metadata imports in the current workspace. No email/reset behavior test failed.
- Frontend: `tests/components/password-reset.test.tsx`: **3 passed**, covering request locale, rate-limit failure, and retaining a valid token/form after a transient error.
- Secure configuration CLI `--help` executes successfully; no credentials supplied and no real email sent.
