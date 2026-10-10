# CUST-REPORT-001 — Customer reporting

## Customer samples extension (2026-10-06)

- `customers.customer_profile` now offers `samples`, `sample_properties`, and internal-only `sample_evaluations` sections. These describe Commercial customer samples, not Production output samples.
- `customers.samples_report` is a standalone, internal report in the existing report center. It reuses `reports:customers:customer_profile`, and additionally requires customer read, sample read, and internal-audience access. No new permission grants or database migration are needed. Evaluation sections additionally require `commercial:evaluations:read`.
- Filters: authorized customer, request-date range (organization timezone), product, current operational status, and independent sample decision. Null legacy decisions are treated as pending. The report prints applied filters. Evaluation history includes all evaluations of matching samples, even if evaluated after the request-date period.
- Sample count/status cards and requested quantities are grouped by stored unit; no mixed-unit sum or delivered-quantity claim. Cancelled samples remain included unless filtered out.
- Product/property/choice labels come from the Master Data interface. Legacy product names and nested values render readably without raw JSON. Customer copies omit sample notes and evaluation details. Internal evaluation history prints evaluator names through the existing tenant-scoped identity provider.
- Sample specifications use one row per sample: customer, sample number, and all labelled property values in a wrapping specifications cell. Customer/sample identity is not repeated for each property; heterogeneous product templates do not create sparse, ever-widening columns.
- Product lookups and report reads intersect the authorized customer set and organization. Queries and rendered rows retain the 5,000-row bound. Existing production, quotation, growth and fulfillment calculations are unchanged.
- Preview/PDF use the existing branding, renderer and shared report form; the UI discovers the new report and section controls from server definitions.

Changed files: `backend/app/commercial/reporting/customers/{definitions,schemas,builders,routes,sample_sections}.py`,
`frontend/src/i18n/locales/{ar,en}/reports.json`, `backend/tests/commercial/{test_customer_reports,test_customer_sample_reports}.py`,
`frontend/tests/components/customer-reports.test.tsx`, and this document.

Validation: customer report regressions and module boundaries, sample permissions/tenant/ownership filters, Master Data labels,
unit-separated totals, internal/customer privacy, actual Arabic/English PDF rendering, frontend preview/download filter submission,
TypeScript, ESLint and locale consistency. Synthetic PDF examples are in `backend/artifacts/customer-sample-reports/`.

## Scope and discovery

Customers are owned by the commercial module. Existing fields: one customer name, code,
sector, city/country, phone/email, operational status, relationship stage, sales owner,
notes and created/updated timestamps. Customer status and relationship stage remain independent.
Interactions and follow-ups exist. Separate contact/address entities, customer CR/VAT,
credit terms, price lists, attachments, status history and reactivation history do not exist.
They are not fabricated or added by this task. No financial statement, invoice or payment
calculation is implemented.

Development read-only counts at discovery: customers 3, follow-ups 2, interactions 0,
quotes 0, commercial orders 0, production demands 4/items 4, allocations 9,
production orders 2/items 6, result entries 0. No staging database was inspected.
PDF samples use isolated synthetic test data, not inserts into development customer records.

## Architecture and modified paths

- `backend/app/core/reporting/{contracts,service,routes}.py`: generic audience support,
  internal sections, extra section/parameter permissions, definition context, filename/reference
  prefixes, module-filtered audit history and definition-owned watermark.
- `backend/app/core/reporting/templates/base.html`: shared title band; customer audience
  shows the customer name and omits the generating user's name.
- `backend/app/production/reporting/definitions.py`: production watermark remains owned
  by the production definition. Existing report content is unchanged.
- `backend/app/core/interfaces/customer_reporting.py`: typed read DTOs and public protocols.
- `backend/app/commercial/application/report_queries.py`: read-only quotation DTOs using
  stored commercial totals. No pricing/VAT recalculation.
- `backend/app/production/application/customer_report_queries.py`: demands, allocations,
  linked orders and result DTOs; delegates result calculations to `OrderResultService`.
