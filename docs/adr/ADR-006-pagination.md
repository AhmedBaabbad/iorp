# ADR-006: Server-side pagination for every list (ARCH-PAGE-001)

## Context

Lists returned every row at once: `GET /commercial/customers` sent all of an organization's customers, with four
queries per customer for the people on it, and the screen drew them all. The same endpoint filled seven pickers. That
grows with every record: a slower page, a heavier browser, and no way to search.

## Decision

1. **The server cuts the page.** A list endpoint takes `page` (from 1) and `page_size` (default 50; the screens offer 25,
   50, 100; at most 100) and answers `{items, total, page, page_size, pages}` (`backend/app/core/pagination.py`:
   `page_params`, `paginate`, `page_of`).
2. **Search, filters and sort run in the query, before the page is cut**, never in the browser on one page.
3. **A stable order** that ends with a unique column (`created_at desc, id desc`), so a row never repeats or disappears
   between pages.
4. **The total is counted after the permission filter**, so it never reveals rows the user may not see.
5. **Pickers search** (`GET …/lookup?search=&limit=20`) instead of loading a whole list; a list that only needs names asks
   for those ids (`lookup?ids=`).
6. **The page lives in the address** (`?page=3&search=gulf&status=active`): refresh, back and a shared link open the
   same page; a new search or filter goes back to page 1 (`frontend/src/lib/pagination.ts` `useListQuery`).
7. **One bar for every list** (`frontend/src/components/pagination/Pagination.tsx`): "Showing 51 to 100 of 340", the
   first, last and nearby pages, and rows per page.
8. The people on a page are read once each, however many rows they own (no query per row).

Offset pages are used (numbered pages that people can jump to). Keyset/cursor paging is kept for a list that would grow
to millions of rows or scroll endlessly (logs), where counting and deep offsets become costly.

## Applied

The whole customers (commercial) module:

| List | Endpoint | Search | Filters |
|---|---|---|---|
| Customers | `GET /commercial/customers` | code, name, phone, e-mail | status, relationship stage, sales owner, sector |
| Quotations | `GET /commercial/quotes` | number, customer name or code | status, customer |
| Sales orders | `GET /commercial/orders` | number, customer reference, customer | status, customer |
| Samples | `GET /commercial/samples` | code, product, customer | status, customer |
| A customer's interactions | `GET /commercial/customers/{id}/interactions` | — | (latest first, 25 a page on the customer's page) |
| Follow-ups | `GET /commercial/follow-ups` | (already paged) | |

- Each row of the quotation, order and sample pages carries its customer's name and code (and an order its quotation's
  number), read in one query for the page, so the screens no longer load the customer list to show names.
- `GET /commercial/customers/lookup` serves the customer picker (quotations, sales orders, samples).
- Lists bounded by one customer and used as pickers stay plain lists (`/customers/{id}/quotes`, `/samples`, `/orders`).
- Screens: the customers, quotations, sales orders, samples and interactions lists use `useListQuery`, `ListToolbar` and
  `Pagination`.
- Already paged before this decision, to align later: production demands, audit and activity logs.
- Next: the other modules' lists, one at a time.

### Production and quality (PROD-QUALITY-FIX-001, item 2)

Same parameters, envelope, defaults and cap as above. Hidden caps (quality lists returned at most 200 or 500 rows) are
gone. Each order ends with `id`.

| List | Endpoint | Search / filters | Order |
|---|---|---|---|
| Production orders | `GET /production/production-orders` | number or product; status, priority, work center | planned start, number, id |
| Order picker | `GET /production/production-orders/lookup?search=&statuses=&ids=&limit=20` | (≤ 50) | as above |
| Waste records | `GET /production/waste-records` | order, run, work center, category (any of a record's), dates | date ↓, created ↓, id ↓ |
| Downtime events | `GET /production/downtime-events` | as before (the `/summary` figures cover every match) | start ↓, id ↓ |
| Shift rosters | `GET /production/shift-rosters` | shift, worker, dates | effective from ↓, id ↓ |
| A run's roster picker | `GET /production/shift-rosters/active?on=` | rosters in effect that day (one per shift at most) | — |
| An order's "Add a demand" picker | `GET /production/orders/{id}/eligible-demand-items?search=&limit=20` | demand number or customer; same product and unit, quantity left, not in the order (≤ 50) | planning queue order |
| Inspections | `GET /quality/quality-checks` | as before + defect type | date ↓, id ↓ |
| Rejections | `GET /quality/quality-rejections` | as before + `unresolved` | date ↓, created ↓, id ↓ |
| Defects | `GET /quality/quality-defects` | category, severity, order, date | date ↓, created ↓, id ↓ |
| Non-conformance reports | `GET /quality/non-conformance-reports` | as before | date ↓, created ↓, id ↓ |
| Corrective actions | `GET /quality/ncr-actions` | as before | due (empty last), report, id |
| Certificates | `GET /quality/quality-certificates` | as before | created ↓, id ↓ |
| Demands, planning queue | (already paged) | now also answer `pages`; default 50, at most 100 | unchanged |

- Screens: the lists above use `useListQuery` / `usePagedFilters` (`frontend/src/lib/pagination.ts`) and `Pagination`; older
  links (`?order=`, `?status=`, `?work_center=`) still open the filtered list.
- Pickers that loaded every order (waste and downtime forms and filters) use `ProductionOrderPicker` (server search, 20 at
  a time, chosen order named by id). The order page's quality tiles read the server's totals (`page_size=1` per count), an
  inspection's certificates ask for the largest page and link to the rest.
- Stay plain lists, being bounded: an order's runs, lines, results and waste summary; a check's defects; work centers,
  shift definitions, test parameters, reference lists, products and workforce members (reference data for pickers).
- Indexes (migration `f6a1b2m6`): `(organization_id, <sort column>)` on each list above, and `(organization_id, status)` on
  production orders and quality checks.
