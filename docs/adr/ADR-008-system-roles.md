# ADR-008: The system roles — one manager per module, executing roles, an overseeing factory manager (RBAC-003)

## Context

Fourteen system roles had grown with the factory's departments rather than with the system's modules: maintenance,
safety, finance and human resources had no module of their own; the warehouse and shipping roles overlapped; the factory
manager held production and quality entirely; every role was a manager, so whoever recorded a shift or an inspection
could also release, close or cancel; the shipping manager could edit sales orders; the viewer read the audit and
security logs, users and roles.

## Decision

Eleven system roles (`backend/app/foundation/domain/system_roles.py`):

| Role | Holds |
|---|---|
| Organization administrator 🔒 | everything; never changes |
| Commercial manager | the commercial module, customer reports, deciding returns, products and reference lists |
| Sales representative | their own customers (scope "own"): customers, interactions, follow-ups, quotations, samples, draft sales orders |
| Production manager | the production module, production reports, the workforce (crews), reading sales orders |
| Production supervisor | the shift: runs, results, downtime, scrap; no planning, release, closing or cancelling |
| Quality manager | the quality module, quality reports, approving suppliers, materials' inspection requirement |
| Quality inspector | inspections: checks, measurements, defects, recording rejections, opening NCRs; no decisions |
| Procurement manager | the procurement module, goods receipts included |
| Shipping manager | the shipping module (preparing, dispatching, delivering, closing, returns) |
| Factory manager | reads every operational module and takes the major decisions (releasing, holding, closing and cancelling production orders, rejection decisions, verifying NCRs, specifications, certificates, returns, purchase orders, suppliers) |
| Viewer | reads the business modules and their reports; never the administration |

- The VAT rate and default currency (`masterdata:settings:update`) belong to the administrator, who may give that
  permission to another role from the roles screen.
- Warehouse, maintenance, safety, finance and human resources are made as custom roles when a factory needs them.
- `tests/test_system_roles.py` holds each role to this list.

Migration `f6a1b2k9` applies it to every organization: each system role's permissions become exactly its list, the two
executing roles are added, the five retired roles are removed; one still assigned to a user becomes the organization's
own (custom) role with its permissions. The administrator's role and the organization's own roles are never touched.
Every change is recorded; the downgrade restores the previous state exactly.
