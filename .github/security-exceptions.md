# Accepted dependency advisories (reviewed 2026-10-15)

CI ignores only these IDs. Each needs a fix or re-review before its review date; a new advisory fails the build.

| ID | Package | Why it is accepted now | Exit |
|---|---|---|---|
| PYSEC-2026-249 | starlette 0.52.1 | `request.form()` limits not fully enforced (resource use on multipart uploads). Mitigation: body-size limit at the reverse proxy; uploads read with `files.read_limit`. | Upgrade to Starlette ≥ 1.3.1 (needs a FastAPI release supporting it). Review by 2026-11-15 |
| PYSEC-2026-161, PYSEC-2026-248 | starlette 0.52.1 | `request.url` rebuilt from the Host header. IORP builds links from `FRONTEND_URL`, not `request.url`; Traefik routes by Host. | Same upgrade |
| PYSEC-2026-2280, PYSEC-2026-2281 | starlette 0.52.1 | `HTTPEndpoint` / `StaticFiles` on Windows — neither is used. | Same upgrade |
| CVE-2026-85394 | python-jose 3.5.0 | HMAC key confusion; IORP pins `HS256` with a server secret, no client-supplied keys. No fixed release. | Replace with PyJWT. Review by 2026-12-31 |
| PYSEC-2026-1325 | ecdsa 0.19.2 | Timing attack on P-256 signing; not used by IORP (transitive of python-jose). | Goes with python-jose |

JavaScript: CI blocks critical advisories in shipped dependencies (`npm audit --omit=dev --audit-level=critical`). Known high advisories (postcss, sharp via Next) are build-time / unused-path issues — see `docs/architecture/foundation-hardening/DEPENDENCY_SECURITY_REVIEW.md`.
