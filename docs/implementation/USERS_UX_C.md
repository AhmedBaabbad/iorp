# USERS-UX-C

Base: `89bc18b483d2c96391919003846f7132575ab14a`; migration `f6a1b2p1`
after `f6a1b2p0`. No deployment or operational user deletion is performed.

## Presence

`foundation_users.last_seen_at` is nullable TIMESTAMPTZ. Migration initially
copies known `last_login_at` values into it, without changing `updated_at`, so
existing users are not falsely described as never having signed in. A successful tenant
login sets it. Validated tenant access requests use a conditional direct UPDATE
at most once per 60 seconds, preserving `updated_at` and `token_version` and
writing no activity event. The WHERE condition also throttles concurrent
requests. Platform authentication and refresh-only calls do not invoke it.

One `PRESENCE_WINDOW` defines five minutes; active accounts seen in that window
are online. Only administration serializers with `foundation:users:read` include
`last_seen_at` and `is_online`; writer-only responses omit those two keys while
retaining the existing response defaults. Self-profile/platform DTOs do not
gain presence data. Lists refresh quietly every 60 seconds, stop the interval
when hidden, resume on visibility, and clear the interval on unmount.

## Guarded deletion

The actual existing router prefix is `/api/v1/admin`, so the new operation is
`DELETE /api/v1/admin/users/{user_id}/permanent`. It uses the existing
`AccountActionRequest` (required reason, 3–500 characters). The existing DELETE
deactivation endpoint and lifecycle rules remain unchanged.

`foundation:users:delete` and its bilingual labels already existed on main.
This change implements the previously reserved operation and clarifies its
description; it does not introduce a duplicate permission. The migration
ensures the permission exists and grants it to existing canonical
`organization_admin` roles only. Explicit custom-role assignments are retained.
New system-role seeding already grants it only to organization administrators.
Downgrade drops presence but retains the existing permission/grants to avoid
removing customized access that predates this revision.

Deletion locks the tenant-scoped user with SELECT FOR UPDATE and rechecks root,
self, activation and references inside that transaction. Activation means a
usable password, last login or last seen. Missing/foreign users return 404;
the four eligibility failures use the requested 409 codes. IntegrityError
rolls back and becomes `USER_DELETE_HAS_HISTORY`.

The metadata helper examines every FK to `foundation_users.id`, without
importing other modules' models. It additionally protects known immutable
non-FK references: audit actors, role-removal subjects and notification actors.
It reports the first five blocking table names in stable sorted order, without
record contents. Even a malformed cross-organization reference blocks deletion.
Only being the target inside security JSON does not block it; being its actor
does. The UI uses server eligibility, requires the exact email and reason,
translates conflicts and offers the existing deactivation flow for history.

## Final disposable self-owned tables / الجداول الذاتية النهائية

| Table | Rows deleted |
| --- | --- |
| `foundation_user_roles` | Only bindings whose `user_id` is the target |
| `foundation_password_reset_tokens` | Target's activation/reset tokens (`user_id`) |
| `foundation_user_email_changes` | Target's pending email change (`user_id`) |
| `core_auth_sessions` | Target's tenant account sessions in the same organization |

An assignment made **by** the target to somebody else remains history and blocks
deletion; the entire roles table is not exempt. No private preference or private
delegation table exists. `foundation_approval_delegations` and
`foundation_approval_records` are immutable business history and are never
deleted, including pending delegations. Notifications, activity/audit/security
events and every business module's records are never removed to enable deletion.

All self-owned rows, the user and a mandatory security event
`user.deleted_permanently` belong to one transaction. The event's actor is the
administrator; details are exactly email, full_name and reason. Audit insertion
failure cannot leave a deleted user without its security event.

## Verification

Backend regressions cover throttle and unchanged timestamps/version, real login
and two access requests, refresh without presence writes, online status, privacy,
each conflict, foreign organization, missing permission, cross-module creator
history, security actors, role-assignment actors, all four disposable tables,
mandatory auditing and rollback after IntegrityError. The route registry names
the foreign-user test as route-specific isolation evidence.

PostgreSQL 16 tests exercise actual Alembic upgrade/downgrade/re-upgrade plus a
disposable schema with an existing administrator and a custom role. Frontend
tests cover Arabic/English presence, eligibility/permissions, reason and email,
409 translations/deactivation handoff and visibility-aware polling. Final
command results and CI status are recorded in the PR.

## ملخص القرارات

أُعيد استخدام صلاحية الحذف الموجودة مسبقًا؛ الترحيل يضمن منحها الافتراضي
لمدير المنظمة ولا يمحو المنح المخصصة عند التراجع. تفويضات الاعتماد سجلات
أعمال وليست بيانات شخصية قابلة للمسح، ولذلك تمنع الحذف. أسماء الجداول
المانعة تُعاد كما هي، دون كشف محتواها. الجداول الذاتية الأربعة أعلاه فقط
قابلة للمسح، ولا تُحذف أي سجلات تاريخية لتمكين حذف المستخدم.