- `backend/app/foundation/application/report_identity_queries.py`: public timezone/user-name reads.
- `backend/app/commercial/reporting/customers/`: schemas, scoped queries, builders,
  definitions, module/provider composition seams, shortcut/lookups and body template.
- `backend/app/main.py`: provider composition and report/router registration.
- `backend/app/commercial/domain/report_permissions.py`: report permission labels and lists.
- `backend/app/foundation/domain/{permission_catalog,system_roles}.py`: catalog and explicit grants.
- `backend/app/core/authorization/scope_resolver.py`: optional fallback; existing callers
  retain their behavior, reports request OWN on missing grants and narrow TEAM to OWN.
- `backend/alembic/versions/2026_10_11_0900_f6a1b2i1_customer_reports.py`: permissions only.
- `frontend/src/features/reports/`: shared ReportCenter/ReportForm/API, customer dialog and permissions.
- `frontend/src/app/{customer-reports,production-reports}/page.tsx`: module composition pages.
- `frontend/src/features/customers/customer-detail-page.tsx`: report/statement buttons.
- `frontend/src/components/layout/page-frame.tsx`: permitted customer report menu link.
- `frontend/src/i18n/{messages.ts,locales/ar/reports.json,locales/en/reports.json}` and
  navigation locale files: shared report wording and Arabic/English labels.

No branding, renderer, fonts, image assets or export-audit tables were copied.
Builders do not import another module's ORM or repositories. Cross-module reads use public
providers assembled in `main.py`. There is no per-tenant module subscription model: the
approved interim capability hook treats composed modules as enabled. Deployments may replace
`providers.module_enabled`; disabled-module behavior is covered by tests.

## Catalog

| Key (`customers.` prefix) | Implemented | Unavailable portions |
|---|---|---|
| customer_profile | Information, contact fields, quote/demand/order summaries, results, internal notes/interactions/follow-ups, last activity | Separate addresses/contacts, credit/payment terms, attachments |
| directory | Customer/status/sector/city/owner/date filters, active-order filter, grouping, sorting, contact phone and optional last activity | Region and richer primary-contact records |
| activity_summary | Per-customer quotation and demand metrics; top N per currency/UoM; SVG bars; order counts and latest activity | Historical quote decision timing |
| quotations_report | Issue-date/status/customer/owner filters; values by status and currency; conversion | No invented pricing, decision-history or lost reasons |
| demand_fulfillment | Demanded/active-allocated/unallocated quantity, linked orders and order-level results | Actual demand settlement and delivery proof |
| growth_retention | New customers by month/quarter; inactivity threshold | Historical status transitions/reactivation: no source history |
| customer_statement | Open operational demand/order data and recently completed orders/results | Financial statement: no invoice/payment source |

Cross-module sections require the owning module to be composed/enabled, the necessary
read permissions and data. Last-activity/inactivity outputs explicitly refer to quotation,
production-demand and production-order activity; they do not claim to include unrecorded
shipping or financial events. Empty scoped datasets produce an empty report, not fabricated rows.

## Audience and access

`internal` requires `reports:customers:internal_audience`. The profile, fulfillment and
statement support `customer`; the remaining reports are internal only. Customer audience
requires a single customer. Definitions return only permitted audiences. The server strips
`internal_only` notes, interaction details and loss/sample/rework sections even if explicitly
requested. Filtering occurs before building output. Public result DTOs structurally contain
only order ID, unit, customer-good and stock-good quantities; internal result DTOs add losses.

Every report also requires `commercial:customers:read`. Customer selection and lookups use
tenant and effective customer ownership scope; OWN excludes unassigned and other-owner rows.
TEAM is conservatively narrowed to OWN until team membership is supported. Missing scope
grants fall back to OWN for reports, without changing existing screens. Quote/order access
is intersected with these authorized customer IDs. Read APIs remain tenant-scoped.

