# Login protection operations

Tenant and platform login use three independent controls: an IP request window,
a database-backed failed-attempt counter, and a temporary account lock. Organization
Root and Platform Root remain subject to the IP window but are exempt from temporary
account lockout.

## Configuration

- `IORP_LOGIN_MAX_ATTEMPTS` (default `5`)
- `IORP_LOGIN_LOCKOUT_MINUTES` (default `15`)
- `IORP_LOGIN_RATE_LIMIT` (default `10` requests/minute/IP)
- `IORP_PLATFORM_LOGIN_MAX_ATTEMPTS` (default `3`)
- `IORP_PLATFORM_LOGIN_LOCKOUT_MINUTES` (default `30`)
- `IORP_PLATFORM_LOGIN_RATE_LIMIT` (default `5` requests/minute/IP)
- `IORP_TRUSTED_PROXY_IPS` (default `127.0.0.1,::1`)

`X-Forwarded-For` is used only when the direct peer is listed in
`IORP_TRUSTED_PROXY_IPS`. Configure the reverse proxy to replace, not append to,
untrusted client headers.

## Deployment limitation

The v0.1 IP window is process-local. It is suitable only for a single backend worker.
Before enabling multiple workers or instances, replace it with a shared Redis-backed
limiter. The database account counter and temporary lock remain shared across workers.
