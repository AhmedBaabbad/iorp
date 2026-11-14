# USERS-UX-D: presence on details, deletion based on business impact

Base `2d565eedd5070511de83c9122182605af53ce807`, branch `fix/users-delete`.
This policy supersedes the activation restriction in USERS-UX-C. Authentication,
password usability, last login/seen and active/inactive/locked status no longer
decide deletion. Organization root, self and business history remain blockers.

## Presence and UI

Presence and permanent deletion are removed from the list, together with its
periodic poll. Details show presence
in the hero, a full localized last-seen timestamp and the existing last login.
The 60-second detail refresh calls the lightweight /presence endpoint and
merges only last_seen_at/is_online, stops while
hidden, resumes on visibility and clears on unmount; open dialogs and their
drafts remain intact. Server presence/window/throttle behavior is unchanged.

Details expose `delete_block` only to foundation:users:delete: null or a root,
self or history code with up to five stable translated type keys. The list
does not compute eligibility or return can_delete_permanently. Fast root/self checks precede metadata scans.
Current FK table types all have Arabic/English labels, verified by a test.
Details show history-blocked deletion disabled, its reason/types and the existing
deactivation handoff; root/self have no delete button. Confirmation, normalized
email comparison and 404 return-to-list behavior are retained.

## Tables deleted

| Table | Scope |
| --- | --- |
| foundation_users | The selected non-root, non-self user in the actor's tenant |
| foundation_user_roles | The user's own role bindings only |
| foundation_password_reset_tokens | Owned tokens in the same organization |
| foundation_user_email_changes | Owned pending email change in the same organization |
| core_auth_sessions | Tenant account sessions in the same organization only |
| notifications_items | The user's own recipient rows in the same organization |

The existing explicit self-owned tables are supplemented by metadata-discovered
CASCADE FKs to foundation_users.id with ownership columns user_id,
recipient_user_id, account_id or owner_user_id. CASCADE actor/creator columns
are never automatically treated as ownership. Cross-tenant malformed rows
remain blockers. The current inventory has no tenant MFA table; platform_mfa
belongs to platform accounts and is never touched.

## Tables detached, never deleted

Only `foundation_security_events.actor_id` is nulled for known own-account
events in the same organization. Existing actor_email is retained; missing
email is filled from the user before deletion. Other event data, occurrence
counts and timestamps are preserved. There is no actor_name column here.

Explicit self-event allowlist: tenant.login_success, tenant.login_failed,
tenant.token_refreshed, tenant.session_revoked,
tenant.refresh_token_reuse_detected, tenant.password_changed,
tenant.password_reset_via_email, tenant.auto_locked, tenant.auto_lock_expired.
The activation flow currently emits password_reset_via_email. sessions_ended
is personal only for ended_by_user/session_limit reasons. Explicit target IDs
of a different account, malformed details and unknown event types remain
blocking. No broad prefix-based exemption is used. There are no tenant MFA
events and no browsing-generated activity rows in the current application.

All foundation_audit_log actors (including self-service administration audits),
business creator/modifier/owner/approver references, role-assignment actors,
delegations and other activity/security events remain history. Administrative
actions against other users therefore block deletion. No business log is
removed or anonymized to enable deletion.

## Transaction, schema and verification

The target is locked FOR UPDATE; impact is rechecked before detachment/deletion.
Cleanup and mandatory user.deleted_permanently audit commit together. The audit
adds deleted_rows/detached_rows totals and deleted_by_table/detached_by_table
counts; deleted_rows includes the user itself. IntegrityError rolls back all
detachment and cleanup and returns USER_DELETE_HAS_HISTORY.

Security actor_id is already nullable and recipient notifications already use
ON DELETE CASCADE. Migration f6a1b2p2 adds the actor_id/event_type index for SQL
history checks. No presence model/schema behavior is changed. The PostgreSQL test proves real deletion with FK enforcement after
activation, login, multiple authenticated GETs, logout and an inbox notification;
security events remain with null actor_id and preserved email. Other tests cover
customer creation blocking, inactive accounts, administrative locks, root/self,
tenant isolation, permission-scoped delete_block, early guard performance,
translated types and rollback of detachment/notification deletion on audit error.
Frontend tests cover absence of list presence/polling, hero/details refresh,
dialog preservation, disabled reason/types and enabled/protected deletion.

## ملخص عربي

الحذف يعتمد على أثر العمل فقط، ولا تمنعه كلمة مرور صالحة أو حالة الحساب
أو تسجيل الدخول. الجداول الستة المذكورة أعلاه هي التي تُحذف صفوفها ضمن
النطاق المحدد. الفصل يخص actor_id لأحداث الحساب الشخصية المعروفة في
foundation_security_events فقط، مع حفظ البريد والبيانات التاريخية. لا
توجد جداول MFA للمستأجر ولا سجلات نشاط تنتج عن التصفح؛ ولا تُمس بيانات
المنصة أو سجلات التدقيق والأعمال. العمود المفصول يقبل NULL بالفعل، وأضيفت
migration f6a1b2p2 لفهرس فحص الأثر. الحذف من التفاصيل فقط وتحديث الحضور
بمسار خفيف مستقل. تُثبت نتائج الأوامر النهائية في وصف PR.
