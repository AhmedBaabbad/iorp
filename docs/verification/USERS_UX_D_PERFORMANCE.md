# USERS-UX-D performance correction

The users list no longer computes deletion eligibility or exposes a permanent
delete action. It loads users and their roles in two queries total, independent
of the number of users and metadata tables. UserListItem no longer contains
can_delete_permanently. Deletion eligibility remains on the details response;
the locked delete transaction still rechecks it before changing data.

GET /api/v1/admin/users/{user_id}/presence requires foundation:users:read and
selects only last_seen_at/status in one organization-scoped foundation_users
query. A foreign or missing user returns 404. The detail timer uses this endpoint
and merges only presence fields; it never reloads eligibility or closes dialogs.
Authentication's existing presence/throttle behavior is unchanged.

Security history is checked with a SELECT 1 ... LIMIT 1 predicate in SQL. The
same total boolean defines the single UPDATE used to detach personal events.
PostgreSQL uses JSONB ->> and jsonb_typeof; SQLite tests use JSON1. Null details
are allowed for personal events, while non-object details, unknown events,
foreign organization references and explicit references to another account
remain blocking. sessions_ended is personal only for ended_by_user/session_limit.
There is no loading of security event rows or identifier lists into Python.

Migration f6a1b2p2 follows f6a1b2p1 and adds
ix_foundation_security_actor_event(actor_id, event_type). A real PostgreSQL
upgrade/downgrade test verifies the index and JSONB predicate parity, including
bulk detachment of 2,000 token events.

## Query measurements

Using the shared SQLite fixture with an authenticated current-context override
(authentication resolution is excluded), a 20-user list on the previous PR
route implementation issued 1,180 SQL statements. The corrected endpoint issues
2 for both 2 and 20 users. The new presence endpoint issues 1. A separate test
proves 2,000 security events detach in 1 UPDATE. These assertions use SQLAlchemy
before_cursor_execute listeners. This is a statement-count check, not a latency
benchmark.

## Dependency fixes

- dnspython 2.9.0 -> **2.9.2**, the minimum published fix for
  [GHSA-vvf4-9x63-8xvv / CVE-2026-128089](https://github.com/advisories/GHSA-vvf4-9x63-8xvv).
- opentelemetry-api 1.45.1 -> **1.45.2**, the minimum published fix for
  [GHSA-mf5v-w3w3-f6cg / CVE-2026-126360](https://github.com/advisories/GHSA-mf5v-w3w3-f6cg).

Both production/dev lockfiles were regenerated with uv 0.13.1, Python 3.12
x86_64-unknown-linux-gnu, SHA-256 hashes, no header and line annotations, using
the pinned backend Python image. Constraints were extracted from the existing
dev lock; only these two versions changed. Commands are the same as
SECURITY_DEPENDENCY_UPDATE_2026-11-04.md. No security exceptions were added.

## ملخص عربي

الحذف النهائي من صفحة التفاصيل فقط. القائمة تنفذ استعلامين، وتحديث الحضور
ينفذ استعلامًا واحدًا دون إعادة فحص أثر العمل. فحص أحداث الأمان وفصلها يجريان
في SQL مع إبقاء الأحداث الإدارية وسجلات العمل مانعة للحذف. أضيف الفهرس في
migration f6a1b2p2، وحُدّثت المكتبتان إلى أقل نسختين مصلحتين دون استثناء جديد.

Final complete-suite and CI results are recorded in PR #14.
