# Sprint 1 — Status

**Completed:** 2026-06-08

---

## Scope delivered

Sprint 1 is a complete vertical slice from database to UI covering the commercial CRM baseline.

### Foundation

| Item | Status |
|------|--------|
| Organization model + migration | ✓ Done |
| User model + migration | ✓ Done |
| Role + Permission models + migration | ✓ Done |
| JWT login (`POST /auth/login`) | ✓ Done |
| Current user endpoint (`GET /auth/me`) | ✓ Done |
| TenantContext (`user_id`, `organization_id`, `roles`) derived from DB on every request | ✓ Done |
| Password hashing (bcrypt) | ✓ Done |
| Dev seed: org, 2 users, roles, permissions | ✓ Done |

### Commercial

| Item | Status |
|------|--------|
| Customer model + migration | ✓ Done |
| Customer CRUD API (create, read, list, update) | ✓ Done |
| Assigned sales user org-membership validation | ✓ Done |
| CustomerInteraction model + migration | ✓ Done |
| Interaction create + list API | ✓ Done |
| FollowUp model + migration | ✓ Done |
| Follow-up create + list (customer-scoped + org-wide) API | ✓ Done |
| Follow-up complete API | ✓ Done |
| Org-scoped tenant isolation on all commercial routes | ✓ Done |

### Frontend

| Item | Status |
|------|--------|
| Login page (auth feature, `LoginPage` component) | ✓ Done |
| JWT token bootstrap on page load (`refreshCurrentUser`) | ✓ Done |
| `ProtectedRoute` — redirects unauthenticated users to `/login` | ✓ Done |
| Logout (sign-out button in `PageFrame`, clears token) | ✓ Done |
| Root redirect (`/` → `/customers`) | ✓ Done |
| Customers list page (table with Stage/Priority/Status badges) | ✓ Done |
| Customer create page | ✓ Done |
| Customer detail page (shell + interactions + follow-ups sections) | ✓ Done |
| Interactions section (create + list + next_step_hint display) | ✓ Done |
| Follow-ups section (create + list + complete + assigned-to display) | ✓ Done |

### Review and stabilization (REV-005 through REV-010)

| Review | Outcome |
|--------|---------|
| REV-005 Backend consistency | Fixed: `FollowUpListItem` consolidation, `assigned_sales_user_id` org validation, follow-up router prefix split |
| REV-006 Frontend structure | Fixed: `optionalText`/`toDatetimeLocalValue` centralized in `lib/utils.ts`, `LoginPage` extracted to feature |
| REV-007 Frontend UX cleanup | Done: disabled-during-submit, required markers, retry buttons, Stage/Priority columns, `next_step_hint` display |
| REV-008 End-to-end flow validation | Conditional pass. Fixed: root page 404, no logout button, login-while-authenticated redirect |
| REV-009 Seed and test readiness | Done: enhanced seed, 12 backend tests (auth + customers + tenant isolation), SQLite in-memory |
| REV-010 Documentation sync | This document |

---

## Known deferred items (not blocking Sprint 2)

| Item | Reason deferred |
|------|----------------|
| Edit customer UI | ADR-003 scope freeze — update API exists, no UI |
| 401 mid-session interceptor | Token lasts 30 min; page refresh re-authenticates. Address in Sprint 2. |
| RBAC enforcement | `app/core/permissions.py` is a stub. Roles stored, not enforced. Planned. |
| `FollowUpListItem` type rename to `FollowUpRead` | Cosmetic frontend naming mismatch. No runtime impact. |

---

## Sprint 2 — Recommended next work

**Commercial Slice 2** — Samples, evaluations, and quotes.

Proposed domain objects:
- `commercial_samples` — physical samples sent to customers
- `commercial_sample_evaluations` — customer feedback on samples
- `commercial_quotes` — formal quote documents linked to customers

Agreed sequence after that: `commercial_orders` (Slice 3), then Production and Quality modules.
