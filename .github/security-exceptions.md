# Accepted dependency advisories (reviewed 2026-10-15)

CI ignores only these IDs. Each needs a fix or re-review before its review date; a new advisory fails the build.

| ID | Package | Why it is accepted now | Exit |
|---|---|---|---|
| PYSEC-2026-249 | starlette 0.52.1 | `request.form()` limits not fully enforced (resource use on multipart uploads). Mitigation: body-size limit at the reverse proxy; uploads read with `files.read_limit`. | Upgrade to Starlette ≥ 1.3.1 (needs a FastAPI release supporting it). Review by 2026-11-15 |
| PYSEC-2026-161, PYSEC-2026-248 | starlette 0.52.1 | `request.url` rebuilt from the Host header. IORP builds links from `FRONTEND_URL`, not `request.url`; Traefik routes by Host. | Same upgrade |
| PYSEC-2026-2280, PYSEC-2026-2281 | starlette 0.52.1 | `HTTPEndpoint` / `StaticFiles` on Windows — neither is used. | Same upgrade |
| CVE-2026-85394 | python-jose 3.5.0 | HMAC key confusion; IORP pins `HS256` with a server secret, no client-supplied keys. No fixed release. | Replace with PyJWT. Review by 2026-12-31 |
| PYSEC-2026-1325 | ecdsa 0.19.2 | Timing attack on P-256 signing; not used by IORP (transitive of python-jose). | Goes with python-jose |

## JavaScript (reviewed 2026-11-17)

CI runs `npm audit --omit=dev --json` through `.github/scripts/npm_audit_gate.py`.
All high/critical findings block unless every advisory contributing to the finding
is explicitly exempt below. Critical findings are never exempt. Invalid reports,
unresolved dependency findings and audit execution failures also block.

| ID | Exact accepted production path | Rationale | Exit / review |
|---|---|---|---|
| [GHSA-fc5q-39xc-vjpf / CVE-2026-112366](https://github.com/advisories/GHSA-fc5q-39xc-vjpf) | `next-intl 4.13.1 → @parcel/watcher 2.5.6 → picomatch 4.0.5` at `node_modules/@parcel/watcher/node_modules/picomatch` | No patched picomatch release is published. In IORP, watcher is used only by next-intl's extractor `SourceFileWatcher` during development/build, with repository-controlled ignore globs. It does not process user input or execute on production request paths, so the vulnerable attacker-controlled repeated-extglob path is not reachable. | Remove immediately when a fixed picomatch or a next-intl update removes this dependency. Review **before 2026-12-17**. |

The gate checks the production lockfile path and consumers, not only the GHSA:
another production consumer/path to picomatch, a changed installed version, another
advisory (including mixed `via` findings), or a critical finding fails closed.
`@parcel/watcher` is exempt only when its entire `via` chain is this exception.
Development-only nodes are outside the shipped audit, as before. There is no
package-wide picomatch exclusion and no change to package versions or lockfiles.

The previously recorded Next/postcss/sharp/source-map-js findings were fixed on
2026-11-04; see `docs/verification/SECURITY_DEPENDENCY_UPDATE_2026-11-04.md`.
The older architecture review is historical, not an exemption for those packages.

Python: the 2026-11-04 update fixes pypdf, pyasn1, Pillow, certifi and dnspython. The seven IDs listed above remain the complete CI ignore list; no new ignore IDs were added.
