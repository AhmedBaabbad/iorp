# USERS-OFFBOARD-E

Base: origin/main 0c2ce902dbac5a37f280c10718fcb2f7885ec0c3.
Branch: fix/users-offboarding. This supersedes the activated-account deletion
policy in USERS_UX_D.md and its performance correction; those documents are
historical. No migration or dependency changes are required.

## Deletion and offboarding

Permanent deletion cancels an invitation only. Guards run in order ROOT, SELF,
ACTIVATED, HAS_HISTORY. A usable password, last_login_at or last_seen_at blocks
deletion before any metadata/reference scan. Existing SQL history checks,
owned-row cleanup, personal-security detachment, locking and atomic mandatory
deletion auditing remain unchanged. List/presence performance stays unchanged.

Details show the permanent-delete action disabled with the server's translated
reason for root, self, activation or history. The eligible invitation button is
labelled "Delete permanently (cancel invitation)". History-blocked invitations
offer "Transfer ownership first" and navigation to offboarding.

The offboarding section is available only with foundation:users:deactivate,
for a known current user viewing another non-root user. It shows numbered
completed/current/locked steps:

1. Transfer customers and open follow-ups through the existing commercial APIs.
   Each category requires its existing transfer and read permissions, otherwise
   an explicit explanation replaces the controls. Candidates come from the
   existing eligibility endpoints. Impact is refreshed after each transfer,
   and the detail is reloaded once to refresh deletion eligibility. The employee
   link cannot be transferred here; the workforce query interface supplies the
   scoped member ID for a link to its existing record. Refresh impact after
   ending that link in HR.
2. Deactivate only when total_blocking_items is zero, with a required reason.
   Existing backend deactivation checks and session revocation remain in force.
3. Archive only after deactivation and clearing dependencies, with a reason.
   Archived accounts display archive time, the audit entry's actor-name snapshot
   and reason. Restore uses the existing activate permission and archive restore
   API; restoring the archive leaves the account inactive.

The existing hero, detail layout and shared form styles/tokens are reused. The
old parallel blocked-deactivation modal/transfer workflow is replaced by this
single section. The light presence timer does not reload impact or dialogs.

## User selection inventory

| Consumer / endpoint | Before | Correction |
| --- | --- | --- |
| HR account linking: /admin/users?selection=true | General admin list returned all statuses, UI filtered active only | Dedicated selection mode filters active and unarchived in SQL; UI and link validation also reject archived users |
| /commercial/customers/eligible-sales-owners | Active only | Explicit archive exclusion in options and target eligibility |
| /commercial/follow-ups/eligible-assignees | Active only | Explicit archive exclusion in options and target eligibility |
| /delegations/options (delegator and delegate) | Active only | Explicit archive exclusion; archived users also fail the existing usable/creation checks |
| /commercial/complaints/{id}/assignees | Active only | Explicit archive exclusion |
| /quality/non-conformance-reports/lookups/users (report/action owner) | All statuses | Active and unarchived only |
| Foundation directory (active users, permission holders, role recipients) | Active only | Explicit archive exclusion; historical names() remains unfiltered |

Administrative user listing still returns all accounts so its existing "Show
archived accounts" switch can work; archived rows remain hidden by default.
Historical name lookups, audit/security/business records and quote PDFs are
not changed. The reassignment algorithms and their existing module boundaries
are not changed; the UI calls each module's existing public API.

## Verification

Tests cover activation's early exit, empty invitation cancellation, customer
assignment blocking an invitation, selector exclusions (including legacy active
archived rows), preservation of historical names, transfer/deactivate/archive/
restore with surviving customer/follow-up records, disabled deletion reasons,
step locks, impact refresh, missing permissions, employee links and archive
display/restore. Final command results and CI links are recorded in the PR.

## ملخص عربي

الحذف النهائي لإلغاء دعوة حساب لم يُفعّل وليس له أثر عمل فقط. الحساب المفعّل
يبقى محفوظًا، ويمر بإنهاء الخدمة: نقل الملكية ثم التعطيل ثم الأرشفة. كل خطوة
توضح حالتها وسبب القفل، وتستخدم المسارات والصلاحيات الموجودة. الربط بالموظف
يُنهى من الموارد البشرية، وتبقى أسماء الحسابات في السجلات التاريخية. لا توجد
migration جديدة، ولا حذف لسجل تاريخي، ولا تغيير في PDF عرض السعر.
