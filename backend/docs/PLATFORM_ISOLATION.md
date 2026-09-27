# Platform Isolation — IORP v0.1

## Platform vs Tenant Architecture

```text
PlatformAccount + BootstrapState ── platform JWT ──► platform routes
                         │
                         └── core interfaces / composition root
                         │
Organization + User + operational data ─ tenant JWT ─► tenant routes
```

## Model Classification Matrix

| Model | Table | Module | Category | Has org_id | Scope/notes |
|---|---|---|---|---|---|
| PlatformAccount | system_platform_accounts | platform | PLATFORM | No | Platform identity |
| BootstrapState | system_bootstrap_state | platform | PLATFORM | No | Bootstrap metadata; documented FK to first organization |
| Organization | foundation_organizations | foundation | TENANT | Defines tenant | Tenant root entity |
| User | foundation_users | foundation | TENANT | Yes | Direct |
| Role | foundation_roles | foundation | TENANT | Yes | Direct |
| Permission | foundation_permissions | foundation | TENANT | No | Global tenant permission catalog; assignments scope through roles |
| RolePermission | foundation_role_permissions | foundation | TENANT | Indirect | Role → organization |
| UserRole | foundation_user_roles | foundation | TENANT | Indirect | User and Role → organization; service validates both |
| Customer | commercial_customers | commercial | TENANT | Yes | Direct |
| CustomerCodeCounter | commercial_customer_code_counters | commercial | TENANT | Yes | Direct |
| SampleCodeCounter | commercial_sample_code_counters | commercial | TENANT | Yes | Direct |
| QuoteCodeCounter | commercial_quote_code_counters | commercial | TENANT | Yes | Direct |
| OrderCodeCounter | commercial_order_code_counters | commercial | TENANT | Yes | Direct |
| Sample | commercial_samples | commercial | TENANT | Indirect | Customer → organization |
| SampleEvaluation | commercial_sample_evaluations | commercial | TENANT | Indirect | Sample → Customer → organization |
| Quote | commercial_quotes | commercial | TENANT | Yes | Direct |
| QuoteItem | commercial_quote_items | commercial | TENANT | Indirect | Quote → organization |
| CommercialOrder | commercial_orders | commercial | TENANT | Yes | Direct |
| CommercialOrderItem | commercial_order_items | commercial | TENANT | Indirect | Order → organization |
| CustomerInteraction | commercial_customer_interactions | commercial | TENANT | Indirect | Customer → organization |
| FollowUp | commercial_follow_ups | commercial | TENANT | Indirect | Customer → organization |
| WorkCenter | production_work_centers | production | TENANT | Yes | Direct |
| ShiftDefinition | production_shift_definitions | production | TENANT | Yes | Direct |
| ProductionOrder | production_orders | production | TENANT | Yes | Direct |
| ProductionOrderItem | production_order_items | production | TENANT | Indirect | ProductionOrder → organization |
| ShiftReport | production_shift_reports | production | TENANT | Yes | Direct |
| ProductionOutput | production_outputs | production | TENANT | Yes | Direct |
| DowntimeEvent | production_downtime_events | production | TENANT | Yes | Direct |
| WasteRecord | production_waste_records | production | TENANT | Yes | Direct |
| QualityCheck | quality_checks | quality | TENANT | Yes | Direct |
| QualityDefect | quality_defects | quality | TENANT | Yes | Direct |
| QualityRejection | quality_rejections | quality | TENANT | Yes | Direct |
| NonConformanceReport | non_conformance_reports | quality | TENANT | Yes | Direct |
| NonConformanceItem | non_conformance_items | quality | TENANT | Indirect | Report → organization |
| WorkforceMember | workforce_members | workforce | TENANT | Yes | Direct |
| WorkforceCodeCounter | workforce_code_counters | workforce | TENANT | Yes | Direct |
| Base | — | core | SHARED | No | SQLAlchemy metadata only |

## Repository Classification Matrix

