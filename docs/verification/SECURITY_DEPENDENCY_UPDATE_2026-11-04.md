# Security dependency update — 2026-11-04

Base: `origin/main` at `9134fd9`. Branch: `fix/security-deps`, independent of backup PR #2. No application behavior or deployment change is intended. Merge requires Claude review and green CI.

## Selected fixes

| Package | Before | Locked after | Reason |
|---|---|---|---|
| next / eslint-config-next | 15.5.27 | 15.5.29 | Patch release within 15.5; no Next 16 migration |
| postcss | 8.4.31 | 8.5.32 | Fixed sourceMappingURL/file disclosure and stringify advisories; override floor 8.5.23 |
| sharp | 0.34.5 | 0.35.5 | Patched libvips/libheif/librsvg dependencies |
| source-map-js | 1.2.1 | 1.2.2 | Indexed source-map offset DoS fix |
| pypdf | 6.20.1 | 6.21.4 | Minimum fixing all findings in the baseline audit |
| pyasn1 | 0.6.4 | 0.6.5 | ASN.1 parsing fixes; explicit security floor |
| Pillow | 12.3.0 | 13.0.0 | Actual CI-equivalent audit also found Pillow advisories; removes the old `<13` upper bound |
| certifi | 2026.7.22 | 2026.10.18 | Additional finding from the same audit |
| dnspython | 2.8.0 | 2.9.0 | Additional finding from the same audit |

The nearest patch fixing the reported critical Next finding is **15.5.28**, per the [official October security update](https://nextjs.org/blog/nextjs-security-update-october-14-2026) and [GHSA-2464-fhr4-w9xw](https://github.com/advisories/GHSA-2464-fhr4-w9xw). We select **15.5.29** because its [official November 3 release](https://github.com/vercel/next.js/releases/tag/v15.5.29) includes three additional moderate security fixes in the same maintenance line. No `npm audit fix --force` or major Next upgrade is used.

[Pillow 13 release notes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html) cover its security fixes and compatibility changes. IORP's actual Pillow usage is upload decoding, image normalization/thumbnails/quantization and logo preparation; the tests cover these paths. PDF parsing uses pypdf in `GotenbergRenderer`.

Pillow 13 drops Python 3.10 support. Accordingly, project metadata now requires Python **3.11 or newer**; the deployment image, CI and validation remain pinned to **3.12**. Existing Python 3.10 development environments must be recreated with a supported interpreter before installing these locks.

## Lock generation

JavaScript uses exactly `node:24-alpine@sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f` (Node 24.22.0, npm **11.19.1**):

```sh
npm install --package-lock-only --no-audit --no-fund
npm ci --no-audit --no-fund
npm audit --omit=dev --audit-level=high
```

Python uses the prior **uv 0.13.1** compiler, SHA-256 hashes and the pinned backend Python 3.12 Linux image. A temporary `../.tmp/tested-constraints.txt` is extracted from the baseline dev lock's `package==version` lines, changing only the five Python packages in the table. All other versions remain unchanged in both output locks. From `backend/`:

```sh
uv pip compile pyproject.toml --python-version 3.12 --python-platform x86_64-unknown-linux-gnu \
  --generate-hashes --no-header --annotation-style line \
  --constraint ../.tmp/tested-constraints.txt --output-file requirements.lock
uv pip compile pyproject.toml --python-version 3.12 --python-platform x86_64-unknown-linux-gnu \
  --generate-hashes --no-header --annotation-style line --extra dev \
  --constraint ../.tmp/tested-constraints.txt --output-file requirements-dev.lock
pip install --require-hashes --no-deps -r requirements-dev.lock
```

No new `--ignore-vuln` IDs are added. CI retains only the seven pre-existing IDs documented in `.github/security-exceptions.md`. The shipped JavaScript gate is strengthened from critical-only to high-and-critical.

## Deterministic dates

- Delegations fixes `Date` at `2026-10-15T12:00:00Z`, inside its October fixture's validity window. `vi.useFakeTimers({toFake: ['Date']})` plus `vi.setSystemTime` leaves polling/notification timers real; cleanup restores real timers.
- Notification fixtures now use the same fixed instant and freeze `Date` for relative labels/announcement date limits.
- Return-window tests freeze `Date` rather than comparing live instants around a boundary.
- Session-guard tests already fake timers; they now explicitly set their initial clock before generating token expiry/activity timestamps.
- Other date literals are server-response fixtures. The search covers `new Date()`, `Date.now()`, date construction and existing fake-clock usage across frontend tests.

## Verification

- `npm ci` succeeded in the pinned Alpine image. `npm audit --omit=dev` reports **0 vulnerabilities**, including high and critical.
- CI-equivalent `pip-audit==2.9.0 --strict --requirement backend/requirements.lock --disable-pip`, with the existing seven ignored IDs only, reports **no known vulnerabilities found, 7 ignored**.
- Full frontend typecheck, lint, tests and production build, full backend tests on Python 3.12, and reporting/image/real Arabic PDF verification are required before completion. Their final results are recorded in the PR.
- No production credentials, deployment, backup code or changes from the user's existing frontend worktree are included.
