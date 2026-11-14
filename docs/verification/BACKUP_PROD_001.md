# BACKUP-PROD-001

Base: origin/main ee901537947605eeab1ce503d138c49e17496ec4.
Branch: fix/backup-production. Repository work and synthetic tests only; no VPS,
live Drive account, real environment file, application Compose or Dockerfile
was accessed/changed. Examples contain placeholders; test credentials/keys are
synthetic or generated in temporary directories.

## Most likely explanation of the reported retention failures

The old code requires every local folder to belong to the current remote
catalog. A reproducible ordinary sequence violates that requirement:

1. Several successful manual/daily backups run on the same UTC day.
2. Remote GFS keeps only the newest recovery point for that day; local retention
   keeps the latest three snapshots, including earlier snapshots of that day.
3. The following daily job sees those healthy local snapshots absent remotely
   and raises local-receipt, before it can prune local backups. Each subsequent
   successful upload adds another local backup but hits the same old orphan.

The owner confirmed this operating sequence: a manual backup before migrations
followed by the nightly backup on the same day. Local retention now follows
remote GFS in the same run: after each successful remote purge, its healthy
local copy is removed immediately. A failed purge retains that local copy and
returns remote-prune. Keep the newest three healthy local members of remote
keep, including the new backup. Normal deployment days never warn or accumulate
quarantine.

Regressions cover manual/nightly then next day, ten days with three double-backup
days, remote purge failure, and legacy orphans quarantined once only. A crash
after remote purge but before local deletion can still leave an abnormal orphan
and is tested separately. Unexpected local entries also triggered the old
local-layout failure. No server inspection was performed.

Interrupted remote uploads (b), valid rclone text
format (c) and more than seven otherwise valid local backups (e) do not alone
explain the old failure. Corrupt/legacy remote metadata remains another possible
failure with an explicit remote code; it must never be silently skipped.

## Safety and recovery behavior

Every completed remote candidate must authenticate/validate before any purge,
local deletion or quarantine. Uncompleted remote folders are preserved and not
recovery points. Unknown remote directories, invalid dates, duplicate names or
extra files/subdirectories in a completed backup fail closed. Loose environment
root files are not listed by dirs-only and are preserved; the environment root
is never purged.

Invalid local entries are atomically renamed into a private sibling quarantine
with a random envelope and original entry name. Contents and symlink targets
are never deleted to resolve an error. Only abnormal entries are quarantined: corruption, symlinks, invalid names,
unexpected items or orphans not explained by this run. Healthy copies follow
local three-copy retention within remote keep and existing remote 7/4/6 retention. No automatic quarantine cleanup:
it preserves evidence, consumes disk and requires owner review.

## rclone format verification

The [official hashsum documentation](https://rclone.org/commands/rclone_hashsum/)
describes native remote hashes without download. The shared formatter in
[rclone HashLister](https://github.com/rclone/rclone/blob/master/fs/operations/operations.go)
uses a fixed-width digest, two spaces and the object's relative path. Drive's
[MD5 capability](https://rclone.org/drive/#checksums) supplies the native hash;
the formatter does not depend on which backend supplies it.

Tests cover uppercase/lowercase hex, two-space separation, filenames containing
spaces and nested relative paths, malformed/duplicate lines and missing hashes.
A real rclone local-backend test checks the same formatter and depth-one
dirs-only listing without any cloud credentials. The backup CI job installs
rclone and runs this test in addition to both encrypted roundtrips. Complete
backups intentionally allow only the five known flat filenames; parsing a
nested path is not permission to accept it in a completed backup.

## New diagnostic codes

| Code | Meaning |
| --- | --- |
| production-only | A nonproduction daily/drill job or disk monitor was rejected before I/O |
| remote-list | Environment directory listing failed |
| remote-entries | Listing a backup's entries failed |
| remote-metadata-read | Downloading a small encrypted catalog file failed |
| remote-hashes | Requesting native hashes failed |
| remote-hash-format | A hash row was malformed or duplicated |
| remote-catalog-read | Unexpected metadata/decryption/JSON/catalog exception |
| remote-prune | Removing a validated obsolete remote backup failed |
| local-scan | Reading the local directory failed |
| local-quarantine | Preserving an invalid local entry by rename failed |
| local-prune | Removing a validated obsolete local backup failed |
| retention-plan | Another retention-planning exception occurred |
| unexpected | The failure was not Failure with exactly one allowed code argument |
| local-quarantined | Successful warning: local evidence was preserved in quarantine |

Existing manifest, receipt, remote-layout/completion/checksum and resource-limit
codes remain. The failure reason is never built from exception text or command
output. Journal and failed Push messages share the validated reason. No
traceback, path, URL, raw rclone output or environment value is emitted.

## Production preparation

Production is the only accepted environment. Templates are disabled by default,
use placeholders and leave DATABASE_URL blank. The owner runbook disables and
masks staging instances, creates a new production key, saves recovery material
offline and tests that saved key on an existing Drive backup before enabling
production timers. The administrative service uses a dedicated private Docker
configuration under its environment directory, without an account-specific
home path.

The runbook documents the pre-migration service/receipt gate, first and monthly
remote restore drills, RPO 24h and RTO 2h, and a separate deliberate emergency
restore. No migration or application image/Compose change is part of this fix.
Final commands, counts and CI result are recorded in the PR.

## Owner review correction

Same-day manual/nightly backups are normal. The runbook includes a read-only
quarantine size check; quarantine remains reserved for abnormal evidence and
is never automatically deleted. Tests and final CI results are recorded in PR.
