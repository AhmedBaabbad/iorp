# REFERENCE-DATA-001 — Implementation record

Completed implementation and final automated checks: 2026-10-14 (Asia/Riyadh).

## Delivered scope

- Shipping transport directory: internal/external drivers, independent vehicles, optional carriers, search and pagination, versioned edit/deactivate, separate read/write permissions.
- One-off driver entry remains available in shipments and goods receipts; no implicit directory entry or login creation.
- Customer contacts and delivery sites on customer profiles; selected on shipment forms with saved snapshots.
- Supplier contacts on supplier profiles; selected on purchase orders with a saved attention name.
- Bilingual quotation terms frozen per issued revision; draft behavior retained; legacy migration baselines clearly marked on documents.
- Master Data lists for downtime reasons, waste reasons, workforce skills and test methods; selection and backend validation in their consumers, preserving historical text.
- Architecture decision: `docs/adr/ADR-009-reusable-operational-records.md`.
- Independent review instructions: `docs/reviews/REFERENCE-DATA-001-REVIEW.md`.

## Files by responsibility

Backend models: Shipping `directory_models.py`, Commercial and Procurement `contact_models.py`, Commercial `quote_terms_models.py`; corresponding owner `models.py` imports and transaction columns.

Backend APIs/services: Shipping `routes_directory.py`, `directory_service.py`, `shipment_service.py`, `schemas.py`, `permissions.py`; Commercial `routes_contacts.py`, `customer_delivery.py`, `quote_terms.py`, `quote_service.py`; Procurement `routes_contacts.py`, `purchase_order_service.py`, `services.py`, `schemas.py`; shared `core/contact_records.py` and the three core interfaces listed in ADR-009; provider/router registration in `main.py`, permission label registration in Foundation.

Supporting lists: Master Data `domain/lists.py`, `api/schemas.py`, `application/catalog_provider.py`; Production `downtime_service.py` and `waste_service.py`; Workforce `services.py`; Quality `specification_service.py`.

Reports: quotation builder/template, Shipping delivery-note document, Procurement receipt document.

Frontend: `features/reference-directory/{DirectorySelect,DirectoryPanel,ReferenceTextSelect}.tsx`, `/shipping-directory/page.tsx`, navigation; customer detail, supplier detail, shipment form/detail/list/reschedule, goods receipts, purchase orders; Master Data types/list page; downtime/waste/workforce/specification forms; affected bilingual labels and feature types.

New behavioral tests: `test_transport_directory.py`, `test_quote_terms_snapshot.py`, `test_contact_directory.py`, `test_supplier_contacts.py`, `test_operational_reference_text.py`, `test_directory_migration_postgres.py`, and `reference-directory.test.tsx`. Existing shipping/receipt test inputs explicitly state the newly required driver affiliation.

## Migration and existing data

`f6a1b2o3` was applied locally from `f6a1b2o2`. Counts checked before/after and unchanged: 13 customers, 12 quotations, 1 supplier, 1 receipt, 3 shipments. Six non-draft quotations received marked `legacy_baseline` snapshots. These are not claimed to be their original issued terms.

Existing contacts/transport text is retained, not merged by matching names. No user accounts were created. Existing custom role grants were not silently expanded; administrators can assign the directory permissions.

Downgrade refuses to discard populated directory/history/reference fields. Fresh isolated upgrade/downgrade and baseline behavior were exercised in PostgreSQL.

## Verification recorded

- Regression suite: **505 passed, 5 skipped**, `backend/reference-directory-regression.log`.
- Final new focused suite including PostgreSQL migration, failed-approval rollback and issued-history deletion protection: **18 passed**, `backend/reference-directory-new-tests.log`.
- Operational consumers: **82 passed, 1 skipped**, `backend/reference-directory-operational-tests.log`.
- UI components: **58 passed**, `frontend/reference-directory-ui.log`.
- Final TypeScript check passed (`frontend/reference-directory-types.log`, exit 0).
- Production build passed in `.next-reference-qa` (`frontend/reference-directory-build.log`), including `/shipping-directory`. Lint/cache warnings are retained in the log. Normal development `next-env.d.ts` and `tsconfig.json` were restored after the isolated build.
- Arabic/English translation check passed: **32 aligned JSON file pairs**.
- Final shipment/directory component rerun: **20 passed**, `frontend/reference-directory-final-ui.log`.
- Final contact/shipment backend rerun: **22 passed, 1 skipped**, `backend/reference-directory-contact-final.log`.
- SMTP delivery was disabled in all backend test runs (`EMAIL_MODE=console`).

These suites overlap; their counts must not be added as a unique-test total. Optional skipped checks are not claimed as passing.

## Verification limits

The integrated browser execution tool was unavailable in this session. Interactive browser/visual RTL inspection is **NOT VERIFIED**, despite passing component tests. No claim of full PDF visual comparison is made. Full quotation-revision archival beyond terms, and automatic deduplication/migration of ambiguous historical people/vehicles, are outside this change.

An intermediate final-check run (`backend/reference-directory-final-tests.log`) found a contact auto-selection regression: omitted contact and explicit manual selection were treated alike. That run had 33 passes and one failure. The defect was fixed by preserving explicitly supplied fields on shipment creation and distinguishing an omitted contact from explicit null. Both final suites above were then green, including the default-contact and manual-contact cases. The intermediate log is retained as evidence rather than represented as a passing run.

No unfinished implementation item remains within the delivered scope. Browser/visual inspection remains a verification gap, not a claimed passing check.
