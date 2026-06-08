# Foundation Module

**Status:** Sprint 1 — Complete

Provides organization identity, user accounts, roles/permissions, and JWT authentication. All other modules depend on Foundation for the `TenantContext`.

---

## Domain objects

### Organization
A tenant boundary. Every piece of business data is scoped to an organization.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| name | String(255) | |
| code | String(64) UNIQUE | Human-readable identifier (e.g. `dev-org`) |
| status | Enum `active/inactive` | |
| industry_type | String(120) nullable | |
| timezone | String(64) | Default `UTC` |

### User
A person who belongs to exactly one organization.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → organizations | |
| full_name | String(255) | |
| email | String(255) | Unique per org |
| password_hash | String(255) | bcrypt |
| status | Enum `active/inactive/suspended` | |
| last_login_at | DateTime nullable | |

### Role
Named role within an organization. Org-scoped.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK | |
| name | String(120) | |
| code | String(64) | Unique per org |

### Permission
A global (not org-scoped) permission code. Stored once, assigned to roles.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| code | String(120) UNIQUE | e.g. `commercial:customers:write` |
| module_name | String(80) | |
| action_name | String(80) | |

### RolePermission / UserRole
Junction tables linking roles to permissions and users to roles.

---

## Auth flow

1. `POST /api/v1/auth/login` — validates email + password, returns a signed JWT (`access_token`).
2. JWT payload: `{sub: user_id, organization_id, exp}`.
3. Every protected route calls `get_current_tenant()` which decodes the token, loads the user from DB, and builds a `TenantContext(user_id, organization_id, roles)`.
4. `TenantContext` is derived from the database on every request — not blindly trusted from the JWT (ADR-001).

---

## Notes and limitations

- **RBAC is stored but not enforced.** `app/core/permissions.py` is a stub. Roles and permissions are recorded in the database (the seed creates them) but no route currently checks `has_permission()`. Planned for a future sprint.
- Token expiry: 30 minutes (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`).
- `SECRET_KEY` must be changed before staging deployment.