Additional sections require `commercial:quotes:read`, `commercial:interactions:read`, `commercial:follow_ups:read`, or
the production permission constants for demands/orders/results. Interactions also respect
their own created-by scope; follow-ups respect assignee scope. Active-order filtering requires demand/order read independently
of section visibility. Name/notes output uses template autoescaping; previews use a sandboxed
iframe. Existing Chromium JS/network restrictions, timeouts and font assets are reused.

Permission codes are `reports:customers:{customer_profile,directory,activity_summary,
quotations_report,demand_fulfillment,growth_retention,customer_statement,internal_audience}`.
Commercial manager receives the explicit list and existing export-history read permission.
Sales rep receives profile, statement, fulfillment and internal audience, retaining existing
customer ownership/data permissions (no new access to quotation or production results).
Organization admin includes the catalog through its existing administration policy.
Custom role grants are preserved.

## Formulas and date semantics

- Conversion: accepted / (accepted + rejected + expired) × 100; 0 when denominator is 0.
  These are current statuses of quotations issued in the period, not a historical status snapshot.
- Quote totals use stored `total_amount`; aggregate independently per currency.
- Demand allocated quantity uses the owning model's active-allocation property;
  unallocated = demanded − active allocated. Released allocations do not reserve quantity.
- Order result summaries use the existing signed correction-aware summary service.
- A single-customer order displays its result. A shared order displays customer allocation,
  total allocation and a shared-order label; produced quantities are never split proportionally.
  No result quantity is labelled delivered.
- Quantities and rankings stay separate by UoM; monetary rankings stay separate by currency.
- Profile/activity order periods use order creation dates; fulfillment periods use demand request dates.
- Inactivity: no quotation, production demand or linked production order dated within the last
  N days (default 90); customers created within that window are excluded. Future-dated events
  do not count as completed activity.
- Recently completed statement orders use actual completion time and `recent_days` (default 90).
- Date comparisons and formatting use organization timezone; date-only values remain dates.
- Read sets and rendered tables are bounded at 5,000; excessive data returns
  `REPORT_ROW_LIMIT_NARROW_FILTERS`. Related-source limits also apply before presentation filtering.

