# PLATFORM-ARCH-001 — Audit and Verification Report

## Classification Matrices

The complete model, repository, service, route-family, and permission matrices are maintained in [PLATFORM_ISOLATION.md](PLATFORM_ISOLATION.md). Every SQLAlchemy business model is classified exactly once. Indirect tenant models document their ownership chain.

## Violations Found

| Finding | Severity | Status / recommendation |
|---|---|---|
| Tenant `User` has no `token_version`; tenant JWTs therefore cannot implement D4 stale-token invalidation | Medium | Follow-up requiring schema design and migration; prohibited by this task's no-schema-change constraint |
| `Permission` is a global tenant permission catalog without `organization_id` | Accepted | Assignments are organization-scoped through Role; codes are immutable catalog data |
| Low-level Foundation repository methods such as model `get` and permission `list_all` are not intrinsically tenant-scoped | Medium | Tenant-facing services use scoped wrappers; future repository-hardening task should split catalog/platform provisioning primitives from tenant query APIs |
| Bootstrap status and initialization do not use platform JWT | Accepted | Status is public and initialization is protected by the one-time bootstrap secret |
| Two Quality table names lack the `quality_` prefix | Existing, out of scope | Requires a migration, explicitly prohibited in this task |

No new database or endpoint change was made. No platform account query is joined or unioned with Foundation user enumeration.

## Guard Audit

| Cross-entity operation | Existing protection | Guard action |
|---|---|---|
| Customer → sales owner | `SalesOwnerEligibilityService.is_user_eligible(user_id, organization_id)` | Existing scoped check retained |
| FollowUp → customer | Customer repository lookup by authenticated organization | Existing scoped check retained |
| FollowUp → interaction | Interaction lookup through customer and organization | Existing scoped check retained |
| FollowUp → assignee | `FollowUpAssigneeEligibilityService` verifies Foundation user organization | Existing scoped check retained |
| User → Role assignment | Foundation service validates both organization IDs | Existing scoped check retained |
| WorkforceMember → User link | Foundation scoped lookup rejects foreign user | Existing scoped check retained |
| Workforce response enrichment → User | Previously loaded by raw ID | Added `validate_same_organization` before attaching user details |
| Production cross-references | Repositories resolve WorkCenter/Shift/Order within organization | Existing scoped checks retained |
| Quality cross-references | Repositories/services resolve owning aggregate within organization | Existing scoped checks retained |

## Schema Audit

An executable reflection test scans every class containing `Create` or `Update` in Foundation, Commercial, Production, Quality, and Workforce schema modules. It found two unused legacy schemas (`UserCreate` and `RoleCreate`); their `organization_id` fields were removed and their legacy service methods now require an explicit organization scope argument. No create/update schema now declares `organization_id`.

Fields named `organization_id` found by the source audit belong to response/read schemas such as `CustomerRead`, `UserDetailResponse`, production reads, quality reads, and `WorkforceMemberResponse`. They report ownership and do not accept scope input. Workforce create/update uses `extra="forbid"`; other services assign scope from authenticated context even if Pydantic ignores an unknown client field.

## Tenant User Enumeration Audit

| Endpoint | Query source | Platform excluded |
|---|---|---|
| `GET /api/v1/admin/users` | `foundation_users` scoped by organization | Yes |
| Eligible sales owners | `foundation_users` + tenant roles/permissions | Yes |
| Eligible follow-up assignees | `foundation_users` + tenant roles/permissions | Yes |
| `GET /api/v1/workforce-members` | `workforce_members` scoped by organization | Yes |

## Files Created or Modified

- `backend/app/core/tenancy.py`
- `backend/app/foundation/api/schemas.py`
- `backend/app/foundation/application/services.py`
- `backend/app/workforce/application/services.py`
- `backend/tests/test_tenant_isolation.py`
- `backend/tests/test_platform_isolation.py`
- `backend/tests/test_module_boundaries.py`
- `backend/docs/TENANCY_RULES.md`
- `backend/docs/PLATFORM_ISOLATION.md`
- `backend/docs/PLATFORM_ARCH_001_REPORT.md`

## Remaining Follow-ups

1. Add tenant `token_version` with a migration and validate it in `get_current_user`.
2. Split global permission-catalog repository APIs from organization-scoped role/assignment APIs.
3. Rename the two legacy NCR tables in a dedicated no-data-loss migration.
4. Add explicit platform permissions to organization routes when platform role management is introduced.

## Verification Results

- Focused boundary, tenancy, platform-isolation, authentication, and follow-up suite: `64 passed`.
- Full backend suite: `324 passed`, `37 failed`, `33 errors`, `2 warnings` in 271.20 seconds.
- The full-suite failures/errors reproduce the repository's existing Commercial, Production, and Workforce fixture/expectation gaps (principally missing permissions and generated-code expectations); none occur in the new isolation tests.
- Application import smoke test: `IMPORT_OK`.
- Static platform/foundation dependency scans: no forbidden import matches.
- `git diff --check`: no whitespace errors (line-ending conversion warnings only).
