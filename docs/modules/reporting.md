# Reporting and branded PDF export (PROD-REPORT-001)

## Layers
- **`app/core/reporting`** is the shared reporting core: contracts, registry, layout, renderer adapter, service, routes, export audit and assets.
  - It imports no business module, foundation included. A test enforces this (`test_reporting_core_imports_no_business_module`).
  - Organization rows are read through the shared metadata.
  - Company identity comes through `core/reporting/providers.branding_provider`, which the composition root (`app/main.py`) sets to `BrandingService.get_branding`.
- **`app/foundation`** owns company identity: `OrganizationBranding`, `StoredAsset`, `BrandingService` and `/organization/branding`.
  - `BrandingService` is the only writer of identity and logos.
  - The logo's source of truth is the stored asset. `organization.logo_path` is a mirror kept in step for existing consumers.
- **`app/production/reporting`** registers the production reports through the registry contract and builds their data read-only.
  - Other modules' tables (users, organizations, customers, workforce members) are read through `Base.metadata.tables`, never by importing their models. A test enforces this.
  - The order report's result comes from `OrderResultService`. The summaries reuse `result_rules.summarize`, so no formula is re-implemented.

## Assets
`app/core/reporting/assets` holds the bundled Noto fonts and the default logo (`defaults/logo-placeholder.png`).
- Code reaches them through `app.core.reporting.assets`, never by building paths.
- The fonts are embedded in each report, so there is no CDN or Google Fonts at render time. The folder is also mounted into the renderer as system fallback fonts.

## Renderer
Gotenberg 8 (headless Chromium) sits behind the `PdfRenderer` adapter. Chromium was chosen for correct Arabic shaping, RTL, repeating table headers and page X of Y.
- It runs on an internal Docker network, reached only through the nginx gateway.
- JavaScript is disabled, public and private IPs are denied, and downloads and webhooks are disabled.
- Concurrency is 2, the queue holds 4, and the API timeout is 60 s.

Report data queries run under a 30 s PostgreSQL statement timeout. A timeout returns `504 REPORT_TIMEOUT_NARROW_FILTERS`. More than 5,000 rows returns `422 REPORT_ROW_LIMIT_NARROW_FILTERS`.

## Reports
| Key | Report | Status |
|---|---|---|
| `production.order_full` | R1 production order report: information, items, allocations, history, execution, team, downtime (cause and planned or availability loss), waste (type), final result (completed and closed orders), notes and signatures. Watermark until the order is closed. | implemented |
| `production.orders_summary` | R2 orders summary: filters, grouping, totals per unit | implemented |
| `production.results_analysis` | R3 results analysis: per period, scrap and sample reasons, loss trend | implemented |
| `production.shift_workforce` | Shift rosters and recorded participation, offered only when rosters exist | implemented |
| R5, R6 | the remaining reports of the specification | **not implemented**: their data does not exist yet |
| `quality.check_full` | Q1 quality check report: inspection information (order, line and readable specification, or sample), quantities as figures, defects, rejections and dispositions, status history, notes and signatures. Watermark until the check is closed; a cancelled check is marked. | implemented |
| `quality.checks_summary` | Q2 checks summary: key figures, checks (optionally grouped), totals per unit (acceptance and rejection %, closed checks only), results distribution | implemented |
| `quality.rejections_analysis` | Q3 rejections and dispositions: per unit by outcome, reasons, dispositions, cases without a final decision with their age, quantity trend | implemented |
| `quality.defects_analysis` | Q4 defects: Pareto by defective units with cumulative %, category × severity, major and critical defects | implemented |

R1 also shows the order's quality checks and rejections (sections `quality_checks` and `quality_rejections`) to users who may read them;
production reads quality's tables through the shared metadata.

Text in the reports follows the report language. The terms match the application: «الهالك» and «نسبة الهالك» for loss, «نسبة الجيد» for yield. Values are wrapped in `<bdi>`, so dates, codes and numbers keep their direction in Arabic. The download file name is in the report language.

## Frontend
- The report center (`/production-reports`) and the order report dialog build their forms from `GET /reports/definitions`.
- Every label and message comes from the locale files:
  - `production.reports.*`;
  - `organization.branding.*` for the identity editor.
- PDF and preview requests go through `apiClient`, using `raw: true`, so session refresh works. Previews render in a sandboxed iframe.

