# PLATFORM-IDENTITY-001 Review

## A. Pre-review verification

| Verification | Result |
|---|---|
| V1 `python -c "import app.main"` | PASS |
| V2 full `pytest -q` | FAIL: 361 passed, 37 failed, 33 errors; failures are the existing Commercial/Production/Workforce baseline, but the repository is not green |
| V3 `test_platform_identity.py` | PASS: 7 grouped tests |
| V4 `test_organization_root.py` | PASS: 25 tests |
| V5 `test_credential_management.py` | File does not exist; actual replacement `test_root_credential_recovery.py` passed: 5 tests |
| V6 `test_module_boundaries.py` | PASS: 11 tests |
| V7 `test_tenant_isolation.py` | PASS: 10 tests |
| V8 `test_platform_isolation.py` | PASS: 11 tests |

V3-V8 actual files passed together: **76 passed, 2 warnings**.

## B. Checks 1-83

### Platform Account Model

1. PASS — `PlatformAccount.role` exists.
2. PASS — `PlatformAccountRole` defines `root` and `admin`.
3. **FAIL** — `is_root` remains a writable Boolean column; it is not computed from `role`.
4. PASS — migration `f6a1b2e2` exists and backfills from `is_root`.
5. PASS — migration supplies upgrade and downgrade.
6. PASS — existing `is_root=true` records are backfilled to `root`.

### Permission System

7. PASS — `platform/domain/permissions.py` exists.
8. PASS — every catalog value starts with `platform:`.
9. PASS — role-to-permission mapping exists.
10. PASS — Root bypass and full mapping cover all permissions.
11. PASS — Admin receives only the mapped subset.
12. PASS — unmapped permission returns 403 with `PLATFORM_PERMISSION_DENIED`.
13. PASS — `require_platform_permission` exists.
14. PASS — protected organization/administrator operations use the dependency; login/bootstrap are intentionally public/pre-initialization and self-service uses authenticated account ownership.
15. PASS — the typed enum prevents tenant permission values from satisfying the checker.

### Last Root Protection

16. **PARTIAL** — deletion is blocked, but the sole bootstrap Root returns `BOOTSTRAP_ROOT_PROTECTED` before `LAST_PLATFORM_ROOT`.
17. PASS — status update to inactive calls service-layer protection.
18. PASS — Root-to-Admin demotion calls service-layer protection.
19. PASS in service logic — another active Root makes deactivation/demotion possible; tests only demonstrate demotion, not every vector.
20. PASS — bootstrap Root deletion is always blocked.
21. PASS — protections live in `PlatformAccountService`.
22. **FAIL** — count query includes the target and compares `<= 1`; behavior works in normal state but does not meet the explicit exclude-target requirement.

### Platform Account CRUD

23. PASS — list endpoint exists.
24. PASS — detail endpoint exists.
25. PASS — create endpoint exists.
26. PASS — update endpoint exists.
27. PASS — DELETE performs JSON-returning soft deactivation.
28. PASS — Admin lacks create permission.
29. PASS — Admin lacks update/deactivate permissions.
30. **FAIL** — Admin mapping omits `ADMINISTRATORS_READ`, so Admin cannot view accounts.
31. PASS — duplicate platform email returns 409.
32. PASS — duplicate tenant email returns 409.
33. PASS — tenant lookup uses `UserCredentialInterface`.
34. PASS — response schemas contain no password hash.
35. PASS — CRUD and reset endpoints return JSON.

### Login and JWT

36. PASS — login queries the shared platform account table and supports either role.
37. PASS — JWT includes `role`.
38. PASS — JWT includes `token_version`.
39. PASS — platform JWT is rejected by tenant dependencies.
40. PASS — tenant JWT is rejected by platform dependencies.
41. PASS — inactive accounts cannot log in.
42. PASS — DB/token version mismatch returns 401.

### Password Management

43. PASS — authenticated platform self-service exists at both compatibility and requested paths.
44. PASS — wrong/missing current password returns 400.
45. PASS — service policy requires 12 characters.
46. PASS — self-service increments token version.
47. PASS — Root can reset without the old password.
48. PASS — Admin lacks administrator-update permission.

### Frontend

49. PASS — `/platform/administrators` exists.
50. **FAIL** — role is localized text but has no Root-indigo/Admin-blue badge.
51. **FAIL** — status is localized text but has no active-green/inactive-gray badge.
52. PASS — create form has name, email, role, password, and confirmation.
53. **FAIL** — there is no administrator edit form/detail workflow; only a role-toggle action. Bootstrap identity fields therefore are not represented as locked edit fields.
54. PASS — deactivate uses localized confirmation.
55. PARTIAL — backend errors are displayed, but there is no dedicated localized last-root state.
56. PARTIAL — reset dialog exists, but it is offered for Root targets as well as Admin targets.
57. PASS — administrator dashboard entry is Root-only.
58. **FAIL** — organization create/status controls are rendered for Admin even though backend permissions reject them; navigation/action visibility is not derived from `permissions`.

