# Independent review request — REFERENCE-DATA-001

Review the actual implementation of reusable operational records and frozen quotation terms. Do not rely on the implementer's report. Read ADR-009 and inspect code, migration, tests and UI. The workspace contains unrelated prior changes: do not revert or attribute all `git diff` changes to this task. Review only; do not modify code or real business data.

## Required checks

1. Shipping owns saved drivers, vehicles and carriers. Procurement consumes transport through the core interface, not Shipping ORM imports.
2. Internal/external affiliation is independent of saved/one-off mode. Internal saved drivers require a same-organization workforce record, not a login. External drivers reject employee links. One-off entries create no directory or user records.
3. New/replaced manual drivers require affiliation. Existing unknown classifications are explicitly labeled legacy in details and documents; no automatic external assumption.
4. Saved selection copies a snapshot; directory rename/deactivation and unrelated document edits do not change historical names, phones, addresses or attention fields. Full-form payloads cannot forge a selected record's snapshot. Switching or clearing selections works.
5. Customer contacts and sites belong to the correct customer and organization. Site contacts cannot point to another customer. Changing customers clears previous references without discarding newly supplied manual data.
6. Supplier contacts appear on supplier profiles and are selectable on purchase orders. Cross-supplier references reject. Supplier changes do not retain the old contact reference.
7. All endpoints reject unauthorized read/write operations; write scope is not widened by broader read scope. No hardcoded role authorization. Organization IDs and audit actors are not accepted from payloads.
8. Directory updates use row locks and version conflicts. Defaults are unique within their parent under concurrent writes. Duplicate vehicle/internal-employee records reject cleanly. Deactivation remains usable and history remains readable.
9. Issuing a quote captures bilingual terms atomically with the existing transition. Drafts read current settings; issued quotes do not. Empty snapshots stay empty. Revision preserves older snapshots. Quotes with issued history cannot be deleted.
10. `legacy_baseline` is visibly distinguished from genuine issuance snapshots. Missing snapshots never read today's settings. Confirm migration SQL matches this policy and preserves original rows.
11. New supporting lists (downtime/waste reasons, workforce skills, test methods) use Master Data as definition source. New values are validated after a list is configured; old text remains intact. Confirm the deliberate text-snapshot policy in ADR-009. No mass rewrite of historical operations.
12. Frontend supports Arabic/English and RTL, search, pagination, edit/deactivate, permission-based controls, and meaningful errors. Inspect shipment creation/edit/reschedule, receipts, customer profile, supplier profile, purchase order, reference lists and quotation preview/PDF.
13. Test actual status codes, persisted values, tenant isolation, stale versions, failed issuance rollback, and migration upgrade/downgrade. Do not substitute mocked happy paths for service tests.

## Main files

- `backend/app/shipping/{api/routes_directory.py,application/directory_service.py,infrastructure/directory_models.py}`
- `backend/app/core/interfaces/{transport_directory.py,customer_delivery.py,reference_lists.py}`
- `backend/app/core/contact_records.py`
- `backend/app/commercial/{api/routes_contacts.py,application/customer_delivery.py,infrastructure/contact_models.py}`
- `backend/app/procurement/{api/routes_contacts.py,infrastructure/contact_models.py,application/purchase_order_service.py,application/services.py}`
- `backend/app/shipping/application/shipment_service.py`
- `backend/app/commercial/{application/quote_terms.py,application/quote_service.py,infrastructure/quote_terms_models.py,reporting/quotation/builder.py,reporting/quotation/templates/quote_body.html}`
- `backend/app/masterdata/{domain/lists.py,api/schemas.py,application/catalog_provider.py}` and Production/Workforce/Quality consumers
- `backend/alembic/versions/2026_11_12_0900_f6a1b2o3_reference_directories.py`
- `frontend/src/features/reference-directory/`, `frontend/src/app/shipping-directory/page.tsx`, and the integrated feature forms/details
- `docs/adr/ADR-009-reusable-operational-records.md`

## Verification

Run from `backend`, with `DEBUG=false` and **`EMAIL_MODE=console`** (the developer's actual SMTP account is configured; never send test email):

```powershell
$env:DEBUG='false'
$env:EMAIL_MODE='console'
python -m pytest tests/shipping tests/procurement tests/commercial/test_quotation_document.py tests/commercial/test_quote_terms_snapshot.py tests/commercial/test_contact_directory.py tests/commercial/test_sales_order_lifecycle.py tests/masterdata tests/test_module_boundaries.py tests/test_all_route_authorization.py -q
python -m pytest tests/production/test_downtime_events.py tests/production/test_waste_records.py tests/workforce/test_workforce_members.py tests/quality/test_quality_specifications.py -q
$env:RUN_POSTGRES_TESTS='1'
python -m pytest tests/test_directory_migration_postgres.py -q
```

The migration test creates and removes a uniquely named disposable PostgreSQL schema. Do not downgrade the real populated project database.

From `frontend`:

```powershell
npx tsc --noEmit --incremental false
npx vitest run tests/components/reference-directory.test.tsx tests/components/shipments.test.tsx tests/components/procurement.test.tsx tests/components/master-data.test.tsx tests/components/downtime-events.test.tsx tests/components/waste-records.test.tsx --maxWorkers=1 --minWorkers=1
$env:NEXT_DIST_DIR='.next-reference-review'
npm run build
```

Report:

A. Checks performed with file/line references.
B. Critical / High / Medium / Low findings, each with a reproducible scenario and impact.
C. Required fixes per file.
D. Architecture drift and migration/data risks.
E. Actual test output and explicit verification gaps, including browser/PDF checks not performed.
F. Verdict: **Approved | Approved with non-blocking follow-ups | Needs Revision**.
