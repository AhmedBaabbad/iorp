# Production readiness — execution plan

Authorized scope: baseline → four P0 workstreams → transaction safety and recovery. SaaS expansion is deferred.

Baseline: source manifest `baseline.json`, local source archive `.tmp/readiness-source-baseline.zip`, branch `fix/production-readiness-20261008`. Existing user changes are preserved. Runtime secrets and uploads are excluded from the source archive; it is not a database backup.

| Stage | Work | Acceptance | Status |
|---|---|---|---|
| Baseline | source snapshot, isolated Python environment, existing audit evidence | reproducible source and dependency versions | in progress |
| P0 dependencies | compatible patched frontend/backend, locks, scans | clean applicable security scans, tests and build | pending |
| P0 migrations | load Master Data metadata | parity regression test, no unintended drops | pending |
| P0 configuration | fail unsafe production config, suppress reset secrets | configuration/log-redaction tests | pending |
| P0 authorization | scope-aware sample aggregate | own/team/org/foreign-tenant tests | pending |
| Transactions | reset-token single-use concurrency; bounded email; file compensation; sensitive audit review | fault/concurrency tests and persisted-state assertions | pending |
| Recovery | backup/restore tooling and isolated drill; readiness checks; deployment gates | verified restoration and explicit operational limitations | pending |

No application-table migration will run before an appropriate data backup. Each implementation gets a focused regression test and relevant architecture checks. A source rollback is separate from database/file recovery. Final production approval requires the documented operational checks; no automatic production deployment is authorized or planned.
