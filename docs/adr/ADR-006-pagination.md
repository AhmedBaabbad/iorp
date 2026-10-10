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