## API and UI

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/reports/definitions?module=customers` | Allowed reports/audiences/sections; optional customer_id/audience context |
| POST | `/api/v1/reports/customers.{key}/preview` | Same HTML/layout used by PDF |
| POST | `/api/v1/reports/customers.{key}/pdf` | Branded PDF |
| GET | `/api/v1/customers/{id}/report.pdf` | Profile shortcut with sections/lang/audience |
| GET | `/api/v1/reports/customers/lookups/{customers,sales_owners,products}` | Scoped, permission-checked lookups |

Export module is derived from the registered report key; no duplicate audit store is introduced.
Reports carry no reference number (see reporting.md, "Nothing is stored"). Download names contain report key, customer code
or reference, and timestamp; responses have ASCII fallback and RFC 5987 filename headers.
Failures are written to the server log; nothing is stored per generation.

The shared report center is parameterized by module and title; shared forms no longer contain
production order IDs/report keys. Customer detail offers profile and statement dialogs. The
native dialog supports focus containment and Escape. Menus/buttons are permission-aware;
the direct report-center route uses the existing no-access gate. Audiences/sections come from
the server. Existing production page composes the same shared center.

## Migration and validation

Migration `f6a1b2i1` follows `f6a1b2i0`, adds permission catalog entries and explicit system-role
grants. Added grant IDs are recorded; downgrade removes only those grants, retaining audit,
customer data and administrator-created grants. No business table schema is changed.

Tests and output: `backend/cust-report-001-tests.log`; test sources:
`backend/tests/commercial/test_customer_reports.py`,
`backend/tests/test_customer_reporting_migration_postgres.py`,
`frontend/tests/components/customer-reports.test.tsx`, and existing production/report tests.
The production layout regression compares generated internal HTML against the pre-extension
base layout for both languages and both watermark states, not just a successful status code.

Commands (PowerShell; set DEBUG=false in this environment):

```powershell
$env:DEBUG='false'
$env:RUN_RENDERER_TESTS='1'
$env:RUN_POSTGRES_TESTS='1'
python -m pytest tests/commercial/test_customer_reports.py tests/test_customer_reporting_migration_postgres.py tests/production/test_production_reports.py tests/production/test_production_rbac.py tests/test_permission_scopes.py -q
```

Frontend: `node node_modules/vitest/vitest.mjs run tests/components/reports.test.tsx tests/components/customer-reports.test.tsx`,
`node node_modules/typescript/bin/tsc --noEmit`, `node scripts/check-i18n.mjs`.

Real synthetic samples: `backend/artifacts/customer-reports/{C1-internal,C1-customer,C2,C3,C5,C7}.pdf`
with matching HTML and first-page PNG previews. Sample generation is opt-in with
`RUN_RENDERER_TESTS=1`; it uses the actual renderer and checks PDF signature, Arabic extraction,
filename headers, references and absence of internal notes in customer copies.

### Actual verification results — 2026-10-01

| Check | Result / evidence |
|---|---|
| Combined customer/production/RBAC/scope/PostgreSQL/PDF suite | `110 passed, 2 skipped in 166.53s`; `backend/cust-report-001-tests.log` |
| Final customer suite after last privacy/layout changes | `22 passed in 24.08s`; `backend/cust-report-001-final-tests.log` |
| Frontend report and customer-report tests | `2 files, 9 passed`; last run 4.18s |
| TypeScript | `tsc --noEmit`, exit 0 |
| AR/EN | `27 Arabic/English JSON file pairs are valid and aligned` |
| Targeted ESLint | Report files clean after correcting the reserved `module` local variable |
| Next production build | Exit 0; customer report route included; existing unrelated lint/CSS warnings remain in `frontend/cust-report-001-build.log` |
| Real PDF samples | Seven actual PDFs, including extra `C1-customer-en.pdf`; Arabic extraction and headers checked |
| Visual review | Profile customer, ranking, and statement page PNGs reviewed; RTL chart-label clipping and narrow order columns corrected |
| Development migration | `f6a1b2i0 → f6a1b2i1`; 24 permission rows across organizations, 63 recorded added grants; `backend/cust-report-001-migration.log` |
| Business record preservation | Customers/orders/result entries remained `[3, 2, 0]` before and after migration |

The two skips in the combined run are pre-existing production renderer/sample opt-ins using
different environment variable names. Customer PDF integration ran with real Chromium, and
the final customer run has no skips. Counts above are separate runs, not an additive total.
Migration upgrade/downgrade was exercised in an isolated PostgreSQL schema before applying
the development upgrade. Browser UI behavior was verified through component tests and the
production build; no interactive end-to-end browser session is claimed.

## Follow-ups outside scope

Tenant module subscriptions; actual demand settlement/delivery; financial statements;
customer status-event history; independent contact/address/terms/attachment models.
The existing commercial screen scope inconsistencies are not silently reproduced in reports.

## Review fixes (CUST-REPORT-001 review)

- **Customer audience omits:**
  - The internal customer status.
  - Draft quotations.
  - The conversion rate and its formula.
  - Stock good.
  - An order's total allocation.
  - The order-level output of shared orders, shown as "not shown for a shared order".

  The customer sees only its own allocation, so other customers' quantities cannot be inferred. Internal reports are unchanged.
- **Report listing reads no report data when no customer is chosen**, so a large organization never fails the listing. Row limits now come from read APIs as `ReportLimitError` (no HTTP in application code). The reporting service answers 422 `REPORT_ROW_LIMIT_NARROW_FILTERS` and records the failure.
- **Order results for many orders use one batch read**: `OrderResultService.unit_totals`, the same signed summary as before.
- **Export history removed.** The export history screen, `GET /reports/exports` and `reports:exports:read` were removed (migration `f6a1b2i2`). Each report prints who prepared it, when, and its reference. The `report_exports` audit table still numbers references and records failures.
- **Header** shows CR and VAT only when they are set. Customer bars use the branding colour. English statuses are readable.