## Tests
- `backend/tests/production/test_production_reports.py` has 24 test functions (32 cases with parametrization).
  - Two need the renderer, and are skipped otherwise:
    - `REPORT_RENDERER_TESTS=1` runs a real Arabic PDF and checks the header, footer, reference and page numbers on every page.
    - `REPORT_SAMPLES_DIR=<folder>` writes the review samples: R1 in progress, R1 closed (Arabic and English), R2 and R3.
- `backend/tests/test_reporting_migration_postgres.py` covers the migration.
- `backend/tests/quality/test_quality_reports.py` covers the quality reports; `REPORT_SAMPLES_DIR` writes Q1–Q4 samples.
- `frontend/tests/components/reports.test.tsx` covers the report form and the branding editor.

## Layout

Every module's report uses the same layout: `core/reporting/templates/base.html`, `sections.html` and `assets/print.css`. A module's body template only includes `sections.html`.

- **Document head.** The title and subject (for example the order number) sit on one side. A labelled details panel sits on the other: Issued, and Prepared by for internal reports. For customer reports the panel shows Prepared for, and the author is never named. An interim report also shows a flag next to the title.
- **Report scope.** The applied filters appear on one labelled line, only when filters were applied.
- **Sections.** Each section is numbered.
  - `TableSection.layout = 'fields'` shows (label, value) rows as a two-column information panel; it is used for order information and for a single customer's details.
  - Tables repeat their header row on each page, never split a row, and show numbers with fixed-width digits.
  - Key figures appear as cards.
  - Bars are scaled to the section's largest value.
- **Brand colour.** The company identity colour (`primary_color`) drives the accents.
- **Text and fonts.** Latin text and digits use Noto Sans, and Arabic falls back to Noto Naskh Arabic, so codes like `PO-2026-000001` keep one weight.
- **Page header and footer.** These are the corporate document identity; see the section below.
- **End mark.** The report ends with "— نهاية التقرير —".

## Nothing is stored

A report is built from current data on each request, returned to the browser and forgotten. No file, no audit row and no reference counter is saved.

- **What the file carries:** when it was issued and, on internal reports, who prepared it. Customer reports show Prepared for instead.
- **Failures:** they go to the server log (`app.core.reporting.service`).
- **Removed tables:** migration `f6a1b2i4` removed `report_exports` and `report_counters`. Its downgrade recreates them empty.
- **Consequence:** downloading the same report later shows the data, terms, bank accounts and logo as they are then.
- **Review samples:** written outside the project, to `REPORT_SAMPLES_DIR` or `<temp>/iorp-report-samples` (`tests/report_samples.py`).

## Corporate document identity (DOC-IDENTITY-001)

Every report and document has one header and one footer, from `core/reporting/templates/identity/`. Modules supply data and metadata, never identity.

- **Single source.** «هوية الشركة» (`foundation_organization_branding` plus `foundation_bank_accounts`) holds:
  - the names, logo, tagline and colour;
  - the CR, Unified No. and VAT number;
  - the addresses, phone, e-mail and website;
  - the bank accounts.

  The core reads them through `providers.branding_provider`; it never imports foundation. A test fails if any company value appears in `backend/app` or `frontend/src`.
- **Validation.** CR is 10 digits. The Unified No. is 10 digits starting with 7. The VAT number is 15 digits starting and ending with 3. The website is stored without `https://`.
- **Classification.** `ReportDefinition.classification` is `internal` or `external`. When it is `None`, the audience decides: `audience=customer` gives `external`, otherwise `internal`. Production reports are internal; customer reports follow the chosen audience; the quotation is external.

| | Internal | External |
|---|---|---|
| Header | Arabic name and tagline on the right, logo in the centre, English name and tagline on the left (whatever the document language) | Same, plus the legal identity (CR, Unified No., VAT) under each side, in that side's language |
| Body details | Issued, Prepared by, Department | Issued, Prepared for |
| Footer | One strip: company name · «وثيقة داخلية / Internal document» with the issue time · page X of Y | The contact line (address, phone, e-mail, website), one line per active bank account (bank, account name, account no., IBAN, SWIFT), then a strip: company name · document number · page X of Y |

- **Never on internal documents:** CR, VAT, Unified No., address, phone, e-mail, website or bank data (tested on HTML and on real PDFs).
- **Same templates everywhere.** The on-screen preview and the PDF use the same templates. The PDF repeats header and footer on every page.
- **Margins.** They follow the variant and the number of bank accounts (`default_margins`), so content never overlaps. A definition may override them with `page_margins`.
- **Language.** The direction (RTL or LTR), the name order and the labels follow the document language.
- **Future documents.** A purchase order, delivery note or invoice only needs `classification="external"` to carry the full corporate identity.