### Translations

59. PASS — Arabic keys exist.
60. PASS — English keys exist.
61. PASS — Arabic JSON is valid UTF-8.
62. PASS — i18n check confirmed aligned structures for all 15 locale pairs.
63. PARTIAL — Arabic grep in platform TSX is empty and new administrator copy uses `t()`, but the platform organizations component still has a hardcoded/mojibake em dash fallback.

### Isolation

64. PASS — platform accounts use a separate table and repository.
65. PASS — platform accounts cannot enter tenant sales-owner queries.
66. PASS — platform accounts cannot enter tenant assignee queries.
67. PASS — `PlatformAccount` has no `organization_id`.
68. PASS — no Foundation import exists under `app/platform`.
69. PASS — no Platform import exists under `app/foundation`.
70. PASS — cross-table lookup is provided through Core interface injection.

### Tests

71. PASS — test file exists.
72. **FAIL** — the file contains 7 grouped test functions, not explicit complete T01-T40 coverage.
73. PARTIAL — tested assertions are meaningful, but multiple required scenarios are absent.
74. PASS — allow and deny permission paths are asserted.
75. PARTIAL — delete/deactivate/demote blocking is asserted, but positive second-Root coverage is incomplete.
76. PASS — platform-table and tenant-table duplicate email cases are asserted.
77. PARTIAL — targeted prior-sprint suites pass; the full repository does not.
78. **FAIL** — full suite has 37 failures and 33 errors.

### Scope Control

79. PASS — no audit-log implementation added.
80. PASS — no MFA, SSO, or billing added.
81. PASS — tenant user-management behavior was not expanded by this task.
82. PASS — no Support role added.
83. PASS — organization lifecycle semantics were not expanded.

## C. Grep evidence

```text
permissions.py: 13 entries, all values begin with platform:
routes_platform_admin.py: permission dependencies on list/get/create/status/reset
routes_platform_administrators.py: permission dependencies on list/get/create/update/delete/reset
services.py: _protect_last_root called by demotion, deactivation update, and delete path
schemas.py password_hash scan: no matches
app/platform Foundation-import scan: no matches
app/foundation Platform-import scan: no matches
platform TSX Arabic-character scan: no matches
models.py: both is_root Boolean and role enum are present
test_credential_management.py exists: False
test_root_credential_recovery.py exists: True
```

## D. Permission assessment

The catalog is complete for the requested v0.1 scope and Root bypass is correct for consistent rows. Admin cannot escalate through APIs because it lacks administrator create/update/deactivate. However, duplicated `role`/`is_root` identity is an authorization invariant risk: dependencies deliberately treat `is_root=true` as Root even when `role=admin`. Admin also cannot perform the review-required read operation because `ADMINISTRATORS_READ` is missing from its mapping.

## E. Last Root assessment

Delete, deactivate, and demote paths call service protection. Bootstrap deletion has an additional independent guard. Normal behavior prevents loss of the final Root, but the query should explicitly count active Roots excluding the target and require at least one result. Duplicated role state should be removed so every path evaluates one authoritative role.

## F. Email uniqueness assessment

The interface boundary is correct and same-request checks work. The platform-table unique constraint handles concurrent platform/platform duplicates, but no database constraint can currently enforce platform/tenant cross-table uniqueness atomically. Two concurrent transactions targeting different tables can both pass the pre-check. A shared identity registry/reservation table or serialized advisory-lock strategy is required for strict global uniqueness.

## G. Issues by severity

### Critical

- None demonstrated through the public API.

### High

- Writable duplicated `is_root` and `role` can create authorization-state divergence.
- Required Admin read access is absent.
- Required T01-T40 regression coverage is incomplete.

### Medium

- Last-Root count does not explicitly exclude target.
- Cross-table uniqueness has a concurrency race.
- Frontend permission gating, edit workflow, badges, target-specific reset, and localized last-root handling are incomplete.
- Full repository suite remains red.

### Low

- Hardcoded/mojibake fallback remains in the organizations table.
- Review command references a non-existent credential test filename.

## H. Required fixes

1. Migrate away from the Boolean `is_root`; expose it as a computed/hybrid property derived only from `role`.
2. Add `ADMINISTRATORS_READ` to Admin mapping while retaining denial of mutations.
3. Rewrite last-Root query to exclude target explicitly and test all positive/negative delete, deactivate, and demote cases.
4. Add explicit, non-grouped T01-T40 tests including Admin self-service and UI-relevant authorization behavior.
5. Implement frontend account detail/edit, bootstrap field locking, role/status badges, permission-derived navigation/actions, and Admin-only reset targeting.
6. Replace hardcoded fallback text with translations.
7. Choose and document an atomic global-email reservation strategy.
8. Restore the full repository test baseline or formally separate and document pre-existing failures.

## I. Final verdict

**NEEDS REVISION.** Core backend identity and isolation are functional and targeted suites pass, but checks 3, 22, 30, 50-53, 58, 72, and 78 prevent approval.