| Repository | Methods | Category | Scoped by | Audit result |
|---|---|---|---|---|
| PlatformAccountRepository | get, get_by_email, add | PLATFORM | Platform account identity | Compliant |
| BootstrapRepository | get, get_for_update, add | PLATFORM | Singleton platform state | Compliant |
| Foundation repositories | organization, user, role, permission, mappings | TENANT | organization parameter or owning User/Role join | Public tenant flows use scoped methods; low-level `get`/`list_all` are composition/provisioning primitives |
| Commercial repositories | customer, interaction, follow-up, sample, quote, order and counters | TENANT | direct organization filter or owning-parent join | Compliant |
| Production repositories | all production aggregates | TENANT | direct organization filter or production-order parent | Compliant |
| Quality repositories | checks, defects, rejections, NCRs/items | TENANT | direct organization filter or NCR parent | Compliant |
| WorkforceRepository | member CRUD/linking/counter | TENANT | direct organization filter | Compliant |

## Service Classification Matrix

| Service | Category | Auth | Scope |
|---|---|---|---|
| BootstrapService | PLATFORM | Bootstrap token | Platform bootstrap + organization interface |
| PlatformAuthService | PLATFORM | Platform credentials | Platform account |
| PlatformOrganizationService | PLATFORM | get_current_platform_account | Explicit platform operation through core interface |
| FoundationService | TENANT | get_current_user | organization_id arguments from CurrentUserContext |
| CustomerService and commercial aggregate services | TENANT | tenant dependencies | TenantContext.organization_id |
| Production services | TENANT | tenant dependencies | TenantContext/organization_id |
| Quality services | TENANT | tenant dependencies | TenantContext/organization_id |
| WorkforceService | TENANT | tenant dependencies | TenantContext/organization_id |
| Dashboard service logic | TENANT | get_current_tenant | TenantContext.organization_id |

## Route Classification Matrix

| Route family | Category | Auth dependency | Permission namespace |
|---|---|---|---|
| `/api/v1/system/bootstrap/*` | PLATFORM | Bootstrap token/public status | None |
| `/api/v1/platform/login` | PLATFORM | Credentials | None |
| `/api/v1/platform/me`, `/change-password` | PLATFORM | get_current_platform_account | Platform identity |
| `/api/v1/platform/organizations/*` | PLATFORM | get_current_platform_account | Platform-only |
| `/api/v1/auth/*` | TENANT | Credentials/get_current_user | Tenant identity |
| `/api/v1/admin/users*` | TENANT | require_permission → get_current_user | foundation:users:* |
| `/api/v1/admin/roles*` | TENANT | require_permission → get_current_user | foundation:roles/user_roles/role_permissions:* |
| `/api/v1/admin/permissions` | TENANT | require_permission → get_current_user | foundation:permissions:read |
| `/api/v1/organizations/*` | TENANT | get_current_user | Authenticated organization |
| `/api/v1/commercial/*` | TENANT | require_permission/get_current_tenant | commercial:* |
| `/api/v1/production/*` | TENANT | require_permission/get_current_tenant | production:* |
| `/api/v1/quality/*` | TENANT | require_permission/get_current_tenant | quality:* |
| `/api/v1/workforce-members*` | TENANT | require_permission/get_current_tenant | workforce:* |
| `/api/v1/dashboard/*` | TENANT | get_current_tenant | Tenant read |

## Permission Classification

`PlatformPermission` contains only `platform:organizations:{read,create,update}`. The tenant catalog contains `foundation:*`, `commercial:*`, `production:*`, `quality:*`, and `workforce:*`. Static tests prohibit namespace mixing in route modules.

## Platform Root Protection Rules

Platform Root is stored separately, authenticated separately, excluded from Foundation queries, and cannot be assigned operational references. Last-root deactivation/deletion policies are reserved for platform account-management work; no such endpoint currently exists.

## What Platform Root Can Do

- Bootstrap the installation.
- Authenticate and change its password.
- List, create, inspect, and change lifecycle status of organizations.

## What Platform Root Cannot Do

- Act as a tenant user or access tenant routes.
- Appear in tenant user or eligibility lists.
- Be a sales owner, follow-up assignee, workforce member, operator, or inspector.
- Access tenant data without an explicit future platform feature and contract.

## Adding a Platform Feature

Add it under `platform`, use platform auth and `platform:*` permissions, communicate through `core/interfaces`, and add identity-crossing rejection tests.

## Adding a Tenant Feature

Follow [TENANCY_RULES.md](TENANCY_RULES.md), derive scope from `TenantContext`, validate parent ownership, and add cross-tenant tests.
