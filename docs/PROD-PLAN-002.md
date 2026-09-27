# PROD-PLAN-002

## Investigation (before implementation)

Database revision: `f6a1b2g4`. Read-only count on 2026-09-15:
`production_orders`: 0 rows; non-null commercial reference: 0; non-null shift reference: 0.

| Area | Current state | Change / risk |
|---|---|---|
| Order commercial reference | Nullable UUID, indexed, no FK; 0 populated | Remove model, schemas and UI reference; migration archives populated references on other databases |
| Order shift reference | Nullable FK, indexed; 0 populated | Remove header link and deletion dependency; preserve ShiftReport links |
| Creation | Manual payload, generated number from count, optional explicit number | Add atomic planning creation, locked numbering, snapshot and allocations |
| Quantity | Order Numeric(14,2), demand Numeric(15,3) | Widen order to Numeric(15,3); prevent allocated order quantity/spec/unit edits |
| Demand | Items, organization mutex, sequence; manual planned transitions | Derived allocation totals and automatic planning transitions |
| Execution | Many ShiftReports may reference one order; outputs, waste and downtime reference order | Preserve these relationships |
| Permissions | production:production_orders:read/write; planning:read/sequence | Add planning:allocate and orders:create |
| Backend files | production models, schemas, services, repositories, routes; permission catalog and migration | Tenant checks, decimal validation, transaction rollback and lock ordering |
| Frontend files | production-orders and production-demands features, translations | Selection, review, allocation detail, remove obsolete fields |
| Tests | SQLite suite, old header-reference expectations | Update superseded assertions; add allocation tests; PostgreSQL needed for real locking verification |

Existing workspace contains substantial unrelated uncommitted work; preserve it.
